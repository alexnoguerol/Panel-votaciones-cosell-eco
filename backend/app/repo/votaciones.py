from __future__ import annotations
import os
import json
import time
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from dateutil import parser, tz

from .base import ensure_dir, append_jsonl, read_jsonl
from ..config import settings

# -------------------- Rutas --------------------
VOT_DIR = Path(settings.data_dir) / "votaciones"
VOT_FILE = VOT_DIR / "votaciones.jsonl"
VOTOS_FILE = VOT_DIR / "votos.jsonl"


# -------------------- Util tiempo/IO --------------------
def _tz():
    return tz.gettz(settings.tz)

def _now_local() -> Tuple[str, int]:
    dt = datetime.now(tz=_tz())
    return dt.isoformat(timespec="minutes"), int(dt.timestamp())

def _iso_from_ts(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=_tz())
    return dt.isoformat(timespec="minutes")

def _to_ts(local_iso: str) -> Tuple[str, int]:
    try:
        dt = parser.parse(local_iso)
    except Exception:
        raise ValueError("Fecha inválida. Usa 'YYYY-MM-DDTHH:MM' (ej: 2025-09-20T10:00)")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    else:
        dt = dt.astimezone(_tz())
    return dt.isoformat(timespec="minutes"), int(dt.timestamp())

def _rewrite_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    ensure_dir(os.path.dirname(path))
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
        for r in rows:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp = tf.name
    os.replace(tmp, path)


# -------------------- Core helpers --------------------
def _leer_votaciones() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(VOT_FILE))) or []

def _leer_votos() -> List[Dict[str, Any]]:
    return list(read_jsonl(str(VOTOS_FILE))) or []

def _normalizar_opciones(opciones: List[str]) -> List[str]:
    clean = []
    for o in opciones or []:
        if not isinstance(o, str):
            continue
        v = o.strip()
        if v:
            clean.append(v)
    # mantener orden pero sin duplicados exactos
    seen = set()
    uniq = []
    for o in clean:
        if o not in seen:
            seen.add(o)
            uniq.append(o)
    return uniq

def _hay_votos(votacion_id: str) -> bool:
    for v in _leer_votos():
        if v.get("votacion_id") == votacion_id:
            return True
    return False

def _en_ventana(v: Dict[str, Any], ts: int) -> bool:
    if v.get("permite_fuera_de_hora"):
        return True
    return int(v["inicio_ts"]) <= ts <= int(v["fin_ts"])

def get_votacion(votacion_id: str) -> Optional[Dict[str, Any]]:
    for v in _leer_votaciones():
        if v.get("id") == votacion_id:
            return v
    return None

def listar_vigentes() -> List[Dict[str, Any]]:
    alls = [v for v in _leer_votaciones() if v.get("estado") != "eliminada"]
    return sorted(alls, key=lambda r: r.get("inicio_ts", 0))


