from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import DATA_DIR, ensure_dir, read_json, write_json

# ============
# Rutas / FS
# ============
AJ_DIR = DATA_DIR / "ajustes"
ensure_dir(AJ_DIR)

F_DOMINIOS        = AJ_DIR / "dominios.json"         # { "permitidos": ["uab.cat", ...] }
F_SMTP            = AJ_DIR / "smtp.json"             # { "provider":"gmail|outlook|custom", "email":"", "app_password":"...", "from":"", "host":"", "port":587, "use_starttls":true }
F_THEMING         = AJ_DIR / "theming.json"          # { "primary":"#...", "secondary":"#...", "accent":"#..." }
F_PERFIL_REGLAS   = AJ_DIR / "perfil_campos.json"    # reglas por campo (edicion/obligatorio/activo)
F_PERFIL_DEFAULTS = AJ_DIR / "perfil_defaults.json"  # { "grupo": "...", "curso": "..." }
F_NOTIFS          = AJ_DIR / "notificaciones.json"   # { "admin_emails": [...], "recordatorios": {...} }
F_GENERAL         = AJ_DIR / "general.json"          # ver get_general() abajo
F_LOGO            = AJ_DIR / "logo.png"              # binario

# ==============================
# Dominios permitidos (login)
# ==============================
def get_allowed_domains() -> List[str]:
    data = read_json(F_DOMINIOS, default={"permitidos": []}) or {}
    doms = []
    for d in data.get("permitidos", []):
        if isinstance(d, str) and d.strip():
            doms.append(d.strip().lower().lstrip("@"))
    return sorted(set(doms))

def set_allowed_domains(domains: List[str]) -> List[str]:
    clean = []
    for d in (domains or []):
        if isinstance(d, str) and d.strip():
            clean.append(d.strip().lower().lstrip("@"))
    clean = sorted(set(clean))
    write_json(F_DOMINIOS, {"permitidos": clean})
    return list(clean)

# ============
# SMTP (simplificado: gmail | outlook | custom)
# ============
def _smtp_defaults() -> Dict[str, Any]:
    return {
        "provider": "gmail",   # "gmail" | "outlook" | "custom"
        "email": "",
        "app_password": "",    # se guarda en disco; en GET público devolvemos has_app_password
        "from": "",
        "host": "",            # solo para "custom"
        "port": 587,
        "use_starttls": True,
    }

def _smtp_runtime_from(cfg: Dict[str, Any]) -> Dict[str, Any]:
    prov = (cfg.get("provider") or "gmail").lower()
    email = (cfg.get("email") or "").strip()
    app_password = cfg.get("app_password") or ""
    sender = (cfg.get("from") or email).strip()

    if prov == "gmail":
        host, port, use_starttls = "smtp.gmail.com", 587, True
    elif prov in ("outlook", "office365", "o365"):
        host, port, use_starttls = "smtp.office365.com", 587, True
    else:
        host = (cfg.get("host") or "").strip()
        port = int(cfg.get("port") or 587)
        use_starttls = bool(cfg.get("use_starttls", True))

    return {
        "provider": prov,
        "email": email,
        "username": email,
        "password": app_password,
        "from": sender,
        "host": host,
        "port": int(port),
        "use_starttls": bool(use_starttls),
    }

def get_smtp_public() -> Dict[str, Any]:
    """Devuelve configuración SMTP sin exponer la contraseña."""
    cfg = _smtp_defaults() | (read_json(F_SMTP, default={}) or {})
    run = _smtp_runtime_from(cfg)
    return {
        "provider": run["provider"],
        "email": run["email"],
        "from": run["from"],
        "host": run["host"],
        "port": run["port"],
        "use_starttls": run["use_starttls"],
        "has_app_password": bool(cfg.get("app_password")),
    }

def get_smtp_runtime() -> Dict[str, Any]:
    """Devuelve configuración completa para enviar (incluye password)."""
    cfg = _smtp_defaults() | (read_json(F_SMTP, default={}) or {})
    return _smtp_runtime_from(cfg)

