from __future__ import annotations
import os
import json
import time
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from dateutil import parser, tz

from .base import ensure_dir, append_jsonl, read_jsonl
from ..config import settings

# Directorios y ficheros
ASIS_DIR = Path(settings.data_dir) / "asistencia"
ACT_FILE = ASIS_DIR / "actividades.jsonl"
CHK_FILE = ASIS_DIR / "checkins.jsonl"
AJU_FILE = ASIS_DIR / "ajustes.jsonl"  # ajustes de tiempo / eliminación de participantes


# ---------------- Utilidades de tiempo / IO ----------------

def _tz():
    """Zona horaria configurada (settings.tz)."""
    return tz.gettz(settings.tz)

def _now_local() -> tuple[str, int]:
    """Devuelve (iso_local, epoch) en la TZ de settings."""
    dt = datetime.now(tz=_tz())
    return dt.isoformat(timespec="minutes"), int(dt.timestamp())

def _iso_from_ts(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=_tz())
    return dt.isoformat(timespec="minutes")

def _to_ts(local_iso: str) -> tuple[str, int]:
    """
    Convierte una ISO (con o sin zona) a:
      - ISO normalizada a settings.tz (timespec=minutes)
      - timestamp epoch (int)
    Lanza ValueError si el formato no es válido.
    """
    try:
        dt = parser.parse(local_iso)
    except Exception:
        raise ValueError("Formato de fecha inválido. Usa 'YYYY-MM-DDTHH:MM' (ej: 2025-09-20T10:00).")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    else:
        dt = dt.astimezone(_tz())

    iso = dt.isoformat(timespec="minutes")
    return iso, int(dt.timestamp())

def _rewrite_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    """Reescribe un JSONL de forma atómica (tmp + replace)."""
    ensure_dir(os.path.dirname(path))
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
        for r in rows:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp_name = tf.name
    os.replace(tmp_name, path)


# ---------------- Actividades ----------------

def _leer_actividades() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(ACT_FILE))) or []

def listar_activas() -> List[Dict[str, Any]]:
    """Lista actividades no eliminadas, ordenadas por inicio."""
    acts = [a for a in _leer_actividades() if a.get("estado") != "eliminada"]
    return sorted(acts, key=lambda a: a.get("inicio_ts", 0))

def get_actividad(actividad_id: str) -> Dict[str, Any] | None:
    for a in _leer_actividades():
        if a.get("id") == actividad_id:
            return a
    return None

def crear_actividad(
    creador_id: str,
    titulo: str,
    inicio_iso: str,
    fin_iso: str,
    lugar: str | None,
    ventana_antes_min: int,
    ventana_despues_min: int,
    permite_fuera_de_hora: bool,
) -> Dict[str, Any]:
    ensure_dir(str(ASIS_DIR))

    inicio_iso2, inicio_ts = _to_ts(inicio_iso)
    fin_iso2, fin_ts = _to_ts(fin_iso)
    if fin_ts <= inicio_ts:
        raise ValueError("fin_iso debe ser posterior a inicio_iso")

    rec = {
        "id": secrets.token_hex(8),
        "titulo": titulo,
        "inicio_iso": inicio_iso2,
        "fin_iso": fin_iso2,
        "inicio_ts": inicio_ts,
        "fin_ts": fin_ts,
        "lugar": lugar,
        "ventana_antes_min": int(ventana_antes_min),
        "ventana_despues_min": int(ventana_despues_min),
        "permite_fuera_de_hora": bool(permite_fuera_de_hora),
        "estado": "activa",
        "creado_por": creador_id,
        "creado_en": time.time(),
    }
    append_jsonl(str(ACT_FILE), rec)
    return rec

