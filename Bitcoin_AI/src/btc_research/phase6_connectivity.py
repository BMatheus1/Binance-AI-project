"""Read-only connectivity diagnostics for the Binance Spot Demo environment.

The module contains no order operation. Every network destination is checked
against a fixed Demo-only allowlist before a socket is opened.
"""
from __future__ import annotations

import asyncio
import json
import socket
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import websockets

from .common import ROOT, save_json
from .phase6_2 import (PersistentKillSwitch, build_demo_service,
                       environment_diagnostic, load_local_dotenv,
                       summarize_account)
from .phase6_4 import AutonomousStore, load_phase64_config
from .phase6_trading import (BinanceDemoAPIError, BinanceDemoBroker,
                             RequestsDemoTransport)


DEMO_HOSTS = frozenset({
    "demo-api.binance.com",
    "demo-stream.binance.com",
    "demo-ws-api.binance.com",
})


def _safe_error(exc: BaseException) -> dict[str, Any]:
    result: dict[str, Any] = {"type": type(exc).__name__}
    if isinstance(exc, OSError):
        result["errno"] = exc.errno
        result["winerror"] = getattr(exc, "winerror", None)
    if isinstance(exc, BinanceDemoAPIError):
        result["http_status"] = exc.http_status
        result["api_code"] = exc.api_code
    return result


def _assert_demo_url(url: str, schemes: set[str]) -> tuple[str, int]:
    parsed = urlparse(url)
    if (parsed.scheme not in schemes or parsed.hostname not in DEMO_HOSTS or
            parsed.username or parsed.password):
        raise ValueError("connectivity target is outside the Binance Demo allowlist")
    default_port = 443
    return parsed.hostname, parsed.port or default_port