# -------------------- CRUD votaciones --------------------
def crear_votacion(
    creador_id: str,
    titulo: str,
    opciones: List[str],
    inicio_iso: str,
    fin_iso: str,
    descripcion: Optional[str],
    permitir_cambiar: bool = False,
    permite_fuera_de_hora: bool = False,
    secreto: bool = True,
    quorum_minimo: Optional[int] = None,
    respuesta_abierta: bool = False,
    respuesta_abierta_etiqueta: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_dir(str(VOT_DIR))
    opts = _normalizar_opciones(opciones)
    if len(opts) < 2 and not respuesta_abierta:
        raise ValueError("Debes indicar al menos 2 opciones o activar respuesta_abierta")

    inicio_iso2, inicio_ts = _to_ts(inicio_iso)
    fin_iso2, fin_ts = _to_ts(fin_iso)
    if fin_ts <= inicio_ts:
        raise ValueError("fin_iso debe ser posterior a inicio_iso")

    rec = {
        "id": secrets.token_hex(8),
        "titulo": titulo.strip(),
        "descripcion": (descripcion or "").strip() or None,
        "opciones": opts,
        "inicio_iso": inicio_iso2,
        "fin_iso": fin_iso2,
        "inicio_ts": inicio_ts,
        "fin_ts": fin_ts,
        "permitir_cambiar": bool(permitir_cambiar),
        "permite_fuera_de_hora": bool(permite_fuera_de_hora),
        "secreto": bool(secreto),
        "quorum_minimo": int(quorum_minimo) if quorum_minimo is not None else None,
        "respuesta_abierta": bool(respuesta_abierta),
        "respuesta_abierta_etiqueta": (respuesta_abierta_etiqueta or "").strip() or "Respuesta abierta",
        "estado": "activa",
        "creado_por": creador_id,
        "creado_en": time.time(),
    }
    append_jsonl(str(VOT_FILE), rec)
    return rec

def editar_votacion(votacion_id: str, cambios: dict) -> Dict[str, Any]:
    rows = _leer_votaciones()
    target = next((x for x in rows if x.get("id") == votacion_id), None)
    if not target:
        raise ValueError("Votación no encontrada")

    # Cerrar ahora
    if cambios.get("cerrar_ahora"):
        now_ts = int(time.time())
        inicio_ts = int(target.get("inicio_ts", now_ts))
        fin_ts = now_ts if now_ts > inicio_ts else (inicio_ts + 60)
        target["fin_ts"] = fin_ts
        target["fin_iso"] = _iso_from_ts(fin_ts)

    # Eliminar / restaurar
    if "eliminar" in cambios:
        target["estado"] = "eliminada" if bool(cambios["eliminar"]) else "activa"

    # Campos simples (ignora strings vacíos)
    if "titulo" in cambios and cambios["titulo"] is not None:
        v = str(cambios["titulo"]).strip()
        if v != "":
            target["titulo"] = v

    if "descripcion" in cambios:
        if cambios["descripcion"] is None:
            target["descripcion"] = None
        else:
            v = str(cambios["descripcion"]).strip()
            if v != "":
                target["descripcion"] = v

    if "permitir_cambiar" in cambios and cambios["permitir_cambiar"] is not None:
        target["permitir_cambiar"] = bool(cambios["permitir_cambiar"])

    if "permite_fuera_de_hora" in cambios and cambios["permite_fuera_de_hora"] is not None:
        target["permite_fuera_de_hora"] = bool(cambios["permite_fuera_de_hora"])

    if "secreto" in cambios and cambios["secreto"] is not None:
        target["secreto"] = bool(cambios["secreto"])

    if "quorum_minimo" in cambios:
        qm = cambios["quorum_minimo"]
        target["quorum_minimo"] = int(qm) if qm is not None else None

    if "respuesta_abierta" in cambios and cambios["respuesta_abierta"] is not None:
        target["respuesta_abierta"] = bool(cambios["respuesta_abierta"])

    if "respuesta_abierta_etiqueta" in cambios:
        if cambios["respuesta_abierta_etiqueta"] is None:
            target["respuesta_abierta_etiqueta"] = "Respuesta abierta"
        else:
            v = str(cambios["respuesta_abierta_etiqueta"]).strip()
            if v != "":
                target["respuesta_abierta_etiqueta"] = v

    # Fechas
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

    # Opciones (si no hay votos emitidos)
    if "opciones" in cambios and cambios["opciones"] is not None:
        if _hay_votos(votacion_id):
            raise ValueError("No se pueden cambiar las opciones: ya hay votos emitidos")
        opts = _normalizar_opciones(list(cambios["opciones"]))
        if len(opts) < 2 and not target.get("respuesta_abierta", False):
            raise ValueError("Debes indicar al menos 2 opciones o activar respuesta_abierta")
        target["opciones"] = opts

    # Coherencia
    if int(target["fin_ts"]) <= int(target["inicio_ts"]):
        raise ValueError("La hora de fin debe ser posterior al inicio")

    _rewrite_jsonl(str(VOT_FILE), rows)
    return target


# -------------------- Votos --------------------
def _ultimo_voto_por_usuario(votacion_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Devuelve dict: user_id -> último voto (por ts) en esa votación.
    """
    by_user: Dict[str, Dict[str, Any]] = {}
    for r in _leer_votos():
        if r.get("votacion_id") == votacion_id:
            uid = r.get("user_id")
            cur = by_user.get(uid)
            if not cur or int(r.get("ts", 0)) >= int(cur.get("ts", 0)):
                by_user[uid] = r
    return by_user

def emitir_voto(user_id: str, votacion_id: str, opcion: Optional[str] = None, texto_abierto: Optional[str] = None) -> Dict[str, Any]:
    v = get_votacion(votacion_id)
    if not v:
        raise ValueError("Votación no encontrada")

    now_ts = int(time.time())
    if not _en_ventana(v, now_ts):
        raise ValueError("Fuera de la ventana de votación")

    # ¿cambia voto?
    ult = _ultimo_voto_por_usuario(votacion_id).get(user_id)
    if ult and not v.get("permitir_cambiar", False):
        raise ValueError("Ya has votado. Esta votación no permite cambiar el voto")

    op = (opcion or "").strip()
    txt = (texto_abierto or "").strip()

    if txt and not v.get("respuesta_abierta", False):
        raise ValueError("Esta votación no admite respuesta abierta")

    if not op and not txt:
        raise ValueError("Debes indicar 'opcion' o 'texto_abierto'")

    if op and txt:
        raise ValueError("Indica solo 'opcion' o solo 'texto_abierto', no ambos")

    if op:
        opciones = [o.strip() for o in v.get("opciones", [])]
        if op not in opciones:
            raise ValueError("Opción no válida")

    # registrar
    rec = {
        "id": secrets.token_hex(8),
        "votacion_id": votacion_id,
        "user_id": user_id,
        "opcion": op or None,
        "texto_abierto": txt or None,
        "ts": now_ts,
        "creado_en": time.time(),
    }
    ensure_dir(str(VOT_DIR))
    append_jsonl(str(VOTOS_FILE), rec)
    return {"ok": True, "voto": rec}

def resultados(votacion_id: str, incluir_detalle: bool = False) -> Dict[str, Any]:
    v = get_votacion(votacion_id)
    if not v:
        raise ValueError("Votación no encontrada")

    ultimos = _ultimo_voto_por_usuario(votacion_id)

    # Conteo de opciones cerradas
    conteo: Dict[str, int] = {o: 0 for o in v.get("opciones", [])}
    # Agregado de abiertas
    abiertas: Dict[str, int] = {}

    for voto in ultimos.values():
        op = (voto.get("opcion") or "").strip()
        if op:
            if op in conteo:
                conteo[op] += 1
        else:
            txt = (voto.get("texto_abierto") or "").strip()
            if txt:
                key = txt.lower()  # agrupar insensible a mayúsculas
                abiertas[key] = abiertas.get(key, 0) + 1

    total_votantes = sum(conteo.values()) + sum(abiertas.values())
    quorum_minimo = v.get("quorum_minimo")
    quorum_ok = None
    if quorum_minimo is not None:
        try:
            quorum_ok = total_votantes >= int(quorum_minimo)
        except Exception:
            quorum_ok = None

    abiertas_list = [
        {"texto": k, "conteo": c} for k, c in sorted(abiertas.items(), key=lambda it: it[1], reverse=True)
    ]

    res: Dict[str, Any] = {
        "votacion": {
            "id": v["id"],
            "titulo": v["titulo"],
            "secreto": bool(v.get("secreto", True)),
            "quorum_minimo": quorum_minimo,
            "respuesta_abierta": bool(v.get("respuesta_abierta", False)),
            "respuesta_abierta_etiqueta": v.get("respuesta_abierta_etiqueta") or "Respuesta abierta",
        },
        "conteo": conteo,
        "abiertas": abiertas_list,
        "total_votantes": total_votantes,
        "quorum_alcanzado": quorum_ok,
    }

    if incluir_detalle and not bool(v.get("secreto", True)):
        detalle = []
        for uid, rv in sorted(_ultimo_voto_por_usuario(votacion_id).items(), key=lambda x: x[0]):
            detalle.append({
                "user_id": uid,
                "opcion": rv.get("opcion"),
                "texto_abierto": rv.get("texto_abierto"),
                "ts": rv.get("ts"),
            })
        res["detalle"] = detalle

    return res

def mis_votos(user_id: str) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for r in _leer_votos():
        if r.get("user_id") != user_id:
            continue
        vid = r.get("votacion_id")
        cur = latest.get(vid)
        if not cur or int(r.get("ts", 0)) >= int(cur.get("ts", 0)):
            latest[vid] = r
    out = list(latest.values())
    out.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return out

# -------------------- Participación y export --------------------
def participantes(votacion_id: str) -> List[Dict[str, Any]]:
    """
    Devuelve lista del último voto por usuario en esa votación.
    """
    v = get_votacion(votacion_id)
    if not v:
        raise ValueError("Votación no encontrada")
    out = []
    for uid, rv in sorted(_ultimo_voto_por_usuario(votacion_id).items(), key=lambda x: x[0]):
        out.append({
            "user_id": uid,
            "opcion": rv.get("opcion"),
            "texto_abierto": rv.get("texto_abierto"),
            "ts": rv.get("ts"),
        })
    return out

def export_csv(votacion_id: str, incluir_detalle: bool) -> str:
    """
    Genera CSV. Si incluir_detalle y la votación NO es secreta -> por usuario.
    Si es secreta o no se pide detalle -> agregado.
    """
    v = get_votacion(votacion_id)
    if not v:
        raise ValueError("Votación no encontrada")

    secret = bool(v.get("secreto", True))
    data = resultados(votacion_id, incluir_detalle=(incluir_detalle and not secret))

    # Detalle por usuario
    if (incluir_detalle and not secret) and "detalle" in data:
        rows = ["user_id,opcion,texto_abierto,ts_iso"]
        for rec in data["detalle"]:
            uid = str(rec.get("user_id") or "")
            op = (rec.get("opcion") or "").replace('"', '""')
            txt = (rec.get("texto_abierto") or "").replace('"', '""')
            ts_iso = _iso_from_ts(int(rec.get("ts") or 0))
            rows.append(f'{uid},"{op}","{txt}",{ts_iso}')
        return "\r\n".join(rows) + "\r\n"

    # Agregado
    rows = ["seccion,valor,conteo"]
    # Opciones cerradas
    for op, cnt in data.get("conteo", {}).items():
        op2 = (op or "").replace('"', '""')
        rows.append(f'opcion,"{op2}",{int(cnt)}')
    # Abiertas
    for item in data.get("abiertas", []):
        txt = (item.get("texto") or "").replace('"', '""')
        rows.append(f'abierta,"{txt}",{int(item.get("conteo") or 0)}')
    return "\r\n".join(rows) + "\r\n"