def editar_actividad(actividad_id: str, cambios: dict) -> dict:
    """
    Edita SOLO los campos presentes en `cambios`. Mantiene el resto.
    Soporta:
      - cerrar_ahora: True  → fin = ahora (Europe/Madrid; si ahora < inicio, usa inicio+60s)
      - eliminar: True|False → estado 'eliminada' / 'activa'
      - titulo, lugar, permite_fuera_de_hora, ventana_antes_min, ventana_despues_min
      - inicio_iso, fin_iso (ISO local o con zona)
    """
    acts = _leer_actividades()
    target = next((a for a in acts if a.get("id") == actividad_id), None)
    if not target:
        raise ValueError("Actividad no encontrada")

    # --- Cerrar ahora ---
    if cambios.get("cerrar_ahora"):
        now_ts = int(time.time())
        inicio_ts = int(target.get("inicio_ts", now_ts))
        fin_ts = now_ts if now_ts > inicio_ts else (inicio_ts + 60)
        target["fin_ts"] = fin_ts
        target["fin_iso"] = _iso_from_ts(fin_ts)

    # --- Eliminar / Restaurar (booleano, más intuitivo) ---
    if "eliminar" in cambios:
        target["estado"] = "eliminada" if bool(cambios["eliminar"]) else "activa"

    # --- Campos opcionales (ignoramos strings vacíos para NO pisar) ---
    if "titulo" in cambios and cambios["titulo"] is not None:
        v = str(cambios["titulo"]).strip()
        if v != "":
            target["titulo"] = v  # si viene "", no cambiamos

    if "lugar" in cambios:
        # Para borrar explícitamente, manda null
        if cambios["lugar"] is None:
            target["lugar"] = None
        else:
            v = str(cambios["lugar"]).strip()
            if v != "":
                target["lugar"] = v  # si viene "", no cambiamos

    if "permite_fuera_de_hora" in cambios and cambios["permite_fuera_de_hora"] is not None:
        target["permite_fuera_de_hora"] = bool(cambios["permite_fuera_de_hora"])

    if "ventana_antes_min" in cambios and cambios["ventana_antes_min"] is not None:
        target["ventana_antes_min"] = int(cambios["ventana_antes_min"])

    if "ventana_despues_min" in cambios and cambios["ventana_despues_min"] is not None:
        target["ventana_despues_min"] = int(cambios["ventana_despues_min"])

    # --- Fechas directas (si vienen y no están vacías) ---
    if "inicio_iso" in cambios and cambios["inicio_iso"]:
        v = str(cambios["inicio_iso"]).strip()
        if v != "":
            ini_iso, ini_ts = _to_ts(v)
            target["inicio_iso"] = ini_iso
            target["inicio_ts"] = ini_ts

    if "fin_iso" in cambios and cambios["fin_iso"]:
        v = str(cambios["fin_iso"]).strip()
        if v != "":
            fin_iso, fin_ts = _to_ts(v)
            target["fin_iso"] = fin_iso
            target["fin_ts"] = fin_ts

    # Validación final
    if int(target["fin_ts"]) <= int(target["inicio_ts"]):
        raise ValueError("La hora de fin debe ser posterior al inicio")

    _rewrite_jsonl(str(ACT_FILE), acts)
    return target


# ---------------- Check-ins ----------------

def _leer_checks() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(CHK_FILE))) or []

def _ultima_accion(user_id: str, actividad_id: str) -> str | None:
    """Devuelve 'in' o 'out' si existe algún registro previo de ese usuario/actividad."""
    last = None
    for r in _leer_checks():
        if r.get("user_id") == user_id and r.get("actividad_id") == actividad_id:
            last = r.get("accion")
    return last

def _en_ventana(act: Dict[str, Any], now_ts: int) -> bool:
    if act.get("permite_fuera_de_hora"):
        return True
    antes = int(act.get("ventana_antes_min", 15)) * 60
    despues = int(act.get("ventana_despues_min", 15)) * 60
    return (act["inicio_ts"] - antes) <= now_ts <= (act["fin_ts"] + despues)

def registrar_check(user_id: str, actividad_id: str, accion: str) -> Dict[str, Any]:
    act = get_actividad(actividad_id)
    if not act:
        raise ValueError("Actividad no encontrada")

    now_ts = int(time.time())
    if not _en_ventana(act, now_ts):
        raise ValueError("Fuera de ventana horaria para esta actividad")

    last = _ultima_accion(user_id, actividad_id)
    if accion == "in" and last == "in":
        raise ValueError("Ya estabas dentro (usa 'out' para salir)")
    if accion == "out" and last != "in":
        raise ValueError("No puedes salir si no has hecho 'in'")

    rec = {
        "id": secrets.token_hex(8),
        "actividad_id": actividad_id,
        "user_id": user_id,
        "accion": accion,  # "in" | "out"
        "ts": now_ts,
        "creado_en": time.time(),
    }
    ensure_dir(str(ASIS_DIR))
    append_jsonl(str(CHK_FILE), rec)
    return {"ok": True, "registro": rec}

def mis_checkins(user_id: str, actividad_id: str | None) -> Dict[str, Any]:
    rows = []
    for r in _leer_checks():
        if r.get("user_id") == user_id and (actividad_id is None or r.get("actividad_id") == actividad_id):
            rows.append(r)
    rows.sort(key=lambda r: r.get("ts", 0))
    return {"user_id": user_id, "items": rows}


