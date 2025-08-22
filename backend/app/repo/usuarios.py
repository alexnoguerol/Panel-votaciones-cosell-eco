# backend/app/repo/usuarios.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ensure_dir, read_json, write_json
from ..config import settings  # <- FIX: sube un nivel

# -------------------- Rutas / ficheros --------------------
USERS_DIR = Path(settings.data_dir) / "usuarios"
INDEX_FILE = USERS_DIR / "index.json"

# -------------------- Utilidades de IO --------------------
def _load_index() -> Dict[str, Any]:
    """Lee el índice de usuarios, garantizando la estructura mínima."""
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
    d = USERS_DIR / user_id
    ensure_dir(str(d))
    write_json(str(d / "perfil.json"), perfil)

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()

def _norm_niu(niu: str) -> str:
    return (niu or "").strip()

def _recalcula_completitud(p: Dict[str, Any]) -> bool:
    ok = bool((p.get("nombre") or "").strip()) and bool((p.get("niu") or "").strip()) and bool((p.get("email") or "").strip())
    p["completo"] = ok
    return ok

# -------------------- Lectura / existencia --------------------
def has_any_user(include_eliminados: bool = False) -> bool:
    """Devuelve True si existe al menos un usuario (según perfiles en carpeta)."""
    ensure_dir(str(USERS_DIR))
    for name in os.listdir(USERS_DIR):
        if name == "index.json":
            continue
        p = _read_perfil(name)
        if not p:
            continue
        if include_eliminados or not bool(p.get("eliminado", False)):
            return True
    return False

def get_user_id_by_email(email: str) -> Optional[str]:
    email = _norm_email(email)
    idx = _load_index()
    return idx.get("by_email", {}).get(email)

def user_exists_by_email(email: str) -> bool:
    email = _norm_email(email)
    uid = get_user_id_by_email(email)
    if not uid:
        return False
    p = _read_perfil(uid)
    return bool(p) and not bool(p.get("eliminado", False))

def user_exists(user_id: str) -> bool:
    user_id = _norm_niu(user_id)
    p = _read_perfil(user_id)
    return bool(p) and not bool(p.get("eliminado", False))

def get_perfil(user_id: str) -> Dict[str, Any]:
    user_id = _norm_niu(user_id)
    p = _read_perfil(user_id)
    # normaliza claves esperadas
    if p:
        p.setdefault("user_id", user_id)
        p.setdefault("email", "")
        p.setdefault("niu", user_id)
        p.setdefault("nombre", "")
        p.setdefault("grupo", None)
        p.setdefault("curso", None)
        p.setdefault("es_admin", False)
        p.setdefault("eliminado", False)
        _recalcula_completitud(p)
    return p

# Alias usado por algún router
get_profile = get_perfil

# -------------------- Escritura / coherencia --------------------
def ensure_profile_links_if_exists(user_id: str, email: str) -> None:
    """
    Asegura coherencia de índices y campos (email/NIU) SOLO si el perfil existe.
    No crea perfiles nuevos.
    """
    user_id = _norm_niu(user_id)
    email = _norm_email(email)

    p = _read_perfil(user_id)
    if not p:
        # no hacemos nada si no existe el perfil (esto es deliberado)
        return

    # completa campos mínimos
    p.setdefault("user_id", user_id)
    if not p.get("email"):
        p["email"] = email
    p.setdefault("niu", user_id)
    p.setdefault("nombre", p.get("nombre") or "")
    p.setdefault("grupo", p.get("grupo") if "grupo" in p else None)
    p.setdefault("curso", p.get("curso") if "curso" in p else None)
    p.setdefault("es_admin", bool(p.get("es_admin", False)))
    p.setdefault("eliminado", bool(p.get("eliminado", False)))

    _recalcula_completitud(p)
    _write_perfil(user_id, p)

    # índices
    idx = _load_index()
    by_email = idx["by_email"]
    by_niu = idx["by_niu"]
    if email:
        by_email[email] = user_id
        idx["permitidos"].setdefault(email, True)
    by_niu[user_id] = p.get("email", email) or ""
    _save_index(idx)

