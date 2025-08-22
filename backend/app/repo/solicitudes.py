from __future__ import annotations
import time, secrets

import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Dict, Any
from .base import append_jsonl, ensure_dir
from typing import Any, Dict, List, Optional

from .base import append_jsonl, ensure_dir, read_jsonl
from ..config import settings

SOL_DIR = Path(settings.data_dir) / "solicitudes"
SOL_FILE = SOL_DIR / "solicitudes.jsonl"


def _rewrite_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    """Reescribe un JSONL de forma atómica."""
    ensure_dir(os.path.dirname(path))
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
        for r in rows:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp = tf.name
    os.replace(tmp, path)


def _leer() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(SOL_FILE))) or []

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


def listar(estado: Optional[str] = None, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    """Devuelve las solicitudes opcionalmente filtradas por estado/tipo."""
    rows = _leer()
    if estado:
        rows = [r for r in rows if r.get("estado") == estado]
    if tipo:
        rows = [r for r in rows if r.get("tipo") == tipo]
    return rows


def resolver(
    sol_id: str,
    estado: str,
    admin_id: str,
    comentario: Optional[str] = None,
) -> Dict[str, Any]:
    if estado not in {"aceptada", "denegada"}:
        raise ValueError("estado inválido")
    rows = _leer()
    found: Optional[Dict[str, Any]] = None
    for r in rows:
        if r.get("id") == sol_id:
            if r.get("estado") != "pendiente":
                raise ValueError("Solicitud ya resuelta")
            r["estado"] = estado
            r["resuelto_por_admin_id"] = admin_id
            r["resuelto_en"] = time.time()
            if comentario is not None:
                r["comentario_admin"] = comentario
            found = r
            break
    if not found:
        raise ValueError("Solicitud no encontrada")
    _rewrite_jsonl(str(SOL_FILE), rows)
    return found