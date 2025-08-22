from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EUROPE_MADRID = ZoneInfo("Europe/Madrid")

def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)

def to_europe_madrid(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EUROPE_MADRID)

def isoformat_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
