"""Utilities for managing attendance records.

Currently only :func:`listar_activas` is implemented. The remaining
functions are stubs so imports continue working while the rest of the
feature set is developed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import secrets
import time
from datetime import datetime

from dateutil import parser, tz

from ..config import settings
from .base import (
    append_jsonl,
    ensure_dir,
    read_json,
    read_jsonl,
    write_json,
)

DATA_DIR = Path(settings.data_dir)


def _tz():
    """Return the configured timezone object."""
    return tz.gettz(settings.tz)


def _now_local() -> tuple[str, int]:
    """Return current local iso string and timestamp."""
    dt = datetime.now(tz=_tz())
    return dt.isoformat(timespec="minutes"), int(dt.timestamp())


def _to_ts(local_iso: str) -> tuple[str, int]:
    """Parse an ISO string using project timezone."""
    try:
        dt = parser.parse(local_iso)
    except Exception as exc:  # pragma: no cover - validation
        raise ValueError("Fecha inválida") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    else:
        dt = dt.astimezone(_tz())
    return dt.isoformat(timespec="minutes"), int(dt.timestamp())


def _actividad_dir(act_id: str) -> Path:
    return DATA_DIR / "asistencia" / act_id


def _meta_path(act_id: str) -> Path:
    return _actividad_dir(act_id) / "reunion.json"


def _checks_path(act_id: str) -> Path:
    return _actividad_dir(act_id) / "checks.jsonl"


def crear_actividad(
    *,
    creador_id: str,
    titulo: str,
    inicio_iso: str,
    fin_iso: str,
    lugar: Optional[str] = None,
    ventana_antes_min: int = 0,
    ventana_despues_min: int = 0,
    permite_fuera_de_hora: bool = False,
) -> Dict[str, Any]:
    """Create and persist a new activity."""

    ensure_dir(DATA_DIR / "asistencia")

    inicio_iso2, inicio_ts = _to_ts(inicio_iso)
    fin_iso2, fin_ts = _to_ts(fin_iso)
    if fin_ts <= inicio_ts:
        raise ValueError("fin_iso debe ser posterior a inicio_iso")

    act_id = secrets.token_hex(8)
    meta = {
        "id": act_id,
        "titulo": titulo.strip(),
        "inicio_iso": inicio_iso2,
        "fin_iso": fin_iso2,
        "inicio_ts": inicio_ts,
        "fin_ts": fin_ts,
        "lugar": (lugar or "").strip() or None,
        "ventana_antes_min": int(ventana_antes_min),
        "ventana_despues_min": int(ventana_despues_min),
        "permite_fuera_de_hora": bool(permite_fuera_de_hora),
        "estado": "abierta",
        "creado_por": creador_id,
        "creado_en": time.time(),
    }

    ensure_dir(_actividad_dir(act_id))
    write_json(_meta_path(act_id), meta)
    return meta


def listar_activas() -> List[Dict[str, Any]]:
    """Return a list of non-closed activities.

    Activities are stored under ``DATA_DIR / 'asistencia' / <id>`` with a
    ``reunion.json`` file containing their metadata. This function scans the
    directory, reads any available metadata and normalises it to the format
    expected by the API. Activities marked as closed (``estado`` "cerrada") or
    flagged as ``eliminado`` are skipped. If the data directory does not
    exist, an empty list is returned.
    """

    base_dir = DATA_DIR / "asistencia"
    actividades: List[Dict[str, Any]] = []
    if not base_dir.exists():
        return actividades

    for item in base_dir.iterdir():
        if not item.is_dir() or item.name.startswith("."):
            continue
        meta_file = item / "reunion.json"
        if not meta_file.is_file():
            continue
        meta = read_json(meta_file, default={}) or {}

        estado = str(meta.get("estado") or meta.get("status") or "").lower()
        if estado in {"cerrada", "cerrado"} or bool(meta.get("eliminado")):
            continue

        act: Dict[str, Any] = {
            "id": item.name,
            "titulo": meta.get("titulo") or meta.get("nombre") or "",
            "inicio_iso": meta.get("inicio_iso") or meta.get("inicio_utc_iso") or "",
            "fin_iso": meta.get("fin_iso") or meta.get("cierre_iso") or "",
            "inicio_ts": int(meta.get("inicio_ts") or meta.get("inicio_utc_ts") or 0),
            "fin_ts": int(meta.get("fin_ts") or meta.get("cierre_utc_ts") or 0),
            "lugar": meta.get("lugar") or None,
            "ventana_antes_min": int(meta.get("ventana_antes_min") or 0),
            "ventana_despues_min": int(meta.get("ventana_despues_min") or 0),
            "permite_fuera_de_hora": bool(meta.get("permite_fuera_de_hora")),
            "estado": meta.get("estado") or meta.get("status") or "abierta",
        }
        actividades.append(act)

    actividades.sort(key=lambda a: a.get("inicio_ts", 0))
    return actividades


def _load_meta(act_id: str) -> Dict[str, Any]:
    meta = read_json(_meta_path(act_id))
    if not meta:
        raise ValueError("Actividad no encontrada")
    return meta


def editar_actividad(actividad_id: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
    """Modify fields of an activity and persist the result."""

    meta = _load_meta(actividad_id)

    if cambios.get("cerrar_ahora"):
        iso, ts = _now_local()
        meta["fin_iso"] = iso
        meta["fin_ts"] = ts

    if "eliminar" in cambios:
        meta["estado"] = "eliminada" if cambios.get("eliminar") else "abierta"

    simple_fields = [
        "titulo",
        "inicio_iso",
        "fin_iso",
        "lugar",
        "ventana_antes_min",
        "ventana_despues_min",
        "permite_fuera_de_hora",
    ]

    for field in simple_fields:
        if field not in cambios or cambios[field] is None:
            continue
        val = cambios[field]
        if field in {"inicio_iso", "fin_iso"}:
            iso2, ts = _to_ts(str(val))
            meta[field] = iso2
            meta[field.replace("_iso", "_ts")] = ts
        elif field.startswith("ventana"):
            meta[field] = int(val)
        elif field == "permite_fuera_de_hora":
            meta[field] = bool(val)
        else:
            v = str(val).strip()
            if v:
                meta[field] = v

    write_json(_meta_path(actividad_id), meta)
    return meta


def registrar_check(*, user_id: str, actividad_id: str, accion: str) -> Dict[str, Any]:
    """Register a check-in or check-out for a user."""

    accion = accion.lower().strip()
    if accion not in {"in", "out"}:
        raise ValueError("Acción inválida")

    meta = _load_meta(actividad_id)
    iso_now, ts_now = _now_local()

    if not meta.get("permite_fuera_de_hora"):
        ventana_antes = int(meta.get("ventana_antes_min", 0)) * 60
        ventana_despues = int(meta.get("ventana_despues_min", 0)) * 60
        inicio = int(meta.get("inicio_ts", ts_now)) - ventana_antes
        fin = int(meta.get("fin_ts", ts_now)) + ventana_despues
        if not (inicio <= ts_now <= fin):
            raise ValueError("Fuera de la ventana de registro")

    rec = {
        "user_id": user_id,
        "actividad_id": actividad_id,
        "accion": accion,
        "iso": iso_now,
        "ts": ts_now,
    }
    append_jsonl(_checks_path(actividad_id), rec)
    return rec


def mis_checkins(user_id: str, actividad_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return check-in/out records for a user."""

    acts: List[str]
    if actividad_id:
        acts = [actividad_id]
    else:
        base = DATA_DIR / "asistencia"
        acts = [d.name for d in base.iterdir() if d.is_dir()] if base.exists() else []

    registros: List[Dict[str, Any]] = []
    for act in acts:
        for rec in read_jsonl(_checks_path(act)):
            if rec.get("user_id") == user_id:
                registros.append(rec)
    registros.sort(key=lambda r: r.get("ts", 0))
    return registros