def ensure_profile_links(user_id: str, email: str) -> None:
    """
    Igual que la anterior, pero si el perfil NO existe, lo crea con estructura mínima.
    """
    user_id = _norm_niu(user_id)
    email = _norm_email(email)

    p = _read_perfil(user_id) or {}
    p.setdefault("user_id", user_id)
    p.setdefault("email", email)
    p.setdefault("niu", user_id)
    p.setdefault("nombre", p.get("nombre") or "")
    p.setdefault("grupo", p.get("grupo") if "grupo" in p else None)
    p.setdefault("curso", p.get("curso") if "curso" in p else None)
    p.setdefault("es_admin", bool(p.get("es_admin", False)))
    p.setdefault("eliminado", False)

    _recalcula_completitud(p)
    _write_perfil(user_id, p)

    idx = _load_index()
    idx["by_email"][p["email"]] = user_id
    idx["by_niu"][user_id] = p["email"]
    idx["permitidos"].setdefault(p["email"], True)
    _save_index(idx)

def update_perfil_fields(user_id: str, nuevos_campos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mezcla y guarda cambios en el perfil (sin validar reglas de negocio aquí).
    """
    user_id = _norm_niu(user_id)
    p = _read_perfil(user_id) or {}
    p.update(nuevos_campos or {})
    p.setdefault("user_id", user_id)
    p.setdefault("niu", user_id)
    p.setdefault("email", p.get("email") or "")
    p.setdefault("eliminado", False)
    _recalcula_completitud(p)
    _write_perfil(user_id, p)

    # mantener índices coherentes si cambió email
    idx = _load_index()
    if p.get("email"):
        idx["by_email"][p["email"]] = user_id
        idx["by_niu"][user_id] = p["email"]
        idx["permitidos"].setdefault(p["email"], True)
        _save_index(idx)

    return p

def set_niu_if_unique(user_id: str, nuevo_niu: str) -> bool:
    """
    Intenta fijar NIU si es único.
    NOTA: en este proyecto el user_id == NIU. Por simplicidad,
    solo permitimos actualizar p["niu"] si coincide con el user_id.
    Si alguien intentase cambiar a un NIU diferente, devolvemos False.
    """
    user_id = _norm_niu(user_id)
    nuevo_niu = _norm_niu(nuevo_niu)
    if not nuevo_niu:
        return False
    if nuevo_niu != user_id:
        # Cambio de 'user_id' no soportado aquí.
        return False

    p = _read_perfil(user_id) or {}
    p["niu"] = user_id
    _recalcula_completitud(p)
    _write_perfil(user_id, p)
    return True

# -------------------- Bootstrap / creación --------------------
def bootstrap_first_admin_from_email(email: str) -> str:
    """
    Si no hay usuarios, crea el primero como admin a partir del email.
    user_id = parte local del email (antes de @).
    """
    if has_any_user(include_eliminados=False):
        raise ValueError("Ya existe al menos un usuario")

    email = _norm_email(email)
    if "@" not in email:
        raise ValueError("Email inválido para bootstrap")
    user_id = _norm_niu(email.split("@", 1)[0])

    # perfil mínimo
    p = {
        "user_id": user_id,
        "email": email,
        "niu": user_id,
        "nombre": "",
        "grupo": None,
        "curso": None,
        "es_admin": True,
        "eliminado": False,
    }
    _recalcula_completitud(p)
    _write_perfil(user_id, p)

    idx = _load_index()
    idx["by_email"][email] = user_id
    idx["by_niu"][user_id] = email
    idx["permitidos"][email] = True
    _save_index(idx)
    return user_id

def get_or_create_user_by_email(email: str) -> str:
    """
    Devuelve el user_id asociado al email, o lo crea si no existe (perfil mínimo).
    Solo usado en endpoints de dev/repair.
    """
    email = _norm_email(email)
    idx = _load_index()
    uid = idx["by_email"].get(email)
    if uid:
        return uid

    # derivamos user_id de la parte local del email
    if "@" not in email:
        raise ValueError("Email inválido")
    uid = _norm_niu(email.split("@", 1)[0])

    # crea perfil mínimo
    p = {
        "user_id": uid,
        "email": email,
        "niu": uid,
        "nombre": "",
        "grupo": None,
        "curso": None,
        "es_admin": False,
        "eliminado": False,
    }
    _recalcula_completitud(p)
    _write_perfil(uid, p)

    # índices
    idx["by_email"][email] = uid
    idx["by_niu"][uid] = email
    idx["permitidos"].setdefault(email, True)
    _save_index(idx)

    return uid
