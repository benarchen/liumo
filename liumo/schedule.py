"""Pure Shanghai schedule slots shared with legacy probes."""
from datetime import datetime, time as wall_time, timedelta, timezone
from zoneinfo import ZoneInfo
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