def participantes_de_actividad(actividad_id: str) -> List[Dict[str, Any]]:
    """Return participants of an activity and their records."""

    users: Dict[str, List[Dict[str, Any]]] = {}
    for rec in read_jsonl(_checks_path(actividad_id)):
        uid = rec.get("user_id")
        if not uid:
            continue
        users.setdefault(uid, []).append({
            "accion": rec.get("accion"),
            "ts": rec.get("ts"),
            "iso": rec.get("iso"),
        })

    participantes: List[Dict[str, Any]] = []
    for uid, regs in users.items():
        regs.sort(key=lambda r: r.get("ts", 0))
        participantes.append({"user_id": uid, "registros": regs})
    participantes.sort(key=lambda p: p["user_id"])
    return participantes


def set_total(actividad_id: str, user_id: str, total_segundos: int, motivo: str, actor_id: str) -> Dict[str, Any]:
    """Store a manual total time adjustment for a participant."""

    rec = {
        "type": "set_total",
        "user_id": user_id,
        "total_segundos": int(total_segundos),
        "motivo": motivo,
        "actor_id": actor_id,
        "ts": int(time.time()),
    }
    append_jsonl(_actividad_dir(actividad_id) / "ajustes.jsonl", rec)
    return rec


def set_ajuste_delta(actividad_id: str, user_id: str, delta: int, motivo: str, actor_id: str) -> Dict[str, Any]:
    """Store a delta time adjustment for a participant."""

    rec = {
        "type": "ajuste_delta",
        "user_id": user_id,
        "delta": int(delta),
        "motivo": motivo,
        "actor_id": actor_id,
        "ts": int(time.time()),
    }
    append_jsonl(_actividad_dir(actividad_id) / "ajustes.jsonl", rec)
    return rec


def set_eliminado(actividad_id: str, user_id: str, eliminar: bool, motivo: str, actor_id: str) -> Dict[str, Any]:
    """Mark or unmark a participant as removed."""

    rec = {
        "type": "eliminado",
        "user_id": user_id,
        "eliminar": bool(eliminar),
        "motivo": motivo,
        "actor_id": actor_id,
        "ts": int(time.time()),
    }
    append_jsonl(_actividad_dir(actividad_id) / "ajustes.jsonl", rec)
    return rec
