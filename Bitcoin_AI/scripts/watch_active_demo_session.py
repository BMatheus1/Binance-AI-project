"""Read-only monitor of one authorized Demo session; never sends requests/orders."""
from __future__ import annotations
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def snapshot(session_id: str) -> dict:
    path = ROOT / "runtime/phase_6_4/autonomous.sqlite3"
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=2) as db:
        db.row_factory = sqlite3.Row
        session = db.execute("SELECT session_id,state,authorized_at,expires_at,entries,stop_reason FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        positions = [dict(row) for row in db.execute("SELECT * FROM positions WHERE session_id=? ORDER BY rowid", (session_id,))]
        activity = db.execute("SELECT recorded_at,event_type,payload_json FROM activity WHERE session_id=? AND event_type!='reconciliation_completed' ORDER BY activity_id DESC LIMIT 1", (session_id,)).fetchone()
    for position in positions:
        position["payload"] = json.loads(position.pop("payload_json"))
        position["fees"] = json.loads(position.pop("fees_json"))
    engine = json.loads((ROOT / "runtime/phase_6_4/engine.json").read_text(encoding="utf-8"))
    kill = json.loads((ROOT / "runtime/phase_6_2/kill_switch.json").read_text(encoding="utf-8"))
    event = dict(activity) if activity else None
    if event:
        event["payload"] = json.loads(event.pop("payload_json"))
    return {"observed_at": datetime.now(timezone.utc).isoformat(), "session": dict(session) if session else None,
            "engine": engine, "kill_switch": kill, "positions": positions, "last_event": event}


def summary(record: dict) -> dict:
    return {"at": record["observed_at"], "session": record["session"],
            "engine_state": record["engine"]["state"], "orders_enabled": record["engine"]["orders_enabled"],
            "reconciliation": record["engine"]["reconciliation"]["state"], "last_error": record["engine"]["last_error"],
            "kill_engaged": record["kill_switch"]["engaged"],
            "positions": [{key: p.get(key) for key in ("position_id", "state", "opened_at", "closed_at", "entry_price", "exit_price", "quantity", "entry_quote", "exit_quote", "net_quote", "close_reason")}
                          | {"entry_category": p["payload"].get("decision", {}).get("entry_category"),
                             "management_estimate": p["payload"].get("management"),
                             "entry_order_id": p["payload"].get("entry", {}).get("orderId"),
                             "exit_order_id": p["payload"].get("exit", {}).get("orderId")} for p in record["positions"]],
            "last_event": record["last_event"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--seconds", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        raise ValueError("monitor duration must be between 1 and 3600 seconds")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.session_id):
        raise ValueError("invalid session ID")
    path = ROOT / "reports/phase_6_4_3" / f"{args.session_id}-monitor.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.seconds
    last_print = 0
    previous = None
    while time.monotonic() < deadline:
        record = snapshot(args.session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        key = (record["engine"]["state"], record["engine"]["last_error"],
               tuple((p["position_id"], p["state"]) for p in record["positions"]))
        if key != previous or time.monotonic()-last_print >= 45:
            print(json.dumps(summary(record), ensure_ascii=False), flush=True)
            last_print = time.monotonic()
            previous = key
        if any(p["state"] == "CLOSED" for p in record["positions"]):
            print("CONFIRMED_LOCAL_CLOSED_POSITION_REQUIRES_EXCHANGE_FILL_AUDIT", flush=True)
            break
        if record["engine"]["state"] == "RECOVERY_REQUIRED":
            break
        time.sleep(5)


if __name__ == "__main__":
    main()
