"""Utilities for managing attendance records.

Currently only :func:`listar_activas` is implemented. The remaining
functions are stubs so imports continue working while the rest of the
feature set is developed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import json
import os
import secrets
import tempfile
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

from . import solicitudes as solicitudes_repo

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


<<<<<<< HEAD
def _participantes_path(act_id: str) -> Path:
    """Ruta del fichero de participantes de la actividad."""
    return _actividad_dir(act_id) / "participantes.json"


def _leer_participantes(act_id: str) -> List[Dict[str, Any]]:
    return read_json(_participantes_path(act_id), default=[]) or []


def _guardar_participantes(act_id: str, items: List[Dict[str, Any]]) -> None:
    write_json(_participantes_path(act_id), items)


def _rewrite_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    """Reescribe un archivo JSONL de forma atómica."""
    ensure_dir(os.path.dirname(path))
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
        for r in rows:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp = tf.name
    os.replace(tmp, path)


def agregar_participante(act_id: str, user_id: str) -> Dict[str, Any]:
    """Añade un participante con el tiempo completo de la reunión."""
    participantes = _leer_participantes(act_id)
    for p in participantes:
        if p.get("user_id") == user_id:
            return p
    meta = _load_meta(act_id)
    dur = int(meta.get("fin_ts", 0) - meta.get("inicio_ts", 0))
    perfil = usuarios_repo.get_perfil(user_id)
    participante = {
        "user_id": user_id,
        "nombre": perfil.get("nombre") or "",
        "niu": perfil.get("niu") or "",
        "tiempo_segundos": dur,
    }
    participantes.append(participante)
    _guardar_participantes(act_id, participantes)
    return participante


def remover_participante(act_id: str, user_id: str, *, limpiar_registros: bool = False) -> None:
    participantes = [p for p in _leer_participantes(act_id) if p.get("user_id") != user_id]
    _guardar_participantes(act_id, participantes)
    if limpiar_registros:
        path = _checks_path(act_id)
        filas: List[Dict[str, Any]] = []
        for rec in read_jsonl(path):
            iterable = rec if isinstance(rec, list) else [rec]
            for r in iterable:
                if r.get("user_id") != user_id:
                    filas.append(r)
        _rewrite_jsonl(str(path), filas)


def ajustar_tiempo(act_id: str, user_id: str, delta: int) -> Dict[str, Any]:
    participantes = _leer_participantes(act_id)
    for p in participantes:
        if p.get("user_id") == user_id:
            p["tiempo_segundos"] = max(0, int(p.get("tiempo_segundos", 0)) + int(delta))
            _guardar_participantes(act_id, participantes)
            return p
    raise ValueError("Participante no encontrado")


def listar_participantes(act_id: str) -> List[Dict[str, Any]]:
    participantes = _leer_participantes(act_id)
    participantes.sort(key=lambda p: p.get("nombre"))
    return participantes


=======
>>>>>>> parent of 9626441 (Participantes cargan borrar funciona a medias)
def obtener_codigo(actividad_id: str) -> str:
    """Return the code associated with an activity."""

    meta = _load_meta(actividad_id)
    codigo = meta.get("codigo")
    if not codigo:
        raise ValueError("Actividad sin código")
    return str(codigo)


def crear_actividad(
    *,
    creador_id: str,
    titulo: str,
    inicio_iso: str,
    fin_iso: str,
    lugar: Optional[str] = None,
    registro_automatico: bool = True,
) -> Dict[str, Any]:
    """Create and persist a new activity."""

    ensure_dir(DATA_DIR / "asistencia")

    inicio_iso2, inicio_ts = _to_ts(inicio_iso)
    fin_iso2, fin_ts = _to_ts(fin_iso)
    if fin_ts <= inicio_ts:
        raise ValueError("fin_iso debe ser posterior a inicio_iso")

    act_id = secrets.token_hex(8)
    codigo = f"{secrets.randbelow(10**6):06d}"
    meta = {
        "id": act_id,
        "titulo": titulo.strip(),
        "inicio_iso": inicio_iso2,
        "fin_iso": fin_iso2,
        "inicio_ts": inicio_ts,
        "fin_ts": fin_ts,
        "lugar": (lugar or "").strip() or None,
        "registro_automatico": bool(registro_automatico),
        "codigo": codigo,
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
        if estado in {"cerrada", "cerrado", "eliminada"} or bool(meta.get("eliminado")):
            continue

        act: Dict[str, Any] = {
            "id": item.name,
            "titulo": meta.get("titulo") or meta.get("nombre") or "",
            "inicio_iso": meta.get("inicio_iso") or meta.get("inicio_utc_iso") or "",
            "fin_iso": meta.get("fin_iso") or meta.get("cierre_iso") or "",
            "inicio_ts": int(meta.get("inicio_ts") or meta.get("inicio_utc_ts") or 0),
            "fin_ts": int(meta.get("fin_ts") or meta.get("cierre_utc_ts") or 0),
            "lugar": meta.get("lugar") or None,
            "registro_automatico": bool(meta.get("registro_automatico")),
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


def obtener_actividad(actividad_id: str) -> Dict[str, Any]:
    """Obtener información básica de una actividad sin incluir el código."""

    meta = _load_meta(actividad_id)
    act: Dict[str, Any] = {
        "id": actividad_id,
        "titulo": meta.get("titulo") or meta.get("nombre") or "",
        "inicio_iso": meta.get("inicio_iso") or meta.get("inicio_utc_iso") or "",
        "fin_iso": meta.get("fin_iso") or meta.get("cierre_iso") or "",
        "inicio_ts": int(meta.get("inicio_ts") or meta.get("inicio_utc_ts") or 0),
        "fin_ts": int(meta.get("fin_ts") or meta.get("cierre_utc_ts") or 0),
        "lugar": meta.get("lugar") or None,
        "registro_automatico": bool(meta.get("registro_automatico")),
        "estado": meta.get("estado") or meta.get("status") or "abierta",
    }
    return act


def editar_actividad(actividad_id: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
    """Modify fields of an activity and persist the result."""

    meta = _load_meta(actividad_id)

    simple_fields = [
        "titulo",
        "inicio_iso",
        "fin_iso",
        "lugar",
        "registro_automatico",
    ]

    for field in simple_fields:
        if field not in cambios or cambios[field] is None:
            continue
        val = cambios[field]
        if field in {"inicio_iso", "fin_iso"}:
            iso2, ts = _to_ts(str(val))
            meta[field] = iso2
            meta[field.replace("_iso", "_ts")] = ts
        elif field in {"registro_automatico"}:
            meta[field] = bool(val)
        else:
            v = str(val).strip()
            if v:
                meta[field] = v

    write_json(_meta_path(actividad_id), meta)
    return meta


def cerrar_actividad(actividad_id: str) -> Dict[str, Any]:
    """Set the activity's closing time to now."""

    meta = _load_meta(actividad_id)
    iso, ts = _now_local()
    meta["fin_iso"] = iso
    meta["fin_ts"] = ts
    write_json(_meta_path(actividad_id), meta)
    return meta


