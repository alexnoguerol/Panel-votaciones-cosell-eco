from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..config import settings
from . import usuarios as usuarios_repo
from ..repo.base import read_json, read_jsonl

DATA_DIR = Path(settings.data_dir)

def _iter_asistencias(user_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    asis_dir = DATA_DIR / "asistencia"
    if not asis_dir.exists():
        return out
    for reunion in asis_dir.iterdir():
        if not reunion.is_dir() or reunion.name.startswith("."):
            continue
        meta_file = reunion / "reunion.json"
        if not meta_file.is_file():
            continue
        meta = read_json(meta_file, default={}) or {}
        for rec in read_jsonl(reunion / "asistentes.jsonl"):
            if str(rec.get("user_id")) == user_id:
                out.append({
                    "reunion_id": reunion.name,
                    "titulo": meta.get("titulo") or meta.get("nombre"),
                    "hora_union_utc": rec.get("hora_union_utc") or rec.get("ts"),
                    "origen": rec.get("origen"),
                })
    return out

def _iter_votos(user_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    vot_dir = DATA_DIR / "votaciones"
    if not vot_dir.exists():
        return out
    for vot in vot_dir.iterdir():
        if not vot.is_dir():
            continue
        defin = read_json(vot / "definicion_votacion.json", default={}) or {}
        # Si fuera anónima de verdad, no habría vínculo user_id→respuesta en disco
        for rec in read_jsonl(vot / "votos.jsonl"):
            if str(rec.get("user_id")) == user_id:
                out.append({
                    "votacion_id": vot.name,
                    "titulo": defin.get("titulo"),
                    "pregunta_id": rec.get("pregunta_id"),
                    "opcion_id": rec.get("opcion_id"),
                    "texto_abierto": rec.get("texto_abierto"),
                    "emitido_en_utc": rec.get("emitido_en_utc"),
                })
    return out

def build_user_export(user_id: str) -> Dict[str, Any]:
    perfil = usuarios_repo.get_perfil(user_id) or {}
    email = perfil.get("email")
    return {
        "user_id": user_id,
        "email": email,
        "perfil": perfil,
        "asistencias": _iter_asistencias(user_id),
        "votos": _iter_votos(user_id),
    }

def write_user_export(user_id: str) -> str:
    payload = build_user_export(user_id)
    out_dir = DATA_DIR / "usuarios"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"export_privado_{user_id}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)