def dns_check(host: str) -> dict:
    if host not in DEMO_HOSTS:
        raise ValueError("DNS target is outside the Binance Demo allowlist")
    started = time.monotonic()
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({row[4][0] for row in rows})
        return {"available": bool(addresses), "addresses": addresses,
                "latency_ms": round((time.monotonic() - started) * 1000, 3), "error": None}
    except Exception as exc:
        return {"available": False, "addresses": [],
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": _safe_error(exc)}


def tls_check(url: str, timeout_seconds: float = 8) -> dict:
    host, port = _assert_demo_url(url, {"https", "wss"})
    started = time.monotonic()
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout_seconds) as raw:
            peer = raw.getpeername()[0]
            with context.wrap_socket(raw, server_hostname=host) as secured:
                certificate = secured.getpeercert()
                cipher = secured.cipher()
                return {
                    "available": True, "host": host, "port": port, "peer": peer,
                    "tls_version": secured.version(),
                    "cipher": cipher[0] if cipher else None,
                    "certificate_not_after": certificate.get("notAfter"),
                    "hostname_verified": True,
                    "latency_ms": round((time.monotonic() - started) * 1000, 3),
                    "error": None,
                }
    except Exception as exc:
        return {"available": False, "host": host, "port": port,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": _safe_error(exc)}


def rest_check(timeout_seconds: float = 8) -> dict:
    started = time.monotonic()
    try:
        broker = BinanceDemoBroker(enabled=False, transport=RequestsDemoTransport(
            timeout_seconds=timeout_seconds))
        ping = broker.ping()
        server = broker.server_time()
        info = broker.exchange_info("BTCUSDT")
        symbol = next(row for row in info.get("symbols", []) if row.get("symbol") == "BTCUSDT")
        return {
            "available": True, "endpoint": broker.base_url,
            "ping": ping, "server_time_received": isinstance(server.get("serverTime"), int),
            "btcusdt_status": symbol.get("status"),
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "error": None,
        }
    except Exception as exc:
        return {"available": False, "endpoint": "https://demo-api.binance.com/api",
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": _safe_error(exc)}


async def _websocket_check(url: str, *, kind: str, timeout_seconds: float) -> dict:
    _assert_demo_url(url, {"wss"})
    started = time.monotonic()
    try:
        async with websockets.connect(url, open_timeout=timeout_seconds,
                                      close_timeout=2, ping_interval=None) as stream:
            if kind == "ws_api":
                await stream.send(json.dumps({"id": "phase641-read-only-ping", "method": "ping"}))
            raw = await asyncio.wait_for(stream.recv(), timeout=timeout_seconds)
            payload = json.loads(raw)
            if kind == "market":
                valid = isinstance(payload, dict) and payload.get("e") in {"trade", "aggTrade"}
                detail = {"event_type": payload.get("e"), "symbol": payload.get("s")}
            else:
                valid = isinstance(payload, dict) and payload.get("id") == "phase641-read-only-ping"
                detail = {"response_id": payload.get("id"), "status": payload.get("status")}
            return {"available": bool(valid), "url": url, **detail,
                    "latency_ms": round((time.monotonic() - started) * 1000, 3),
                    "error": None if valid else {"type": "UnexpectedPayload"}}
    except Exception as exc:
        return {"available": False, "url": url,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": _safe_error(exc)}


async def websocket_checks(timeout_seconds: float = 8) -> dict:
    market_url = "wss://demo-stream.binance.com/ws/btcusdt@trade"
    alternate_url = "wss://demo-stream.binance.com:9443/ws/btcusdt@trade"
    api_url = "wss://demo-ws-api.binance.com/ws-api/v3"
    primary, alternate, api = await asyncio.gather(
        _websocket_check(market_url, kind="market", timeout_seconds=timeout_seconds),
        _websocket_check(alternate_url, kind="market", timeout_seconds=timeout_seconds),
        _websocket_check(api_url, kind="ws_api", timeout_seconds=timeout_seconds),
    )
    return {"market_443": primary, "market_9443": alternate, "websocket_api": api}


def authenticated_read_check(root: Path = ROOT) -> dict:
    started = time.monotonic()
    try:
        service = build_demo_service(root)
        server = service.broker.server_time()
        account = service.broker.balances()
        summary = summarize_account(account)
        try:
            plan = service.plan("BTCUSDT", __import__("decimal").Decimal("10"))
            plan_result = {"valid": True, "quantity": plan.quantity,
                           "notional": plan.estimated_notional,
                           "minimum_notional": plan.min_notional, "error": None}
        except Exception as exc:
            plan_result = {"valid": False, "error": _safe_error(exc)}
        return {
            "available": True, "authentication": "ok", "can_trade": summary["can_trade"],
            "account_type": summary["account_type"], "permissions": summary["permissions"],
            "nonzero_balances": summary["nonzero_balances"],
            "server_time_received": isinstance(server.get("serverTime"), int),
            "ten_usdt_plan": plan_result,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "error": None, "orders_sent": False,
        }
    except Exception as exc:
        return {"available": False, "authentication": "unavailable",
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "error": _safe_error(exc), "orders_sent": False}


async def diagnose_connectivity(root: Path = ROOT, timeout_seconds: float = 8) -> dict:
    load_local_dotenv(root)
    config = load_phase64_config(root)
    endpoints = config["endpoints"]
    dns = {host: dns_check(host) for host in sorted(DEMO_HOSTS)}
    tls_targets = {
        "rest": endpoints["rest_root"],
        "market_443": endpoints["market_stream"],
        "market_9443": endpoints["market_stream"] + ":9443",
        "websocket_api": endpoints["websocket_api"],
    }
    tls = {name: tls_check(url, timeout_seconds) for name, url in tls_targets.items()}
    websockets_status = await websocket_checks(timeout_seconds)
    rest = rest_check(timeout_seconds)
    authenticated = authenticated_read_check(root)
    kill = PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json").status()
    store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
    session = store.active_session()
    engine_path = root / "runtime/phase_6_4/engine.json"
    try:
        engine = json.loads(engine_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        engine = {}
    authorization_active = bool(
        session and session.get("state") in {"authorized", "running"} and
        session.get("boot_id") == engine.get("boot_id") and not kill["engaged"])
    environment = environment_diagnostic(root)
    all_public = (all(row["available"] for row in dns.values()) and
                  all(row["available"] for row in tls.values()) and rest["available"] and
                  websockets_status["market_443"]["available"] and
                  websockets_status["websocket_api"]["available"])
    result = {
        "checked_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "environment": "DEMO", "mode": "OBSERVE",
        "configured_endpoints": endpoints, "allowlisted_hosts": sorted(DEMO_HOSTS),
        "dns": dns, "tls": tls, "rest": rest, "websockets": websockets_status,
        "authenticated_read": authenticated,
        "public_connectivity_available": all_public,
        "authenticated_connectivity_available": authenticated["available"],
        "kill_switch": kill,
        "authorization_active": authorization_active,
        "orders_sent": False,
        "production_endpoint_tested": False,
        "production_trading_supported": False,
        "credentials_present": all(environment["expected_variables"][name]["nonempty"]
                                   for name in ("BINANCE_DEMO_API_KEY", "BINANCE_DEMO_API_SECRET")),
        "secrets_displayed": False,
    }
    report = root / "reports/phase_6_4_1/connectivity_status.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    save_json(report, result)
    return result