def eliminar_actividad(actividad_id: str) -> None:
    """Mark an activity as deleted."""

    meta = _load_meta(actividad_id)
    meta["estado"] = "eliminada"
    meta["eliminado"] = True
    write_json(_meta_path(actividad_id), meta)


def registrar_check(*, user_id: str, actividad_id: str, accion: str) -> Dict[str, Any]:
    """Register a check-in or check-out for a user."""

    accion = accion.lower().strip()
    if accion not in {"in", "out"}:
        raise ValueError("Acción inválida")

    meta = _load_meta(actividad_id)
    iso_now, ts_now = _now_local()

    inicio = int(meta.get("inicio_ts", ts_now))
    fin = int(meta.get("fin_ts", ts_now))
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


def registrar_check_in_codigo(user_id: str, actividad_id: str, codigo: str) -> Dict[str, Any]:
    """Registrar un check-in verificando un código para una actividad dada."""

    meta = _load_meta(actividad_id)
    if str(meta.get("codigo")) != codigo:
        raise ValueError("Código inválido")
    if meta.get("estado") != "abierta":
        raise ValueError("Actividad cerrada")
    if bool(meta.get("registro_automatico")):
        rec = registrar_check(user_id=user_id, actividad_id=actividad_id, accion="in")
        return {"status": "registrado", "registro": rec, "actividad_id": actividad_id}
    sol_id = solicitudes_repo.crear_solicitud_asistencia(user_id, actividad_id, "in")
    return {"status": "solicitud", "solicitud_id": sol_id, "actividad_id": actividad_id}


def registrar_check_codigo(user_id: str, codigo: str, accion: str) -> Dict[str, Any]:
    """Register a check using an activity code.

    If the activity has ``registro_automatico`` enabled the check is stored
    immediately. Otherwise a pending request is created and its id returned.
    """

    base = DATA_DIR / "asistencia"
    if not base.exists():
        raise ValueError("Código inválido")

    codigo = codigo.strip()
    for item in base.iterdir():
        meta = read_json(_meta_path(item.name)) or {}
        if meta.get("codigo") != codigo:
            continue
        if meta.get("estado") != "abierta":
            raise ValueError("Actividad cerrada")
        act_id = meta.get("id") or item.name
        if bool(meta.get("registro_automatico")):
            rec = registrar_check(user_id=user_id, actividad_id=act_id, accion=accion)
            return {"status": "registrado", "registro": rec, "actividad_id": act_id}
        sol_id = solicitudes_repo.crear_solicitud_asistencia(user_id, act_id, accion)
        return {"status": "solicitud", "solicitud_id": sol_id, "actividad_id": act_id}

    raise ValueError("Código inválido")


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
            # ``checks.jsonl`` files may contain either one JSON object per line
            # or a single line with a JSON array (legacy format).  ``rec`` can
            # therefore be a dict or a list of dicts.  Normalize to an iterable
            # of records before processing.
            iterable = rec if isinstance(rec, list) else [rec]
            for r in iterable:
                if r.get("user_id") == user_id:
                    registros.append(r)
    registros.sort(key=lambda r: r.get("ts", 0))
    return registros


def participantes_de_actividad(actividad_id: str) -> List[Dict[str, Any]]:
    """Return participants of an activity and their records."""

    users: Dict[str, List[Dict[str, Any]]] = {}
    for rec in read_jsonl(_checks_path(actividad_id)):
        iterable = rec if isinstance(rec, list) else [rec]
        for r in iterable:
            uid = r.get("user_id")
            if not uid:
                continue
            users.setdefault(uid, []).append({
                "accion": r.get("accion"),
                "ts": r.get("ts"),
                "iso": r.get("iso"),
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
