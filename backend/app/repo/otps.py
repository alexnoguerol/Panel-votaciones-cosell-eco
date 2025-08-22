from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Dict, Tuple

from .base import read_json, write_json, ensure_dir, DATA_DIR
from . import ajustes as ajustes_repo
from ..emailer import send_email

AUTH_DIR = DATA_DIR / "auth"
ensure_dir(AUTH_DIR)
F_OTPS = AUTH_DIR / "otps.json"  # { email: { "code":"123456", "exp": 1234567890, "last_sent":1234567, "attempts":0 } }

def _load() -> Dict[str, Dict]:
    return read_json(F_OTPS, default={}) or {}

def _save(data: Dict[str, Dict]) -> None:
    write_json(F_OTPS, data)

def _gen_code(length: int) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(int(length)))

def request(email: str) -> Tuple[bool, str]:
    cfg = ajustes_repo.get_general()["otp"]
    L = int(cfg["length"])
    ttl = int(cfg["ttl_seconds"])
    resend_win = int(cfg["resend_window_seconds"])
    now = int(time.time())

    store = _load()
    rec = store.get(email, {})
    last_sent = int(rec.get("last_sent", 0))
    if now - last_sent < resend_win:
        return False, f"Espera {resend_win - (now - last_sent)}s para reenviar el código."

    code = _gen_code(L)
    store[email] = {"code": code, "exp": now + ttl, "last_sent": now, "attempts": 0}
    _save(store)

    # Enviar email (no exponemos el código por API)
    try:
        import asyncio
        asyncio.create_task(send_email(email, "Tu código de acceso", f"Tu código es: {code} (caduca en {ttl}s)"))
    except Exception:
        pass

    return True, "Código enviado por email."

def verify(email: str, otp: str) -> Tuple[bool, str]:
    cfg = ajustes_repo.get_general()["otp"]
    now = int(time.time())
    store = _load()
    rec = store.get(email)
    if not rec:
        return False, "Solicita un código primero."
    if now > int(rec.get("exp", 0)):
        return False, "Código expirado. Solicita uno nuevo."
    # (opcional) podrías limitar intentos con cfg["rate_limit_seconds"], aquí solo validamos
    if str(otp).strip() != str(rec.get("code")):
        rec["attempts"] = int(rec.get("attempts", 0)) + 1
        store[email] = rec
        _save(store)
        return False, "Código incorrecto."
    # Consúmelo
    del store[email]
    _save(store)
    return True, "Verificado."
