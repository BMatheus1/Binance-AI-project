"""Local, secret-free snapshot and consistent SQLite backups before recovery restart."""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = ROOT / "runtime/phase_6_4/recovery_backups" / stamp
backup.mkdir(parents=True, exist_ok=True)
databases = {
    "observation": "runtime/phase_6_4/observation.sqlite3",
    "autonomous": "runtime/phase_6_4/autonomous.sqlite3",
    "evaluations": "runtime/phase_6_1/evaluations.sqlite3",
    "execution": "runtime/phase_6_2/execution.sqlite",
}
for name, relative in databases.items():
    path = ROOT / relative
    if path.exists():
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as source:
            with sqlite3.connect(backup / f"{name}.sqlite3") as destination:
                source.backup(destination)

with sqlite3.connect(backup / "observation.sqlite3") as db:
    rows = db.execute("SELECT sampled_at,payload_json FROM observation_samples ORDER BY sample_id").fetchall()
payloads = [json.loads(row[1]) for row in rows]
cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
recent = [p for p in payloads if datetime.fromisoformat(p["sampled_at"]) >= cutoff]
failed = [p for p in payloads if not p.get("demo_public", {}).get("available")]
with sqlite3.connect(backup / "autonomous.sqlite3") as db:
    db.row_factory = sqlite3.Row
    failures = [dict(r) for r in db.execute(
        "SELECT recorded_at,event_type,payload_json FROM activity WHERE event_type='reconciliation_failed' ORDER BY activity_id")]
    sessions = [dict(r) for r in db.execute(
        "SELECT session_id,created_at,authorized_at,state,entries,stop_reason FROM sessions ORDER BY created_at")]
    positions = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
with sqlite3.connect(backup / "execution.sqlite3") as db:
    journal_states = dict(db.execute("SELECT state,COUNT(*) FROM order_intents GROUP BY state"))
def fraction(items, predicate):
    return sum(bool(predicate(p)) for p in items) / len(items) if items else None
report = {
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "backup_directory": str(backup.relative_to(ROOT)),
    "consistent_sqlite_backups": list(databases),
    "first_demo_public_failure": failed[0]["sampled_at"] if failed else None,
    "last_demo_public_failure": failed[-1]["sampled_at"] if failed else None,
    "demo_public_failed_samples": len(failed),
    "recent_60m_samples": len(recent),
    "recent_60m_demo_availability": fraction(recent, lambda p: p.get("demo_public", {}).get("available")),
    "latest_collectors": payloads[-1].get("collectors") if payloads else {},
    "reconciliation_failures": failures,
    "sessions": sessions, "experimental_positions": positions,
    "execution_journal_states": journal_states,
    "credentials_read_or_displayed": False, "network_requests": 0, "orders_sent": False,
}
out = ROOT / "reports/phase_6_4_1/recovery" / f"audit_{stamp}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"report": str(out), "backup_directory": str(backup),
                  "recent_60m_demo_availability": report["recent_60m_demo_availability"],
                  "last_demo_public_failure": report["last_demo_public_failure"],
                  "reconciliation_failures": len(failures), "experimental_positions": positions,
                  "latest_collectors": report["latest_collectors"]}, indent=2))
