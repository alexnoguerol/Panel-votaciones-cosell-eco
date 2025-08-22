from __future__ import annotations
import time, secrets
from pathlib import Path
from typing import Dict, Any
from .base import append_jsonl, ensure_dir
from ..config import settings

SOL_DIR = Path(settings.data_dir) / "solicitudes"
SOL_FILE = SOL_DIR / "solicitudes.jsonl"

def crear_solicitud_alta(payload: Dict[str, Any]) -> str:
    ensure_dir(str(SOL_DIR))
    sol_id = secrets.token_hex(8)
    rec = {
        "id": sol_id,
        "tipo": "alta",
        "estado": "pendiente",
        "payload": payload,
        "solicitante_email": payload.get("email"),
        "creado_en": time.time(),
    }
    append_jsonl(str(SOL_FILE), rec)
    return sol_id

def crear_solicitud_mod_perfil(user_id: str, email: str, diff: Dict[str, Any]) -> str:
    ensure_dir(str(SOL_DIR))
    sol_id = secrets.token_hex(8)
    rec = {
        "id": sol_id,
        "tipo": "modificacion_perfil",
        "estado": "pendiente",
        "user_id": user_id,
        "email": email,
        "diff": diff,
        "creado_en": time.time(),
    }
    append_jsonl(str(SOL_FILE), rec)
    return sol_id
