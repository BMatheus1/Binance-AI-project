from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from btc_research.common import ROOT
from btc_research.dashboard_api import (DashboardRepository, DashboardSettings, create_app,
                                        autonomous_runtime_summary)


@pytest.fixture()
def dashboard_root(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    shutil.copy2(ROOT / "configs/phase_6_2.json", tmp_path / "configs/phase_6_2.json")
    (tmp_path / ".gitignore").write_text(".env\nruntime/phase_6_2/\n", encoding="utf-8")

    execution = tmp_path / "runtime/phase_6_2/execution.sqlite"
    execution.parent.mkdir(parents=True)
    with sqlite3.connect(execution) as db:
        db.execute("""CREATE TABLE order_intents (
            client_order_id TEXT PRIMARY KEY, diagnostic_id TEXT NOT NULL,
            symbol TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL,
            state TEXT NOT NULL, exchange_order_id TEXT, payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        buy = {"executedQty": "0.00012", "cummulativeQuoteQty": "9.60",
               "fills": [{"commission": "0.00000012", "commissionAsset": "BTC"}]}
        sell = {"executedQty": "0.00011", "cummulativeQuoteQty": "8.79",
                "fills": [{"commission": "0.00879", "commissionAsset": "USDT"}]}
        db.execute("INSERT INTO order_intents VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("buy-1", "diag-1", "BTCUSDT", "BUY", "0.00012", "RECONCILED", "1",
                    json.dumps(buy), "2026-10-18T20:00:00+00:00", "2026-10-18T20:00:01+00:00"))
        db.execute("INSERT INTO order_intents VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("sell-1", "diag-1", "BTCUSDT", "SELL", "0.00011", "RECONCILED", "2",
                    json.dumps(sell), "2026-10-18T20:01:00+00:00", "2026-10-18T20:01:01+00:00"))

    events = tmp_path / "runtime/phase_6/events.sqlite3"
    events.parent.mkdir(parents=True)
    with sqlite3.connect(events) as db:
        db.executescript("""CREATE TABLE events(event_id TEXT PRIMARY KEY, source TEXT,
            published_at TEXT, first_received_at TEXT, analyzed_at TEXT, fingerprint TEXT, payload TEXT);
            CREATE TABLE revisions(revision_id INTEGER PRIMARY KEY, event_id TEXT, recorded_at TEXT,
            fingerprint TEXT, payload TEXT);""")
        event = {"event_id": "e1", "source": "official", "title": "Protocol update",
                 "url": "https://example.test/item", "published_at": "2026-10-18T19:00:00+00:00",
                 "first_received_at": "2026-10-18T19:01:00+00:00",
                 "analyzed_at": "2026-10-18T19:01:02+00:00", "affected_assets": ["BTCUSDT"],
                 "event_category": "market_news", "sentiment_by_asset": {"BTCUSDT": "neutral"},
                 "interpretation_confidence": .7, "novelty": .8, "confirmation_status": "confirmed",
                 "market_reaction_evidence": {}, "summary": "metadata only"}
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", ("e1", "official", event["published_at"],
                   event["first_received_at"], event["analyzed_at"], "fp", json.dumps(event)))
    return tmp_path


def fake_account():
    return {"account": {"canTrade": True, "accountType": "SPOT", "permissions": ["SPOT"],
                        "balances": [{"asset": "USDT", "free": "4999", "locked": "0"},
                                     {"asset": "BTC", "free": "0.00000988", "locked": "0"}]},
            "open_orders": {"BTCUSDT": [], "ETHUSDT": [], "SOLUSDT": []},
            "prices": {"BTCUSDT": "80000", "ETHUSDT": "2000", "SOLUSDT": "100"},
            "endpoint": "https://demo-api.binance.com/api", "received_at": "2026-10-18T20:02:00+00:00"}


@pytest.fixture()
def client(dashboard_root):
    settings = DashboardSettings(root=dashboard_root, origins=("http://localhost:3000",),
                                 allow_test_client=True)
    with TestClient(create_app(settings, fake_account)) as test_client:
        yield test_client


def login(client: TestClient) -> str:
    response = client.post("/api/session", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_healthz_has_no_trading_control(client):
    response = client.get("/healthz")
    assert response.json() == {"status": "ok", "mode": "local-observation", "trading_enabled": False}


def test_api_requires_local_session(client):
    assert client.get("/api/overview").status_code == 401
    login(client)
    assert client.get("/api/overview").status_code == 200


def test_dashboard_preparation_reuses_cli_service_requires_csrf_and_never_authorizes(client, monkeypatch):
    calls = []
    payload = {"confirmation": "PREPARAR SESSAO DEMO"}
    assert client.post("/api/control/prepare-session", json=payload).status_code == 401
    token = login(client)
    assert client.post("/api/control/prepare-session", json=payload).status_code == 403
    client.app.state.repository.kill.engage("test_only")
    def prepare(root):
        calls.append(root)
        return {"session_id": "test-prepared", "state": "prepared", "orders_sent": False}
    monkeypatch.setattr("btc_research.dashboard_api.prepare_authorization", prepare)
    response = client.post("/api/control/prepare-session", json=payload,
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": token})
    assert response.status_code == 200 and len(calls) == 1
    assert response.json()["data"]["state"] == "prepared"
    assert client.app.state.repository.kill.status()["engaged"]
    assert client.post("/api/control/authorize-session", json={}).status_code == 404


def test_intelligence_heartbeat_freshness_matches_actual_publication_interval(dashboard_root, monkeypatch):
    repo = DashboardRepository(DashboardSettings(dashboard_root), account_loader=fake_account)
    monkeypatch.setattr(repo, "autonomous", lambda: {})
    path = dashboard_root / "runtime/phase_6_1/heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat = {"state": "running", "updated_at": (datetime.now(timezone.utc)-timedelta(seconds=20)).isoformat(),
                 "heartbeat_interval_seconds": 30, "decision_worker": {"state": "abstaining"}}
    path.write_text(json.dumps(heartbeat), encoding="utf-8")
    assert repo.intelligence()["worker"]["state"] == "abstaining"
    heartbeat["heartbeat_interval_seconds"] = 5
    path.write_text(json.dumps(heartbeat), encoding="utf-8")
    assert repo.intelligence()["worker"]["state"] == "not_running"


def test_backend_cpu_requires_two_samples_and_reuses_process(dashboard_root, monkeypatch):
    from types import SimpleNamespace
    measurements = iter([0., 25.])
    constructions = []
    def process():
        constructions.append(True)
        return SimpleNamespace(cpu_percent=lambda interval=None: next(measurements),
                               memory_info=lambda: SimpleNamespace(rss=1024))
    monkeypatch.setattr("psutil.Process", process)
    repo = DashboardRepository(DashboardSettings(dashboard_root), account_loader=fake_account)
    assert repo.health()["resources"]["cpu_percent"] is None
    assert repo.health()["resources"]["cpu_percent"] == 25.
    assert len(constructions) == 1


def test_session_rejects_untrusted_origin(client):
    response = client.post("/api/session", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_read_token_supports_embedded_browser_without_weakening_mutations(client):
    token = login(client)
    client.cookies.clear()
    read_headers = {"Origin": "http://localhost:3000", "X-Dashboard-Token": token}
    assert client.get("/api/operations", headers=read_headers).status_code == 200
    assert client.get("/api/operations", headers={
        "Origin": "https://evil.example", "X-Dashboard-Token": token,
    }).status_code == 403
    payload = {"reason": "teste local", "confirmation": "ACIONAR KILL SWITCH"}
    assert client.post("/api/control/kill-switch", json=payload, headers={
        "Origin": "http://localhost:3000", "X-CSRF-Token": token,
    }).status_code == 401


def test_overview_uses_real_store_and_marks_residual_dust(client):
    login(client)
    data = client.get("/api/overview").json()["data"]
    btc = next(row for row in data["account"]["balances"] if row["asset"] == "BTC")
    assert btc["category"] == "residual_dust"
    assert data["diagnostic_operation_count"] == 1
    assert data["strategy_performance"]["net_result"] is None
    assert data["strategy_performance"]["trade_count"] == 0


def test_diagnostic_is_separate_from_strategy_metrics(client):
    login(client)
    operation = client.get("/api/operations").json()["data"]["items"][0]
    performance = client.get("/api/performance").json()["data"]
    assert operation["category"] == "diagnostic"
    assert operation["status"] == "reconciled"
    assert operation["residual_base_quantity"] == pytest.approx(0.00000988)
    assert operation["net_result_quote"] is not None
    assert not operation["strategy_evaluation_eligible"]
    assert performance["diagnostic"]["operation_count"] == 1
    assert performance["strategy"]["completed_with_net_result"] == 0


def test_news_contract_uses_metadata_not_summary_body(client):
    login(client)
    item = client.get("/api/news").json()["data"]["items"][0]
    assert item["title"] == "Protocol update"
    assert item["summary_available"] is True
    assert "summary" not in item
    assert item["qwen_classification_available"] is False


def test_kill_switch_requires_csrf_and_cannot_be_cleared(client, dashboard_root):
    csrf = login(client)
    payload = {"reason": "teste local", "confirmation": "ACIONAR KILL SWITCH"}
    assert client.post("/api/control/kill-switch", json=payload,
                       headers={"Origin": "http://localhost:3000"}).status_code == 403
    response = client.post("/api/control/kill-switch", json=payload,
                           headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf})
    assert response.status_code == 200
    state = json.loads((dashboard_root / "runtime/phase_6_2/kill_switch.json").read_text())
    assert state["engaged"] is True and state["reason"].startswith("dashboard:")
    assert all(route.path != "/api/control/kill-switch/clear" for route in client.app.routes)


def test_credentials_never_appear_in_api(client, monkeypatch):
    monkeypatch.setenv("BINANCE_DEMO_API_KEY", "should-never-appear")
    monkeypatch.setenv("BINANCE_DEMO_API_SECRET", "also-never-appear")
    login(client)
    bodies = [client.get(path).text for path in ("/api/overview", "/api/system-health", "/api/logs")]
    assert "should-never-appear" not in "".join(bodies)
    assert "also-never-appear" not in "".join(bodies)


def test_market_unknown_state_does_not_invent_candles(client):
    login(client)
    market = client.get("/api/markets?symbol=BTCUSDT").json()["data"]
    assert market["candles"] == []
    assert market["price"] is None
    assert market["stream_state"] == "stale"


def test_invalid_market_symbol_is_rejected(client):
    login(client)
    assert client.get("/api/markets?symbol=DOGEUSDT").status_code == 422


def test_csv_export_requires_authentication(client):
    assert client.get("/api/export/operations.csv").status_code == 401
    login(client)
    response = client.get("/api/export/operations.csv")
    assert response.status_code == 200
    assert "diagnostic" in response.text


def test_websocket_requires_session_and_streams_snapshot(client):
    csrf = login(client)
    with client.websocket_connect(f"/api/ws?csrf={csrf}",
                                  headers={"Origin": "http://localhost:3000"}) as websocket:
        payload = websocket.receive_json()
    assert payload["type"] == "snapshot"
    assert payload["data"]["overview"]["environment"] == "DEMO"


def test_repository_reads_sqlite_in_query_only_mode(dashboard_root):
    repository = DashboardRepository(DashboardSettings(root=dashboard_root), fake_account)
    assert len(repository.operations()) == 1
    assert repository.health()["reconciliation"]["unresolved"] == 0


def _authorized_runtime(now):
    return {"engine": {"state": "AUTHORIZED_DEMO", "orders_enabled": True,
                       "boot_id": "current-worker", "updated_at": now.isoformat(),
                       "reconciliation": {"state": "healthy", "last_success_at": now.isoformat()}},
            "session_and_positions": {"session": {"state": "authorized",
                "boot_id": "current-worker", "expires_at": (now+timedelta(hours=1)).isoformat()},
                "open_position": None},
            "kill_switch": {"engaged": False}, "limits": {"policy": "A_quantitative"}}


def test_overview_reports_active_phase64_even_when_legacy_readiness_is_blocked(dashboard_root, monkeypatch):
    repository = DashboardRepository(DashboardSettings(root=dashboard_root), fake_account)
    payload = _authorized_runtime(datetime.now(timezone.utc))
    monkeypatch.setattr(repository, "autonomous", lambda: payload)
    result = repository.overview()["autonomous"]
    assert result["ready"] is True
    assert result["status_label"] == "Ativo · Demo"
    assert result["status_tone"] == "good"
    assert result["policy"] == "A_quantitative"
    assert result["source"] == "phase6_4_engine_and_session"


@pytest.mark.parametrize("failure", ["kill", "expired", "boot", "heartbeat", "reconciliation", "disabled", "observe"])
def test_overview_never_labels_failed_runtime_checks_as_active(failure):
    now = datetime.now(timezone.utc)
    data = _authorized_runtime(now)
    if failure == "kill":
        data["kill_switch"]["engaged"] = True
    elif failure == "expired":
        data["session_and_positions"]["session"]["expires_at"] = (now-timedelta(seconds=1)).isoformat()
    elif failure == "boot":
        data["session_and_positions"]["session"]["boot_id"] = "old-worker"
    elif failure == "heartbeat":
        data["engine"]["updated_at"] = (now-timedelta(minutes=1)).isoformat()
    elif failure == "reconciliation":
        data["engine"]["reconciliation"]["state"] = "blocked"
    elif failure == "disabled":
        data["engine"]["orders_enabled"] = False
    else:
        data["engine"]["state"] = "OBSERVE"
    result = autonomous_runtime_summary(data, now)
    assert result["ready"] is False
    assert result["status_tone"] != "good"
    assert result["status_label"] != "Ativo · Demo"

