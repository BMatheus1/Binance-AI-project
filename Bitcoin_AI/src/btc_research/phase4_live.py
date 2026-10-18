"""Observador shadow da Fase 4 sobre os endpoints públicos da Binance."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import numpy as np
import pandas as pd

from .common import ROOT, save_json, write_text
from .features import SPECS, make_features
from .live_market import BinancePublicCollector
from .prospective import (ImmutableLedger, PaperSession, PaperSpotConfig,
                          ProspectiveObserver, prospective_evaluation)


KLINE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                 "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]


def _rest_klines(rows: list) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=KLINE_COLUMNS)
    frame["open_time"] = pd.to_datetime(frame.open_time, unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame.close_time, unit="ms", utc=True)
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    frame["trades"] = pd.to_numeric(frame.trades, errors="raise").astype("int64")
    return frame.drop(columns="ignore")


def _stream_kline(payload: dict) -> pd.DataFrame:
    k = payload["k"]
    return pd.DataFrame([{
        "open_time": pd.to_datetime(k["t"], unit="ms", utc=True), "open": float(k["o"]),
        "high": float(k["h"]), "low": float(k["l"]), "close": float(k["c"]),
        "volume": float(k["v"]), "close_time": pd.to_datetime(k["T"], unit="ms", utc=True),
        "quote_volume": float(k["q"]), "trades": int(k["n"]),
        "taker_base": float(k["V"]), "taker_quote": float(k["Q"]),
    }])


class Phase4ShadowRunner:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.cfg = json.loads((root / "configs/phase_4.json").read_text(encoding="utf-8"))
        self.pointer = json.loads((root / "reports/phase_4/latest.json").read_text(encoding="utf-8"))
        self.results = json.loads((root / self.pointer["results"]).read_text(encoding="utf-8"))
        self.ledger = ImmutableLedger(root / "data/phase_4/prospective" / f"{self.pointer['run_id']}.jsonl")
        self.observers = {}
        self.paper = {}
        for horizon in self.cfg["horizons"]:
            item = self.results["horizons"][str(horizon)]
            selected = item["selected_for_shadow"]
            artifact = item["candidates"][selected]
            self.observers[horizon] = ProspectiveObserver(
                root / artifact["artifact"], self.ledger,
                model_version=f"{self.pointer['run_id']}:{horizon}m:{selected}", horizon_minutes=horizon,
                threshold=max(self.cfg["thresholds"]), expected_sha256=artifact["sha256"])
            self.paper[horizon] = PaperSession(PaperSpotConfig(fee_bps_per_side=5, latency_ms=250))
        self.candles = pd.DataFrame()
        self.pending: list[dict] = []
        self.latest_quote = None
        self.closed_candles_received = 0
        self.duplicate_closed_candles = 0
        self.technical_abstentions = 0
        self.latencies_ms: list[float] = []
        self.source_clock_deltas_ms: list[float] = []
        self.callback_queue_delays_ms: list[float] = []
        self.clock_waits_ms: list[float] = []

    async def warmup(self, rest_base: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(rest_base.rstrip("/") + "/api/v3/klines",
                                   params={"symbol": "BTCUSDT", "interval": "1m", "limit": 250}, timeout=30) as response:
                response.raise_for_status()
                rows = await response.json()
        frame = _rest_klines(rows)
        now = pd.Timestamp.now(tz="UTC")
        self.candles = frame[frame.close_time < now].tail(220).reset_index(drop=True)
        if len(self.candles) < 180 or self.candles.open_time.diff().dropna().ne(pd.Timedelta(minutes=1)).any():
            raise ValueError("Warmup público insuficiente ou descontínuo")
        resolved = {row["prediction_id"] for row in self.ledger.records() if row["record_type"] == "outcome"}
        for prediction in self.ledger.records():
            if (prediction["record_type"] != "prediction" or prediction["prediction_id"] in resolved
                    or prediction["probabilities"] is None):
                continue
            decision_time = pd.Timestamp(prediction["decision_time"])
            feature_open_time = decision_time - pd.Timedelta(minutes=1)
            if feature_open_time in set(self.candles.open_time):
                quote = prediction.get("data_quality", {}).get("observed_quote") or {}
                self.pending.append({"prediction_id": prediction["prediction_id"],
                                     "horizon": int(prediction["horizon_minutes"]),
                                     "feature_open_time": feature_open_time,
                                     "decision": prediction["decision"], "entry_ask": quote.get("ask")})
        self._resolve()

    def _resolve(self) -> None:
        by_time = {time: index for index, time in enumerate(self.candles.open_time)}
        keep = []
        for item in self.pending:
            base = by_time.get(item["feature_open_time"])
            if base is None or len(self.candles) - 1 < base + item["horizon"]:
                keep.append(item)
                continue
            entry = self.candles.iloc[base + 1]
            exit_row = self.candles.iloc[base + item["horizon"]]
            value = exit_row.close / entry.open - 1
            outcome = 0 if value < 0 else 2 if value > 0 else 1
            exit_quote = self.latest_quote or {}
            self.ledger.resolve(item["prediction_id"], event_end=exit_row.open_time.to_pydatetime() + pd.Timedelta(minutes=1),
                                outcome=outcome,
                                entry={"next_open": float(entry.open), "observed_ask_at_decision": item.get("entry_ask")},
                                exit={"close": float(exit_row.close), "observed_bid": exit_quote.get("bid"), "return": float(value)})
            if (item["decision"] == "up" and item.get("entry_ask") and exit_quote.get("bid")
                    and self.paper[item["horizon"]].active):
                self.paper[item["horizon"]].add_spot_result(entry_ask=item["entry_ask"], exit_bid=exit_quote["bid"],
                                                            time=exit_row.close_time.to_pydatetime())
        self.pending = keep

    async def on_event(self, record: dict) -> None:
        payload = record["payload"]
        callback_started = datetime.now(timezone.utc)
        received_at = datetime.fromisoformat(record["received_at"])
        self.callback_queue_delays_ms.append(max(0.0, (callback_started - received_at).total_seconds() * 1000))
        if record.get("source_event_time"):
            latency = (received_at - datetime.fromisoformat(record["source_event_time"])).total_seconds() * 1000
            self.source_clock_deltas_ms.append(latency)
            if latency >= 0:
                self.latencies_ms.append(latency)
        if "b" in payload and "a" in payload and (payload.get("e") == "bookTicker" or record["stream"].endswith("@bookTicker")):
            self.latest_quote = {"bid": float(payload["b"]), "ask": float(payload["a"]),
                                 "received_at": record["received_at"]}
        if payload.get("e") != "kline" or not payload.get("k", {}).get("x", False):
            return
        candle = _stream_kline(payload)
        open_time = candle.open_time.iloc[0]
        if not self.candles.empty and open_time <= self.candles.open_time.iloc[-1]:
            self.duplicate_closed_candles += 1
            return
        continuous = self.candles.empty or open_time == self.candles.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        self.candles = pd.concat([self.candles, candle], ignore_index=True).tail(240).reset_index(drop=True)
        self.closed_candles_received += 1
        self._resolve()
        feature = make_features(self.candles).iloc[[-1]]
        finite = np.isfinite(feature[list(SPECS)].to_numpy()).all()
        decision_time = pd.Timestamp(feature.decision_time.iloc[0]).to_pydatetime()
        clock_wait = max(0.0, (decision_time - datetime.now(timezone.utc)).total_seconds())
        clock_skew_ok = clock_wait <= 2.0
        if clock_wait and clock_skew_ok:
            await asyncio.sleep(clock_wait + .01)
            self.clock_waits_ms.append(clock_wait * 1000)
        complete = bool(continuous and finite and clock_skew_ok)
        quality = {"complete": complete, "closed_candle": True, "continuous": continuous,
                   "warmup_rows": len(self.candles), "book_valid": bool(self.latest_quote),
                   "finite_features": bool(finite), "clock_skew_ok": clock_skew_ok,
                   "clock_wait_ms": clock_wait * 1000, "observed_quote": self.latest_quote}
        for horizon, observer in self.observers.items():
            prediction = observer.observe(feature, quality, now=datetime.now(timezone.utc))
            if prediction["decision"] == "abstain_technical":
                self.technical_abstentions += 1
            if prediction["probabilities"] is not None:
                self.paper[horizon].observe_decision(prediction["decision"] if prediction["decision"] == "up" else "abstain_spot_direction")
                self.pending.append({"prediction_id": prediction["prediction_id"], "horizon": horizon,
                                     "feature_open_time": open_time, "decision": prediction["decision"],
                                     "entry_ask": self.latest_quote.get("ask") if self.latest_quote else None})

    async def run(self, duration_seconds: float = 370) -> dict:
        phase3_cfg = json.loads((self.root / "configs/phase_3.json").read_text(encoding="utf-8"))
        await self.warmup(phase3_cfg["public_rest_base"])
        collector = BinancePublicCollector(
            self.root / "runtime/phase_4/live", phase3_cfg["public_websocket_base"], phase3_cfg["public_rest_base"],
            partition_minutes=phase3_cfg["collector_partition_minutes"],
            reconnect_seconds=phase3_cfg["collector_reconnect_seconds"], event_callback=self.on_event)
        operational = await collector.run(duration_seconds)
        report = {"started_after_freeze": self.pointer["prospective_reservation_created_at"],
                  "duration_seconds": duration_seconds, "operational": operational,
                  "closed_candles_received": self.closed_candles_received,
                  "duplicate_closed_candles": self.duplicate_closed_candles,
                  "technical_abstentions": self.technical_abstentions,
                  "callback_queue_delay_ms": ({"n": len(self.callback_queue_delays_ms),
                                                "median": float(np.median(self.callback_queue_delays_ms)),
                                                "p95": float(np.quantile(self.callback_queue_delays_ms, .95)),
                                                "max": float(np.max(self.callback_queue_delays_ms))}
                                               if self.callback_queue_delays_ms else None),
                  "source_to_receive_clock_delta_ms": ({"n": len(self.source_clock_deltas_ms),
                                                         "median": float(np.median(self.source_clock_deltas_ms)),
                                                         "p05": float(np.quantile(self.source_clock_deltas_ms, .05)),
                                                         "p95": float(np.quantile(self.source_clock_deltas_ms, .95)),
                                                         "min": float(np.min(self.source_clock_deltas_ms)),
                                                         "max": float(np.max(self.source_clock_deltas_ms))}
                                                        if self.source_clock_deltas_ms else None),
                  "clock_alignment_wait_ms": ({"n": len(self.clock_waits_ms),
                                                "median": float(np.median(self.clock_waits_ms)),
                                                "max": float(np.max(self.clock_waits_ms))}
                                               if self.clock_waits_ms else None),
                  "source_to_receive_latency_ms": ({"n": len(self.latencies_ms),
                                                     "median": float(np.median(self.latencies_ms)),
                                                     "p95": float(np.quantile(self.latencies_ms, .95)),
                                                     "max": float(np.max(self.latencies_ms))}
                                                    if self.latencies_ms else None),
                  "pending_outcomes": len(self.pending), "ledger": prospective_evaluation(self.ledger),
                  "paper": {str(h): session.status() for h, session in self.paper.items()},
                  "sufficient_for_economic_conclusion": False, "real_orders": False}
        save_json(self.root / "reports/phase_4/observer_operation.json", report)
        latency = report["source_to_receive_latency_ms"]
        write_text(self.root / "reports/phase_4/03_operacao_observador.md", f"""# 03 — Operação do observador