# ---------------- Ajustes (tiempos / eliminación de participantes) ----------------

def _leer_ajustes() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(AJU_FILE))) or []

def set_ajuste_delta(actividad_id: str, user_id: str, delta_segundos: int, motivo: str, autor_id: str) -> Dict[str, Any]:
    """Suma/resta segundos al total calculado de un usuario."""
    rec = {
        "id": secrets.token_hex(8),
        "tipo": "ajuste_delta",
        "actividad_id": actividad_id,
        "user_id": user_id,
        "delta_segundos": int(delta_segundos),
        "motivo": motivo or "",
        "autor_id": autor_id,
        "ts": time.time(),
    }
    append_jsonl(str(AJU_FILE), rec)
    return rec

def set_total(actividad_id: str, user_id: str, total_segundos: int, motivo: str, autor_id: str) -> Dict[str, Any]:
    """Fija un total exacto para un usuario en una actividad."""
    rec = {
        "id": secrets.token_hex(8),
        "tipo": "set_total",
        "actividad_id": actividad_id,
        "user_id": user_id,
        "total_segundos": int(total_segundos),
        "motivo": motivo or "",
        "autor_id": autor_id,
        "ts": time.time(),
    }
    append_jsonl(str(AJU_FILE), rec)
    return rec

def set_eliminado(actividad_id: str, user_id: str, eliminado: bool, motivo: str, autor_id: str) -> Dict[str, Any]:
    """Marca a un usuario como eliminado/restaurado para una actividad (no aparece en el resumen)."""
    rec = {
        "id": secrets.token_hex(8),
        "tipo": "eliminado",
        "actividad_id": actividad_id,
        "user_id": user_id,
        "eliminado": bool(eliminado),
        "motivo": motivo or "",
        "autor_id": autor_id,
        "ts": time.time(),
    }
    append_jsonl(str(AJU_FILE), rec)
    return rec

def _aplicar_ajustes(actividad_id: str, user_id: str, total_calculado: int) -> tuple[int, bool, List[Dict[str, Any]]]:
    """
    Aplica ajustes para (actividad_id, user_id) en orden de aparición.
    Devuelve: (total_final_no_negativo, eliminado, ajustes_aplicados[])
    """
    total = int(total_calculado)
    eliminado = False
    applied: List[Dict[str, Any]] = []
    for a in _leer_ajustes():
        if a.get("actividad_id") == actividad_id and a.get("user_id") == user_id:
            t = a.get("tipo")
            if t == "ajuste_delta":
                total += int(a.get("delta_segundos", 0))
                applied.append(a)
            elif t == "set_total":
                total = int(a.get("total_segundos", total))
                applied.append(a)
            elif t == "eliminado":
                eliminado = bool(a.get("eliminado"))
                applied.append(a)
    return max(0, total), eliminado, applied

def participantes_de_actividad(actividad_id: str) -> Dict[str, Any]:
    """
    Devuelve:
      {
        "actividad": {...},
        "participantes": [
          {
            "user_id": "...",
            "total_segundos": 1234,         # tras aplicar ajustes
            "registros": [ ... in/out ... ], # crudo
            "ajustes_aplicados": [ ... ]     # historial de ajustes
          },
          ...
        ]
      }
    Oculta los participantes marcados como eliminados.
    """
    act = get_actividad(actividad_id)
    if not act:
        raise ValueError("Actividad no encontrada")

    # Agrupar por usuario
    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for r in _leer_checks():
        if r.get("actividad_id") == actividad_id:
            by_user.setdefault(r["user_id"], []).append(r)

    resumen: List[Dict[str, Any]] = []
    now_ts = int(time.time())

    for uid, rows in by_user.items():
        rows.sort(key=lambda r: r.get("ts", 0))

        # Emparejar in/out
        total = 0
        last_in = None
        for r in rows:
            if r["accion"] == "in":
                last_in = r["ts"]
            elif r["accion"] == "out" and last_in is not None:
                total += max(0, int(r["ts"]) - int(last_in))
                last_in = None
        # Si quedó dentro al cerrar la actividad, computar hasta ahora
        if last_in is not None:
            total += max(0, now_ts - int(last_in))

        total_final, eliminado, applied = _aplicar_ajustes(actividad_id, uid, total)
        if eliminado:
            continue  # no listar eliminados

        resumen.append({
            "user_id": uid,
            "total_segundos": total_final,
            "registros": rows,
            "ajustes_aplicados": applied,
        })

    return {"actividad": act, "participantes": resumen}
