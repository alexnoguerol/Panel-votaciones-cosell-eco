from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr, RootModel

from ..deps.auth import require_admin, UserCtx
from ..repo import ajustes as ajustes_repo
from ..utils.audit import audit_event

router = APIRouter(prefix="/ajustes", tags=["ajustes"])

# ---------------------------
# Modelos
# ---------------------------
class DomainsIn(BaseModel):
    dominios: List[str] = Field(default_factory=list)

class DomainsOut(BaseModel):
    allowed_domains: List[str] = Field(default_factory=list)

class SMTPIn(BaseModel):
    provider: Literal["gmail", "outlook", "custom"] = Field(
        description="gmail | outlook | custom"
    )
    email: EmailStr
    app_password: Optional[str] = Field(default=None, description="Contraseña de aplicación")
    from_email: Optional[EmailStr] = Field(default=None)
    # Solo para 'custom'
    host: Optional[str] = None
    port: Optional[int] = None
    use_starttls: Optional[bool] = None

class SMTPOut(BaseModel):
    provider: Literal["gmail", "outlook", "custom"]
    email: EmailStr
    from_email: EmailStr
    host: str
    port: int
    use_starttls: bool
    has_app_password: bool

class PerfilDefaultsIn(BaseModel):
    grupo: Optional[str] = None
    curso: Optional[str] = None

class PerfilDefaultsOut(BaseModel):
    defaults: Dict[str, Any]

# Pydantic v2: usar RootModel en vez de __root__
class PerfilReglasIn(RootModel[Dict[str, Dict[str, Any]]]):
    pass

class PerfilReglasOut(BaseModel):
    reglas: Dict[str, Dict[str, Any]]

class ThemingIn(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    topbar: Optional[str] = None
    accent: Optional[str] = None

class NotificationsIn(BaseModel):
    admin_emails: Optional[List[EmailStr]] = None
    recordatorios: Optional[Dict[str, Any]] = None

class GeneralIn(BaseModel):
    timezone: Optional[str] = None
    otp: Optional[Dict[str, int]] = None
    retention: Optional[Dict[str, int]] = None
    auto_export: Optional[Dict[str, bool]] = None

# ---------------------------
# Dominios
# ---------------------------
@router.get("/domains", response_model=DomainsOut)
def get_allowed_domains():
    doms = ajustes_repo.get_allowed_domains()
    return DomainsOut(allowed_domains=doms or [])

@router.put("/domains", response_model=DomainsOut)
def set_allowed_domains(body: DomainsIn, user: UserCtx = Depends(require_admin), request: Request = None):
    clean: List[str] = []
    for d in body.dominios:
        d = (d or "").strip().lower()
        if d.startswith("@"):
            d = d[1:]
        if d:
            clean.append(d)
    out = ajustes_repo.set_allowed_domains(clean)
    audit_event("ajustes_domains_update", actor_user_id=user.user_id, actor_email=user.email, request=request, details={"count": len(out)})
    return DomainsOut(allowed_domains=out)

# ---------------------------
# SMTP
# ---------------------------
@router.get("/smtp", response_model=SMTPOut)
def get_smtp(user: UserCtx = Depends(require_admin)):
    pub = ajustes_repo.get_smtp_public()
    return SMTPOut(
        provider=pub["provider"],  # type: ignore[arg-type]
        email=pub["email"],
        from_email=pub["from"],
        host=pub["host"],
        port=pub["port"],
        use_starttls=pub["use_starttls"],
        has_app_password=pub["has_app_password"],
    )

@router.put("/smtp", response_model=SMTPOut)
def set_smtp(body: SMTPIn, user: UserCtx = Depends(require_admin), request: Request = None):
    cfg = {
        "provider": body.provider,
        "email": str(body.email),
        "from": str(body.from_email or body.email),
    }
    if body.provider == "custom":
        if not body.host or not body.port:
            raise HTTPException(status_code=400, detail="Para 'custom' indica host y port.")
        cfg["host"] = body.host
        cfg["port"] = int(body.port)
        cfg["use_starttls"] = bool(True if body.use_starttls is None else body.use_starttls)
    if body.app_password:
        cfg["app_password"] = body.app_password
    pub = ajustes_repo.set_smtp(cfg)
    audit_event("ajustes_smtp_update", actor_user_id=user.user_id, actor_email=user.email, request=request, details={"provider": pub["provider"]})
    return SMTPOut(
        provider=pub["provider"],  # type: ignore[arg-type]
        email=pub["email"],
        from_email=pub["from"],
        host=pub["host"],
        port=pub["port"],
        use_starttls=pub["use_starttls"],
        has_app_password=pub["has_app_password"],
    )

@router.post("/smtp/test")
async def smtp_test(to: EmailStr, user: UserCtx = Depends(require_admin), request: Request = None):
    from ..emailer import send_test_email
    await send_test_email(str(to))
    audit_event("ajustes_smtp_test", actor_user_id=user.user_id, actor_email=user.email, request=request, details={"to": str(to)})
    return {"ok": True, "sent_to": str(to)}

# ---------------------------
# Perfil: defaults y reglas
# ---------------------------
@router.get("/perfil/defaults", response_model=PerfilDefaultsOut)
def get_perfil_defaults():
    data = ajustes_repo.get_profile_defaults() or {}
    return PerfilDefaultsOut(defaults=data)

@router.patch("/perfil/defaults", response_model=PerfilDefaultsOut)
def patch_perfil_defaults(body: PerfilDefaultsIn, user: UserCtx = Depends(require_admin), request: Request = None):
    current = ajustes_repo.get_profile_defaults() or {}
    if body.grupo is not None:
        current["grupo"] = body.grupo
    if body.curso is not None:
        current["curso"] = body.curso
    out = ajustes_repo.set_profile_defaults(current)
    audit_event("ajustes_perfil_defaults_update", actor_user_id=user.user_id, actor_email=user.email, request=request)
    return PerfilDefaultsOut(defaults=out)

@router.get("/perfil/reglas", response_model=PerfilReglasOut)
def get_perfil_reglas():
    return PerfilReglasOut(reglas=ajustes_repo.get_perfil_reglas())

@router.put("/perfil/reglas", response_model=PerfilReglasOut)
def put_perfil_reglas(body: PerfilReglasIn, user: UserCtx = Depends(require_admin), request: Request = None):
    out = ajustes_repo.set_perfil_reglas(body.root or {})  # RootModel en v2
    audit_event("ajustes_perfil_reglas_update", actor_user_id=user.user_id, actor_email=user.email, request=request, details={"campos": list(out.keys())})
    return PerfilReglasOut(reglas=out)

# ---------------------------
# Theming
# ---------------------------
@router.get("/theming")
def get_theming():
    return ajustes_repo.get_theming()

@router.patch("/theming")
def patch_theming(body: ThemingIn, user: UserCtx = Depends(require_admin), request: Request = None):
    merged = {}
    for k in ("primary", "secondary", "topbar", "accent"):
        v = getattr(body, k)
        if v is not None:
            merged[k] = v
    out = ajustes_repo.set_theming(merged)
    audit_event("ajustes_theming_update", actor_user_id=user.user_id, actor_email=user.email, request=request)
    return out

# ---------------------------
# Logo
# ---------------------------
@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), user: UserCtx = Depends(require_admin), request: Request = None):
    content = await file.read()
    ajustes_repo.save_logo(content)
    audit_event("ajustes_logo_upload", actor_user_id=user.user_id, actor_email=user.email, request=request, details={"filename": file.filename})
    return {"ok": True}

