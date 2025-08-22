from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from ..config import settings
from ..repo.base import append_jsonl, ensure_dir

DATA_DIR = Path(settings.data_dir)
LOG_DIR = DATA_DIR / "logs"
ensure_dir(LOG_DIR)

def _today_path() -> Path:
    return LOG_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"

def audit_event(
    event: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    rec: Dict[str, Any] = {
        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        "event": event,
        "actor_user_id": actor_user_id,
        "actor_email": actor_email,
        "details": details or {},
    }
    if request is not None:
        try:
            rec["ip"] = request.client.host if request.client else None
            rec["method"] = request.method
            rec["path"] = request.url.path
            # Evita loggear tokens/secretos en query
        except Exception:
            pass
    append_jsonl(_today_path(), rec)