def set_smtp(input_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cur = _smtp_defaults() | (read_json(F_SMTP, default={}) or {})
    # Campos admitidos
    for k in ("provider", "email", "from", "host", "port", "use_starttls"):
        if k in input_cfg:
            cur[k] = input_cfg[k]
    # Guardar password si viene (si no viene, conservar)
    if "app_password" in input_cfg and (input_cfg["app_password"] or "").strip():
        cur["app_password"] = str(input_cfg["app_password"])
    write_json(F_SMTP, cur)
    return get_smtp_public()

# ============
# Theming
# ============
def get_theming() -> Dict[str, str]:
    data = read_json(F_THEMING, default={"primary": "#0ea5e9", "secondary": "#64748b", "accent": "#22c55e"}) or {}
    return {
        "primary": str(data.get("primary", "#0ea5e9")),
        "secondary": str(data.get("secondary", "#64748b")),
        "accent": str(data.get("accent", "#22c55e")),
    }

def set_theming(colors: Dict[str, str]) -> Dict[str, str]:
    cur = get_theming()
    for k in ("primary", "secondary", "accent"):
        v = colors.get(k)
        if isinstance(v, str) and v.strip():
            cur[k] = v.strip()
    write_json(F_THEMING, cur)
    return cur

# ===================================
# Reglas de campos de perfil
# ===================================
_DEF_REGLAS_ES: Dict[str, Dict[str, Any]] = {
    "nombre":   {"obligatorio": True,  "edicion": "libre",       "activo": True},
    "niu":      {"obligatorio": True,  "edicion": "aprobacion",  "activo": True},
    "email":    {"obligatorio": True,  "edicion": "bloqueado",   "activo": True},
    "grupo":    {"obligatorio": False, "edicion": "libre",       "activo": True},
    "curso":    {"obligatorio": False, "edicion": "libre",       "activo": True},
    "es_admin": {"obligatorio": False, "edicion": "bloqueado",   "activo": True},
}

def get_perfil_reglas() -> Dict[str, Dict[str, Any]]:
    data = read_json(F_PERFIL_REGLAS, default=_DEF_REGLAS_ES) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for campo, conf in (data.items() if isinstance(data, dict) else []):
        if not isinstance(conf, dict):
            conf = {}
        ed = str(conf.get("edicion", "bloqueado")).lower()
        out[campo] = {
            "obligatorio": bool(conf.get("obligatorio", False)),
            "edicion": ed if ed in ("libre", "aprobacion", "bloqueado") else "bloqueado",
            "activo": bool(conf.get("activo", True)),
        }
    for k, v in _DEF_REGLAS_ES.items():
        out.setdefault(k, v)
    return out

def set_perfil_reglas(reglas: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    cur = get_perfil_reglas()
    for campo, conf in (reglas or {}).items():
        if not isinstance(conf, dict):
            continue
        merged = {
            "obligatorio": bool(conf.get("obligatorio", cur.get(campo, {}).get("obligatorio", False))),
            "edicion": str(conf.get("edicion", cur.get(campo, {}).get("edicion", "bloqueado"))).lower(),
            "activo": bool(conf.get("activo", cur.get(campo, {}).get("activo", True))),
        }
        cur[campo] = merged
    write_json(F_PERFIL_REGLAS, cur)
    return get_perfil_reglas()

# ====================================
# Valores por defecto de perfil (UI)
# ====================================
def get_profile_defaults() -> Dict[str, Any]:
    data = read_json(F_PERFIL_DEFAULTS, default={"grupo": None, "curso": None}) or {}
    return {"grupo": data.get("grupo"), "curso": data.get("curso")}

def set_profile_defaults(values: Dict[str, Any]) -> Dict[str, Any]:
    cur = get_profile_defaults()
    if "grupo" in values: cur["grupo"] = values.get("grupo")
    if "curso" in values: cur["curso"] = values.get("curso")
    write_json(F_PERFIL_DEFAULTS, cur)
    return cur

# =================
# Notificaciones
# =================
def get_notifications() -> Dict[str, Any]:
    data = read_json(F_NOTIFS, default={"admin_emails": [], "recordatorios": {}}) or {}
    admins = []
    for e in data.get("admin_emails", []) or []:
        if isinstance(e, str) and e.strip():
            admins.append(e.strip().lower())
    return {
        "admin_emails": sorted(list(set(admins))),
        "recordatorios": data.get("recordatorios", {}) or {},
    }

def set_notifications(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cur = get_notifications()
    if "admin_emails" in cfg:
        emails = []
        for e in (cfg.get("admin_emails") or []):
            if isinstance(e, str) and e.strip():
                emails.append(e.strip().lower())
        cur["admin_emails"] = sorted(list(set(emails)))
    if "recordatorios" in cfg and isinstance(cfg["recordatorios"], dict):
        cur["recordatorios"] = cfg["recordatorios"]
    write_json(F_NOTIFS, cur)
    return cur

def get_admin_emails() -> List[str]:
    return get_notifications().get("admin_emails", [])

# =======================
# General (TZ / OTP / Retención / Auto-export)
# =======================
def get_general() -> Dict[str, Any]:
    data = read_json(
        F_GENERAL,
        default={
            "timezone": "Europe/Madrid",
            "otp": {"length": 6, "ttl_seconds": 600, "rate_limit_seconds": 60, "resend_window_seconds": 60},
            "retention": {"audit_days": 90, "backups_days": 30},
            "auto_export": {"usuarios_csv_daily": False, "backup_daily": True},
        },
    ) or {}
    otp = data.get("otp") or {}
    retention = data.get("retention") or {}
    auto_export = data.get("auto_export") or {}
    return {
        "timezone": str(data.get("timezone", "Europe/Madrid") or "Europe/Madrid"),
        "otp": {
            "length": int(otp.get("length", 6) or 6),
            "ttl_seconds": int(otp.get("ttl_seconds", 600) or 600),
            "rate_limit_seconds": int(otp.get("rate_limit_seconds", 60) or 60),
            "resend_window_seconds": int(otp.get("resend_window_seconds", 60) or 60),
        },
        "retention": {
            "audit_days": int(retention.get("audit_days", 90) or 90),
            "backups_days": int(retention.get("backups_days", 30) or 30),
        },
        "auto_export": {
            "usuarios_csv_daily": bool(auto_export.get("usuarios_csv_daily", False)),
            "backup_daily": bool(auto_export.get("backup_daily", True)),
        },
    }

def set_general(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cur = get_general()
    if "timezone" in cfg:
        tz = str(cfg.get("timezone") or "").strip() or "Europe/Madrid"
        cur["timezone"] = tz
    if "otp" in cfg and isinstance(cfg["otp"], dict):
        i = cfg["otp"]
        for k in ("length", "ttl_seconds", "rate_limit_seconds", "resend_window_seconds"):
            if k in i: cur["otp"][k] = int(i[k])
    if "retention" in cfg and isinstance(cfg["retention"], dict):
        r = cfg["retention"]
        for k in ("audit_days", "backups_days"):
            if k in r: cur["retention"][k] = int(r[k])
    if "auto_export" in cfg and isinstance(cfg["auto_export"], dict):
        a = cfg["auto_export"]
        for k in ("usuarios_csv_daily", "backup_daily"):
            if k in a: cur["auto_export"][k] = bool(a[k])
    write_json(F_GENERAL, cur)
    return cur

# =========
# Logo
# =========
def save_logo(content: bytes, suffix: str = ".png") -> Path:
    ensure_dir(AJ_DIR)
    # siempre guardamos como .png por simplicidad (si quieres, cambia por suffix)
    F_LOGO.write_bytes(content)
    return F_LOGO

def has_logo() -> bool:
    return F_LOGO.exists() and F_LOGO.is_file()

def get_logo_path() -> Optional[str]:
    return str(F_LOGO) if has_logo() else None

def delete_logo() -> bool:
    if has_logo():
        F_LOGO.unlink(missing_ok=True)
        return True
    return False