@router.get("/logo")
def get_logo():
    path = ajustes_repo.get_logo_path()
    if not path:
        raise HTTPException(status_code=404, detail="No hay logo")
    return FileResponse(path, media_type="image/png")

@router.delete("/logo")
def delete_logo(user: UserCtx = Depends(require_admin), request: Request = None):
    ok = ajustes_repo.delete_logo()
    if ok:
        audit_event("ajustes_logo_delete", actor_user_id=user.user_id, actor_email=user.email, request=request)
    return {"ok": ok}

# ---------------------------
# Notificaciones
# ---------------------------
@router.get("/notifications")
def get_notifications():
    return ajustes_repo.get_notifications()

@router.patch("/notifications")
def patch_notifications(body: NotificationsIn, user: UserCtx = Depends(require_admin), request: Request = None):
    cfg: Dict[str, Any] = {}
    if body.admin_emails is not None:
        cfg["admin_emails"] = [str(e) for e in body.admin_emails]
    if body.recordatorios is not None:
        cfg["recordatorios"] = body.recordatorios
    out = ajustes_repo.set_notifications(cfg)
    audit_event("ajustes_notifications_update", actor_user_id=user.user_id, actor_email=user.email, request=request)
    return out

# ---------------------------
# General
# ---------------------------
@router.get("/general")
def get_general():
    return ajustes_repo.get_general()

@router.patch("/general")
def patch_general(body: GeneralIn, user: UserCtx = Depends(require_admin), request: Request = None):
    merged: Dict[str, Any] = {}
    if body.timezone is not None:
        merged["timezone"] = body.timezone
    if body.otp is not None:
        merged["otp"] = body.otp
    if body.retention is not None:
        merged["retention"] = body.retention
    if body.auto_export is not None:
        merged["auto_export"] = body.auto_export
    out = ajustes_repo.set_general(merged)
    audit_event("ajustes_general_update", actor_user_id=user.user_id, actor_email=user.email, request=request)
    return out
