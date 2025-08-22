from __future__ import annotations
import csv
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ensure_dir, read_json, write_json
from ..config import settings

USERS_DIR = Path(settings.data_dir) / "usuarios"
INDEX_FILE = USERS_DIR / "index.json"

def _load_index() -> Dict[str, Any]:
    ensure_dir(str(USERS_DIR))
    idx = read_json(str(INDEX_FILE)) or {}
    idx.setdefault("by_email", {})
    idx.setdefault("by_niu", {})
    idx.setdefault("permitidos", {})
    return idx

def _save_index(idx: Dict[str, Any]) -> None:
    ensure_dir(str(USERS_DIR))
    write_json(str(INDEX_FILE), idx)

def _perfil_path(user_id: str) -> Path:
    return USERS_DIR / user_id / "perfil.json"

def _read_perfil(user_id: str) -> Dict[str, Any]:
    return read_json(str(_perfil_path(user_id))) or {}

def _write_perfil(user_id: str, perfil: Dict[str, Any]) -> None:
    dirp = USERS_DIR / user_id
    ensure_dir(str(dirp))
    write_json(str(dirp / "perfil.json"), perfil)

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()

def _norm_niu(niu: str) -> str:
    return (niu or "").strip()

# ----------------------- listar/filtrar -----------------------
def listar(
    query: Optional[str] = None,
    grupo: Optional[str] = None,
    curso: Optional[str] = None,
    es_admin: Optional[bool] = None,
    eliminado: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    ensure_dir(str(USERS_DIR))
    out: List[Dict[str, Any]] = []
    for name in os.listdir(USERS_DIR):
        if name == "index.json":
            continue
        p = _read_perfil(name)
        if not p:
            continue

        if query:
            q = query.strip().lower()
            if q not in (p.get("nombre", "") or "").lower() \
               and q not in (p.get("email", "") or "").lower() \
               and q not in (p.get("niu", "") or "").lower():
                continue
        if grupo is not None and (p.get("grupo") or "") != grupo:
            continue
        if curso is not None and (p.get("curso") or "") != curso:
            continue
        if es_admin is not None and bool(p.get("es_admin")) != bool(es_admin):
            continue
        if eliminado is not None and bool(p.get("eliminado", False)) != bool(eliminado):
            continue

        out.append(p)

    out.sort(key=lambda r: ((r.get("nombre") or "").lower(), r.get("niu") or ""))
    return out

# ----------------------- alta/edición/baja -----------------------
def alta_o_actualiza(
    email: str,
    niu: str,
    nombre: Optional[str] = None,
    grupo: Optional[str] = None,
    curso: Optional[str] = None,
    es_admin: Optional[bool] = None,
    marcar_permitido: bool = True,
) -> Dict[str, Any]:
    email = _norm_email(email)
    niu = _norm_niu(niu)
    if not email or not niu:
        raise ValueError("email y niu son obligatorios")

    idx = _load_index()
    by_email = idx["by_email"]
    by_niu = idx["by_niu"]

    # coherencia índices
    existing_user_id_from_email = by_email.get(email)
    existing_email_from_niu = by_niu.get(niu)
    if existing_user_id_from_email and existing_user_id_from_email != niu:
        raise ValueError("Email ya está asociado a otro NIU")
    if existing_email_from_niu and existing_email_from_niu != email:
        # reasociamos el email del NIU a éste
        by_email.pop(existing_email_from_niu, None)

    user_id = niu
    by_email[email] = user_id
    by_niu[niu] = email
    if marcar_permitido:
        idx["permitidos"][email] = True
    _save_index(idx)

    # perfil en carpeta
    p = _read_perfil(user_id)
    p.setdefault("user_id", user_id)
    p["email"] = email
    p["niu"] = user_id
    if nombre is not None and nombre.strip():
        p["nombre"] = nombre.strip()
    if grupo is not None:
        p["grupo"] = grupo
    if curso is not None:
        p["curso"] = curso
    if es_admin is not None:
        p["es_admin"] = bool(es_admin)
    p.setdefault("eliminado", False)

    p["completo"] = all([
        (p.get("nombre") or "").strip(),
        (p.get("niu") or "").strip(),
        (p.get("email") or "").strip(),
    ])

    _write_perfil(user_id, p)
    return p

def editar(user_id: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
    user_id = _norm_niu(user_id)
    p = _read_perfil(user_id)
    if not p:
        raise ValueError("Usuario no encontrado")

    if "nombre" in cambios and cambios["nombre"] is not None:
        v = str(cambios["nombre"]).strip()
        if v != "":
            p["nombre"] = v
    if "grupo" in cambios and cambios["grupo"] is not None:
        p["grupo"] = str(cambios["grupo"])
    if "curso" in cambios and cambios["curso"] is not None:
        p["curso"] = str(cambios["curso"])
    if "es_admin" in cambios and cambios["es_admin"] is not None:
        p["es_admin"] = bool(cambios["es_admin"])

    p["completo"] = all([
        (p.get("nombre") or "").strip(),
        (p.get("niu") or "").strip(),
        (p.get("email") or "").strip(),
    ])

    _write_perfil(user_id, p)
    return p

def set_admin(user_id: str, es_admin: bool) -> Dict[str, Any]:
    return editar(user_id, {"es_admin": bool(es_admin)})

def baja_logica(user_id: str, undo: bool = False) -> Dict[str, Any]:
    user_id = _norm_niu(user_id)
    p = _read_perfil(user_id)
    if not p:
        raise ValueError("Usuario no encontrado")
    p["eliminado"] = not bool(undo)
    _write_perfil(user_id, p)

    # desmarcar permitido si se da de baja
    idx = _load_index()
    email = p.get("email") or ""
    if email:
        idx["permitidos"][email] = False if not undo else True
        _save_index(idx)
    return p

# ----------------------- export/import CSV -----------------------
def export_csv() -> str:
    rows = listar()
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "niu", "email", "nombre", "grupo", "curso", "es_admin", "eliminado", "completo"])
    for p in rows:
        w.writerow([
            p.get("user_id") or "",
            p.get("niu") or "",
            p.get("email") or "",
            p.get("nombre") or "",
            p.get("grupo") or "",
            p.get("curso") or "",
            "1" if p.get("es_admin") else "0",
            "1" if p.get("eliminado") else "0",
            "1" if p.get("completo") else "0",
        ])
    return buf.getvalue()

def import_csv_text(csv_text: str) -> Dict[str, Any]:
    import io, csv
    f = io.StringIO(csv_text)
    r = csv.DictReader(f)
    req = {"email", "niu", "nombre"}
    if not req.issubset({(h or "").strip().lower() for h in r.fieldnames or []}):
        raise ValueError("Cabeceras requeridas: email, niu, nombre")

    ok, errors = 0, []
    for i, row in enumerate(r, start=2):
        try:
            email = row.get("email") or ""
            niu = row.get("niu") or ""
            nombre = row.get("nombre") or ""
            grupo = row.get("grupo")
            curso = row.get("curso")
            es_admin = None
            if "es_admin" in row and row.get("es_admin") not in (None, ""):
                es_admin = str(row["es_admin"]).strip().lower() in ("1", "true", "yes", "si", "sí")
            alta_o_actualiza(email=email, niu=niu, nombre=nombre, grupo=grupo, curso=curso, es_admin=es_admin, marcar_permitido=True)
            ok += 1
        except Exception as e:
            errors.append({"linea": i, "error": str(e)})
    return {"importados": ok, "errores": errors}
