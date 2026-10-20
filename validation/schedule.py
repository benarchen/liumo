"""Beijing schedule decisions; a lightweight local probe, no installed job."""

import json
import plistlib
import time
from datetime import datetime, time as wall_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import ROOT, parse_time, timestamp, write_json
from .state import exclusive

SHANGHAI = ZoneInfo("Asia/Shanghai")
SLOTS = ((22, 0), (22, 30), (23, 0), (23, 30))


def latest_slot(now):
    local = now.astimezone(SHANGHAI)
    candidates = [datetime.combine(local.date() - timedelta(days=day), wall_time(h, m), SHANGHAI)
                  for day in (0, 1) for h, m in SLOTS]
    return max(value for value in candidates if value <= local).astimezone(timezone.utc)


def next_slot(now):
    local = now.astimezone(SHANGHAI)
    candidates = [datetime.combine(local.date() + timedelta(days=day), wall_time(h, m), SHANGHAI)
                  for day in (0, 1) for h, m in SLOTS]
    return min(value for value in candidates if value > local).astimezone(timezone.utc)


def decide(now, last_attempt, online, last_online=None):
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    if last_attempt is not None and last_attempt > now:
        return {"run": False, "reason": "clock_moved_backwards"}
    if not online:
        return {"run": False, "reason": "offline", "online": False}
    if last_attempt is None:
        return {"run": True, "reason": "initial_check", "online": True}
    if last_online is False:
        return {"run": True, "reason": "recovery_coalesced", "online": True}
    if latest_slot(now) > last_attempt:
        return {"run": True, "reason": "scheduled_or_missed_coalesced", "online": True}
    return {"run": False, "reason": "not_due", "online": True}


def probe(path, now=None, online=True, hold=0):
    synthetic_clock = now is not None
    path = Path(path)
    with exclusive(path.with_suffix(".lock")):
        state = json.loads(path.read_text()) if path.exists() else {}
        now = now or datetime.now(timezone.utc)
        last = parse_time(state["last_attempt"]) if state.get("last_attempt") else None
        decision = decide(now, last, online, state.get("online"))
        state["online"] = online
        state["observed_at"] = now.isoformat()
        if decision["run"]:
            # This is a lightweight task only, not a successful WeChat list check.
            state["last_attempt"] = now.isoformat()
            state["runs"] = state.get("runs", 0) + 1
        if hold:
            time.sleep(hold)
        write_json(path, state)
        return {"evidence": "synthetic_clock" if synthetic_clock else "local_process", **decision,
                "runs": state.get("runs", 0), "next_slot": next_slot(now).isoformat()}


def render_plist(output):
    """A minute heartbeat avoids launchd's system-local timezone ambiguity.

    Python decides the four Beijing slots; offline recovery checks need the same
    gate. This prototype only runs the no-network probe. RunAtLoad accounts for
    loading/login; real wake/network behavior remains an explicit device test.
    """
    data = {
        "Label": "local.liumo.feasibility",
        "ProgramArguments": [str(ROOT / ".venv/bin/python"), "-m", "validation", "schedule",
                             "--state", str(ROOT / "state/feasibility-schedule.json")],
        "WorkingDirectory": str(ROOT), "RunAtLoad": True,
        "StartCalendarInterval": {},
        "StandardOutPath": str(ROOT / "logs/feasibility-schedule.log"),
        "StandardErrorPath": str(ROOT / "logs/feasibility-schedule-error.log"),
    }
    # An empty calendar dictionary matches every minute (all fields wildcard).
    output = Path(output)
    if output.exists():
        raise FileExistsError("refuse_to_overwrite_schedule")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(plistlib.dumps(data, sort_keys=False))
    return {"generated_at": timestamp(), "path": str(output), "loaded": False}
