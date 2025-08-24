"""Utilities for managing attendance records.

Currently only :func:`listar_activas` is implemented. The remaining
functions are stubs so imports continue working while the rest of the
feature set is developed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from .base import read_json

DATA_DIR = Path(settings.data_dir)


def crear_actividad(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Create a new activity. Placeholder implementation."""
    raise NotImplementedError("crear_actividad is not implemented")


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


def editar_actividad(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Edit an existing activity. Placeholder implementation."""
    raise NotImplementedError("editar_actividad is not implemented")


def registrar_check(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Register a check-in or check-out. Placeholder implementation."""
    raise NotImplementedError("registrar_check is not implemented")


def mis_checkins(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """Return check-ins for a user. Placeholder implementation."""
    raise NotImplementedError("mis_checkins is not implemented")