O smoke test público rodou por {duration_seconds:.0f} segundos após o congelamento. Foram recebidas {operational['messages']} mensagens, com {operational['reconnections']} reconexões, {operational['aggtrade_gap_events']} eventos de gap de AggTrade e {operational['depth_invalidations']} invalidações do livro. O livro terminou válido: {operational['book'].get('valid', False)}.

Candles encerrados novos: {self.closed_candles_received}. Previsões registradas: {report['ledger']['predictions']}; resolvidas: {report['ledger']['resolved']}; pendentes: {len(self.pending)}; abstenções técnicas: {self.technical_abstentions}. Atraso interno até o callback: {report['callback_queue_delay_ms']}. Delta assinado entre relógio da origem e recebimento: {report['source_to_receive_clock_delta_ms']}. Latência origem→recebimento não negativa: {latency if latency else 'indisponível'}.

O teste valida o caminho operacional e a ordem imutável previsão→resultado. A amostra é insuficiente para qualquer conclusão econômica. Nenhuma ordem foi enviada.
""")
        write_text(self.root / "reports/phase_4/07_prospectivo_inicial.md", f"""# 07 — Prospectivo inicial

O ledger contém {report['ledger']['predictions']} previsões e {report['ledger']['resolved']} resultados após este smoke test. Há {len(self.pending)} desfechos aguardando seus horizontes. As métricas, quando calculáveis, estão em `observer_operation.json` e derivam apenas dos registros resolvidos.

Esta quantidade está abaixo dos mínimos congelados de {self.cfg['prospective_minimum_resolved_signals']} sinais resolvidos e {self.cfg['prospective_minimum_days']} dias, além de não cobrir regimes diversos. O resultado não é evidência de viabilidade e não será usado para reajustar os modelos congelados.
""")
        return report


async def run_shadow(duration_seconds: float = 370, root: Path = ROOT) -> dict:
    return await Phase4ShadowRunner(root).run(duration_seconds)
