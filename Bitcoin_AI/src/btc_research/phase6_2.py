"""Fail-closed Binance Spot Demo execution controls for Phase 6.2.

This module has no production endpoint, does not load secrets at import time and
does not submit an order unless three independent gates are open: the Demo-only
environment flag, a persistent kill switch and an explicit per-command phrase.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from enum import Enum
from pathlib import Path
from typing import Any

from .common import ROOT
from .phase6_trading import (BinanceDemoBroker, DecisionLedger,
                             LocalPaperBroker, RequestsDemoTransport, UNIVERSE)


UTC = timezone.utc
CONFIG_PATH = Path("configs/phase_6_2.json")
EXPECTED_ENV_NAMES = ("BINANCE_DEMO_API_KEY", "BINANCE_DEMO_API_SECRET",
                      "BITCOIN_AI_ENABLE_DEMO_ORDERS")
DEMO_REST = "https://demo-api.binance.com/api"
DEMO_WS_API = "wss://demo-ws-api.binance.com/ws-api/v3"
DEMO_STREAM = "wss://demo-stream.binance.com/stream"
DIAGNOSTIC_CONFIRMATION = "I_AUTHORIZE_ONE_DEMO_DIAGNOSTIC"
KILL_SWITCH_CONFIRMATION = "I_AUTHORIZE_BINANCE_DEMO_ONLY"
AUTONOMOUS_CONFIRMATION = "I_AUTHORIZE_DEMO_AUTONOMOUS"


class ExecutionMode(str, Enum):
    OBSERVE = "OBSERVE"
    PAPER = "PAPER"
    DEMO_DIAGNOSTIC = "DEMO_DIAGNOSTIC"
    DEMO_AUTONOMOUS = "DEMO_AUTONOMOUS"


def load_phase62_config(root: Path = ROOT) -> dict:
    config = json.loads((root / CONFIG_PATH).read_text(encoding="utf-8"))
    expected = {"rest": DEMO_REST, "websocket_api": DEMO_WS_API,
                "market_stream": DEMO_STREAM}
    if config.get("endpoints") != expected:
        raise ValueError("a configuração contém endpoint fora da allowlist Binance Demo")
    if config.get("environment") != "DEMO" or config.get("default_mode") != "OBSERVE":
        raise ValueError("a Fase 6.2 deve iniciar em DEMO/OBSERVE")
    if config.get("real_trading_supported") or config.get("automatic_promotion"):
        raise ValueError("execução real ou promoção automática é proibida")
    if tuple(config.get("universe", ())) != UNIVERSE:
        raise ValueError("universo da Fase 6.2 não corresponde ao universo congelado")
    execution = config["demo_execution"]
    if execution.get("orders_enabled_by_default"):
        raise ValueError("ordens devem permanecer bloqueadas por padrão")
    if execution["maximum_absolute_minutes"] != 23:
        raise ValueError("limite absoluto deve permanecer em 23 minutos")
    if config["autonomous"]["maximum_policies_active"] != 1:
        raise ValueError("somente uma política Demo pode estar ativa")
    return config


def load_local_dotenv(root: Path = ROOT) -> bool:
    """Load the local .env without returning or printing any secret."""
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv não está instalado") from exc
    path = root / ".env"
    if not path.is_file():
        return False
    load_dotenv(path, override=False)
    return True


def environment_diagnostic(root: Path = ROOT) -> dict:
    """Return secret-safe environment metadata only."""
    env_path = root / ".env"
    ignore_path = root / ".gitignore"
    ignore_lines = set()
    if ignore_path.exists():
        ignore_lines = {line.strip() for line in ignore_path.read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#")}
    status = {name: {"present": name in os.environ, "nonempty": bool(os.getenv(name))}
              for name in EXPECTED_ENV_NAMES}
    return {
        "environment": "DEMO",
        "default_mode": ExecutionMode.OBSERVE.value,
        "dotenv_exists": env_path.is_file(),
        "dotenv_ignored": ".env" in ignore_lines or ".env*" in ignore_lines,
        "expected_variables": status,
        "secrets_displayed": False,
        "orders_enabled": os.getenv("BITCOIN_AI_ENABLE_DEMO_ORDERS") == "I_UNDERSTAND_DEMO_ONLY",
        "real_trading_supported": False,
    }


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class PersistentKillSwitch:
    """Persistent, fail-closed gate. Missing or corrupt state means engaged."""
    def __init__(self, path: Path):
        self.path = path

    def status(self) -> dict:
        if not self.path.exists():
            return {"engaged": True, "reason": "not_explicitly_cleared",
                    "updated_at": None}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state.get("engaged"), bool):
                raise ValueError
            return state
        except (OSError, ValueError, json.JSONDecodeError):
            return {"engaged": True, "reason": "invalid_state_fail_closed",
                    "updated_at": None}

    def engage(self, reason: str = "manual") -> dict:
        state = {"engaged": True, "reason": str(reason)[:200],
                 "updated_at": datetime.now(UTC).isoformat()}
        _atomic_json(self.path, state)
        return state

    def clear(self, confirmation: str) -> dict:
        if confirmation != KILL_SWITCH_CONFIRMATION:
            raise PermissionError("confirmação inválida; kill switch permanece ativo")
        state = {"engaged": False, "reason": "explicit_demo_authorization",
                 "updated_at": datetime.now(UTC).isoformat()}
        _atomic_json(self.path, state)
        return state


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"valor inválido em {label}") from exc
    if not result.is_finite():
        raise ValueError(f"valor inválido em {label}")
    return result


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if value <= 0 or step <= 0:
        raise ValueError("quantidade e step devem ser positivos")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    market_step_size: Decimal
    market_min_qty: Decimal
    market_max_qty: Decimal
    min_notional: Decimal
    quote_order_qty_market_allowed: bool

    @classmethod
    def from_exchange_info(cls, payload: dict, symbol: str) -> "SymbolRules":
        rows = payload.get("symbols", [])
        item = next((row for row in rows if row.get("symbol") == symbol), None)
        if not item:
            raise ValueError("símbolo ausente na resposta exchangeInfo")
        filters = {row.get("filterType"): row for row in item.get("filters", [])}
        regular_lot = filters.get("LOT_SIZE")
        market_lot = filters.get("MARKET_LOT_SIZE") or regular_lot
        if not market_lot or not regular_lot:
            raise ValueError("filtro de quantidade de mercado ausente")
        market_step = _decimal(market_lot["stepSize"], "stepSize")
        if market_step <= 0:
            market_step = _decimal(regular_lot["stepSize"], "LOT_SIZE.stepSize")
        market_min = _decimal(market_lot["minQty"], "minQty")
        if market_min <= 0:
            market_min = _decimal(regular_lot["minQty"], "LOT_SIZE.minQty")
        market_max = _decimal(market_lot["maxQty"], "maxQty")
        regular_max = _decimal(regular_lot["maxQty"], "LOT_SIZE.maxQty")
        if market_max <= 0:
            market_max = regular_max
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
        if not notional:
            raise ValueError("filtro de notional ausente")
        return cls(
            symbol=symbol,
            base_asset=item["baseAsset"], quote_asset=item["quoteAsset"],
            status=item.get("status", "UNKNOWN"),
            market_step_size=market_step,
            market_min_qty=market_min,
            market_max_qty=min(market_max, regular_max),
            min_notional=_decimal(notional.get("minNotional", "0"), "minNotional"),
            quote_order_qty_market_allowed=bool(item.get("quoteOrderQtyMarketAllowed", False)),
        )

    def quantity_for_quote(self, quote_amount: Decimal, reference_price: Decimal) -> Decimal:
        if self.status != "TRADING":
            raise ValueError("símbolo não está em estado TRADING")
        if quote_amount < self.min_notional:
            raise ValueError("valor solicitado abaixo do notional mínimo")
        quantity = floor_to_step(quote_amount / reference_price, self.market_step_size)
        if quantity < self.market_min_qty or quantity > self.market_max_qty:
            raise ValueError("quantidade calculada viola MARKET_LOT_SIZE")
        if quantity * reference_price < self.min_notional:
            raise ValueError("quantidade arredondada ficou abaixo do notional mínimo")
        return quantity

    def public_record(self) -> dict:
        row = asdict(self)
        for key, value in list(row.items()):
            if isinstance(value, Decimal):
                row[key] = decimal_text(value)
        return row


def summarize_account(account: dict) -> dict:
    balances = []
    for row in account.get("balances", []):
        free = _decimal(row.get("free", 0), "free")
        locked = _decimal(row.get("locked", 0), "locked")
        if free or locked:
            balances.append({"asset": row.get("asset"), "free": decimal_text(free),
                             "locked": decimal_text(locked)})
    return {
        "can_trade": bool(account.get("canTrade")),
        "can_deposit": bool(account.get("canDeposit")),
        "can_withdraw": bool(account.get("canWithdraw")),
        "account_type": account.get("accountType"),
        "permissions": list(account.get("permissions", [])),
        "nonzero_balances": balances,
        "api_keys_in_output": False,
    }


@dataclass(frozen=True)
class DiagnosticPlan:
    symbol: str
    quote_amount: str
    reference_price: str
    quantity: str
    estimated_notional: str
    available_quote_balance: str
    min_notional: str
    maximum_position_quote: str
    order_will_be_sent: bool = False


class ExecutionJournal:
    """Durable intent journal used before any outbound order request."""
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS order_intents (
                client_order_id TEXT PRIMARY KEY, diagnostic_id TEXT NOT NULL,
                symbol TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL,
                state TEXT NOT NULL, exchange_order_id TEXT,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    def reserve(self, *, client_order_id: str, diagnostic_id: str, symbol: str,
                side: str, quantity: str) -> dict:
        now = datetime.now(UTC).isoformat()
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute("INSERT INTO order_intents VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (client_order_id, diagnostic_id, symbol, side, quantity,
                              "PREPARED", None, "{}", now, now))
        except sqlite3.IntegrityError as exc:
            raise ValueError("client_order_id já reservado; reenvio bloqueado") from exc
        return self.get(client_order_id)

    def transition(self, client_order_id: str, state: str, payload: dict | None = None) -> dict:
        allowed = {"PREPARED", "SUBMITTING", "UNKNOWN", "NEW", "PARTIALLY_FILLED",
                   "FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED"}
        if state not in allowed:
            raise ValueError("estado de ordem inválido")
        payload = payload or {}
        exchange_id = payload.get("orderId")
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "UPDATE order_intents SET state=?, exchange_order_id=?, payload_json=?, updated_at=? "
                "WHERE client_order_id=?",
                (state, str(exchange_id) if exchange_id is not None else None,
                 json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                 datetime.now(UTC).isoformat(), client_order_id))
            if cursor.rowcount != 1:
                raise KeyError("intenção de ordem não encontrada")
        return self.get(client_order_id)

    def get(self, client_order_id: str) -> dict:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM order_intents WHERE client_order_id=?",
                               (client_order_id,)).fetchone()
        if row is None:
            raise KeyError("intenção de ordem não encontrada")
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def unresolved(self) -> list[dict]:
        terminal = ("FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED")
        placeholders = ",".join("?" for _ in terminal)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"SELECT * FROM order_intents WHERE state NOT IN ({placeholders})",
                                terminal).fetchall()
        return [dict(row) for row in rows]


def _balance(account: dict, asset: str) -> Decimal:
    row = next((item for item in account.get("balances", []) if item.get("asset") == asset), None)
    return _decimal(row.get("free", 0) if row else 0, f"saldo {asset}")


class DemoExecutionService:
    """Controlled round-trip executor. Call only from the explicit CLI command."""
    def __init__(self, *, broker: BinanceDemoBroker, kill_switch: PersistentKillSwitch,
                 journal: ExecutionJournal, ledger: DecisionLedger, config: dict):
        self.broker = broker
        self.kill_switch = kill_switch
        self.journal = journal
        self.ledger = ledger
        self.config = config

    def plan(self, symbol: str, quote_amount: Decimal) -> DiagnosticPlan:
        if symbol not in self.config["universe"]:
            raise ValueError("símbolo fora do universo congelado")
        limit = _decimal(self.config["demo_execution"]["maximum_position_quote"], "limite")
        if quote_amount <= 0 or quote_amount > limit:
            raise ValueError("valor fora do limite de posição diagnóstica")
        account = self.broker.balances()
        rules = SymbolRules.from_exchange_info(self.broker.exchange_info(symbol), symbol)
        average = _decimal(self.broker.average_price(symbol)["price"], "preço médio")
        quantity = rules.quantity_for_quote(quote_amount, average)
        available = _balance(account, rules.quote_asset)
        notional = quantity * average
        if not account.get("canTrade"):
            raise PermissionError("a conta Demo não possui permissão de negociação")
        if available < notional:
            raise ValueError("saldo virtual insuficiente para o diagnóstico")
        if self.journal.unresolved():
            raise RuntimeError("há intenção de ordem não resolvida no diário; reconcilie antes de continuar")
        if self.broker.open_orders(symbol):
            raise RuntimeError("há ordem Demo aberta no símbolo; nova entrada bloqueada")
        return DiagnosticPlan(symbol, decimal_text(quote_amount), decimal_text(average),
                              decimal_text(quantity), decimal_text(notional),
                              decimal_text(available), decimal_text(rules.min_notional),
                              decimal_text(limit))

    @staticmethod
    def _diagnostic_economics(buy: dict, sell: dict, quote_asset: str) -> dict:
        buy_quote = _decimal(buy.get("cummulativeQuoteQty", 0), "buy quote")
        sell_quote = _decimal(sell.get("cummulativeQuoteQty", 0), "sell quote")
        quote_fees = Decimal("0")
        non_quote_fees = []
        for order in (buy, sell):
            for fill in order.get("fills", []):
                fee = _decimal(fill.get("commission", 0), "commission")
                asset = fill.get("commissionAsset")
                if asset == quote_asset:
                    quote_fees += fee
                elif fee:
                    non_quote_fees.append({"asset": asset, "amount": decimal_text(fee)})
        complete = not non_quote_fees and buy_quote > 0 and sell_quote > 0
        return {
            "buy_quote": decimal_text(buy_quote), "sell_quote": decimal_text(sell_quote),
            "quote_fees": decimal_text(quote_fees), "non_quote_fees": non_quote_fees,
            "net_quote": decimal_text(sell_quote - buy_quote - quote_fees) if complete else None,
            "net_quote_complete": complete,
            "strategy_evaluation_eligible": False,
        }

    def _recover_once(self, symbol: str, client_id: str) -> dict:
        """Query once after an ambiguous submission; never repeat the order."""
        try:
            return self.broker.order_status(symbol=symbol, client_order_id=client_id)
        except Exception:
            self.journal.transition(client_id, "UNKNOWN", {"recovery": "status_unavailable"})
            self.kill_switch.engage("unknown_order_status")
            raise RuntimeError("status da ordem desconhecido; novas entradas bloqueadas") from None

    def _submit(self, *, diagnostic_id: str, symbol: str, side: str,
                quantity: str, client_id: str) -> dict:
        self.journal.reserve(client_order_id=client_id, diagnostic_id=diagnostic_id,
                             symbol=symbol, side=side, quantity=quantity)
        self.journal.transition(client_id, "SUBMITTING")
        try:
            response = self.broker.submit_market(symbol=symbol, side=side,
                                                 quantity=quantity, client_order_id=client_id)
        except Exception:
            response = self._recover_once(symbol, client_id)
        status = response.get("status", "UNKNOWN")
        if status not in {"NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
            self.journal.transition(client_id, "UNKNOWN", {"status": status})
            self.kill_switch.engage("unexpected_order_status")
            raise RuntimeError("status de ordem inesperado; novas entradas bloqueadas")
        self.journal.transition(client_id, status, response)
        return response

    def execute_diagnostic(self, *, symbol: str, quote_amount: Decimal,
                           confirmation: str) -> dict:
        if confirmation != DIAGNOSTIC_CONFIRMATION:
            raise PermissionError("confirmação explícita da operação diagnóstica ausente")
        if self.kill_switch.status()["engaged"]:
            raise PermissionError("kill switch ativo")
        if not self.broker.enabled:
            raise PermissionError("envio de ordens Demo não foi habilitado no .env")
        plan = self.plan(symbol, quote_amount)
        rules = SymbolRules.from_exchange_info(self.broker.exchange_info(symbol), symbol)
        diagnostic_id = f"diag-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        buy_id = f"bai62-b-{uuid.uuid4().hex[:20]}"
        self.ledger.append("demo_diagnostic_prepared", {**asdict(plan),
                           "diagnostic_id": diagnostic_id}, datetime.now(UTC))
        try:
            buy = self._submit(diagnostic_id=diagnostic_id, symbol=symbol, side="BUY",
                               quantity=plan.quantity, client_id=buy_id)
            if buy.get("status") in {"NEW", "PARTIALLY_FILLED"}:
                self.broker.cancel(symbol=symbol, client_order_id=buy_id)
                buy = self.broker.order_status(symbol=symbol, client_order_id=buy_id)
                self.journal.transition(buy_id, buy.get("status", "UNKNOWN"), buy)
            executed = _decimal(buy.get("executedQty", 0), "executedQty")
            for fill in buy.get("fills", []):
                if fill.get("commissionAsset") == rules.base_asset:
                    executed -= _decimal(fill.get("commission", 0), "commission")
            sell_quantity = floor_to_step(executed, rules.market_step_size)
            if sell_quantity < rules.market_min_qty:
                raise RuntimeError("quantidade adquirida insuficiente para encerramento válido")
            sell_id = f"bai62-s-{uuid.uuid4().hex[:20]}"
            sell = self._submit(diagnostic_id=diagnostic_id, symbol=symbol, side="SELL",
                                quantity=decimal_text(sell_quantity), client_id=sell_id)
            if sell.get("status") in {"NEW", "PARTIALLY_FILLED"}:
                self.broker.cancel(symbol=symbol, client_order_id=sell_id)
                sell = self.broker.order_status(symbol=symbol, client_order_id=sell_id)
                self.journal.transition(sell_id, sell.get("status", "UNKNOWN"), sell)
            sold = _decimal(sell.get("executedQty", 0), "sell executedQty")
            if sold < sell_quantity:
                self.kill_switch.engage("diagnostic_position_not_fully_closed")
                raise RuntimeError("encerramento parcial; posição residual exige reconciliação")
            open_orders = self.broker.open_orders(symbol)
            result = {"diagnostic_id": diagnostic_id, "mode": "DEMO_DIAGNOSTIC",
                      "strategy_evaluation_eligible": False, "buy": buy, "sell": sell,
                      "remaining_open_orders": len(open_orders), "reconciled": not open_orders,
                      "diagnostic_economics": self._diagnostic_economics(
                          buy, sell, rules.quote_asset)}
            if open_orders:
                self.kill_switch.engage("diagnostic_reconciliation_failed")
                raise RuntimeError("reconciliação encontrou ordens abertas; kill switch acionado")
            self.journal.transition(buy_id, "RECONCILED", buy)
            self.journal.transition(sell_id, "RECONCILED", sell)
            self.kill_switch.engage("diagnostic_completed_rearm_required")
            self.ledger.append("demo_diagnostic_completed", result, datetime.now(UTC))
            return result
        except Exception as exc:
            self.kill_switch.engage(f"diagnostic_failure:{type(exc).__name__}")
            self.ledger.append("demo_diagnostic_failed", {"diagnostic_id": diagnostic_id,
                               "error_type": type(exc).__name__}, datetime.now(UTC))
            raise


@dataclass(order=True)
class PrioritizedNewsJob:
    priority: float
    sequence: int
    received_at_epoch: float
    text: str
    fingerprint: str


class PriorityInferenceQueue:
    """Bounded async priority queue with stale-item rejection and deduplication."""
    def __init__(self, *, maxsize: int = 64, maximum_age_seconds: float = 600):
        if maxsize < 1 or maximum_age_seconds <= 0:
            raise ValueError("configuração inválida da fila neural")
        self.queue: asyncio.PriorityQueue[PrioritizedNewsJob] = asyncio.PriorityQueue(maxsize=maxsize)
        self.maximum_age_seconds = maximum_age_seconds
        self._fingerprints: set[str] = set()
        self._sequence = 0
        self.metrics = {"accepted": 0, "duplicates": 0, "queue_full": 0, "stale": 0}

    def submit(self, *, text: str, fingerprint: str, received_at_epoch: float,
               novelty: float, relevance: float) -> bool:
        age = max(0.0, time.time() - received_at_epoch)
        if age > self.maximum_age_seconds:
            self.metrics["stale"] += 1
            return False
        if fingerprint in self._fingerprints:
            self.metrics["duplicates"] += 1
            return False
        score = max(0.0, min(1.0, novelty)) * .4 + max(0.0, min(1.0, relevance)) * .6
        job = PrioritizedNewsJob(-score, self._sequence, received_at_epoch, text, fingerprint)
        self._sequence += 1
        try:
            self.queue.put_nowait(job)
        except asyncio.QueueFull:
            self.metrics["queue_full"] += 1
            return False
        self._fingerprints.add(fingerprint)
        self.metrics["accepted"] += 1
        return True

    async def next_valid(self) -> PrioritizedNewsJob | None:
        while not self.queue.empty():
            job = await self.queue.get()
            self._fingerprints.discard(job.fingerprint)
            if time.time() - job.received_at_epoch > self.maximum_age_seconds:
                self.metrics["stale"] += 1
                self.queue.task_done()
                continue
            return job
        return None


def endpoint_safety_check() -> dict:
    rejected = []
    for url in ("https://api.binance.com/api", "https://api1.binance.com/api",
                "http://demo-api.binance.com/api", "https://example.com/api"):
        try:
            BinanceDemoBroker(base_url=url)
        except ValueError:
            rejected.append(url)
    return {"demo_rest": DEMO_REST, "production_endpoints_rejected": len(rejected) == 4,
            "rejected_count": len(rejected), "fallback_to_production": False}


def build_demo_service(root: Path = ROOT) -> DemoExecutionService:
    config = load_phase62_config(root)
    broker = BinanceDemoBroker.from_environment(RequestsDemoTransport())
    return DemoExecutionService(
        broker=broker,
        kill_switch=PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json"),
        journal=ExecutionJournal(root / "runtime/phase_6_2/execution.sqlite"),
        ledger=DecisionLedger(root / "runtime/phase_6_2/decision_ledger.jsonl"),
        config=config,
    )


def autonomous_readiness(root: Path = ROOT) -> dict:
    config = load_phase62_config(root)
    auto = config["autonomous"]
    kill = PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json").status()
    checks = {
        "single_frozen_policy": auto["maximum_policies_active"] == 1 and bool(auto["frozen_policy"]),
        "prospective_policy_approved": bool(auto["prospective_policy_approved"]),
        "diagnostic_round_trip_validated": bool(auto["diagnostic_round_trip_validated"]),
        "demo_order_environment_enabled": os.getenv("BITCOIN_AI_ENABLE_DEMO_ORDERS") == "I_UNDERSTAND_DEMO_ONLY",
        "kill_switch_cleared": not kill["engaged"],
    }
    return {"mode": "DEMO_AUTONOMOUS", "policy": auto["frozen_policy"],
            "ready": all(checks.values()), "checks": checks,
            "automatic_promotion": False, "real_trading_supported": False}

