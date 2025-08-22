from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from ..deps.auth import UserCtx  # (solo para tipos; no es dependencia aquí)
from ..utils.tokens import create_token
from ..utils.ratelimit import limit_by_ip, limit_by_key
from ..utils.audit import audit_event
from ..config import settings
from ..repo import usuarios as usuarios_repo
from ..repo import ajustes as ajustes_repo
from ..repo import otps as otps_repo

router = APIRouter(prefix="/auth", tags=["auth"])


# --------- Schemas ---------
class OtpRequestIn(BaseModel):
    email: EmailStr


class OtpVerifyIn(BaseModel):
    email: EmailStr
    otp: str


# --------- Endpoints ---------
@router.post("/otp/request")
async def request_otp(body: OtpRequestIn, request: Request):
    """
    Solicita un OTP para login sin contraseña.
    Reglas:
      - Si hay lista de dominios y el dominio del email NO está en la lista -> 403.
      - Si no existe ningún usuario todavía -> bootstrap del primer admin con ese email.
      - Si ya hay usuarios: el email debe existir en el sistema -> 403 si no existe.
      - Rate limit por IP y por email para evitar abuso.
    """
    email = body.email.strip().lower()
    domain = email.split("@")[-1]

    # Rate-limit (p. ej. 5 peticiones/min por IP y 5/min por email)
    limit_by_ip(request, scope="otp_request", limit=5, window_s=60)
    limit_by_key(email, scope="otp_request", limit=5, window_s=60)

    # Dominio permitido
    allowed = ajustes_repo.get_allowed_domains()
    if allowed and domain not in allowed:
        audit_event("otp_request_denied_domain", actor_email=email, request=request, details={"domain": domain})
        raise HTTPException(status_code=403, detail="Dominio no permitido")

    # Bootstrap del primer usuario/admin si no hay ninguno
    if not usuarios_repo.has_any_user(include_eliminados=False):
        user_id = usuarios_repo.bootstrap_first_admin_from_email(email)
        usuarios_repo.ensure_profile_links(user_id, email)
    else:
        # Ya hay usuarios -> el email debe existir
        if not usuarios_repo.user_exists_by_email(email):
            audit_event("otp_request_denied_unknown_email", actor_email=email, request=request)
            raise HTTPException(status_code=403, detail="No estás dado de alta. Solicita acceso.")

    # Generar/registrar OTP (el repo gestiona TTL/rate interno)
    ok, msg = otps_repo.request(email=email)
    if not ok:
        audit_event("otp_request_failed", actor_email=email, request=request, details={"reason": msg})
        raise HTTPException(status_code=400, detail=msg)

    audit_event("otp_requested", actor_email=email, request=request)
    return {"ok": True, "message": msg}


@router.post("/otp/verify")
async def verify_otp(body: OtpVerifyIn, request: Request):
    """
    Verifica el OTP y emite un access_token.
    Mantiene coherencia con el flujo de request:
      - Requiere que el usuario exista (salvo bootstrap ya realizado).
      - Emite JWT HS256 con sub=user_id, email, iat/exp.
    """
    email = body.email.strip().lower()

    # (Leve) rate-limit de verificación por IP
    limit_by_ip(request, scope="otp_verify", limit=10, window_s=60)

    # El usuario debe existir (si hubo bootstrap ya se habrá creado)
    if not usuarios_repo.user_exists_by_email(email):
        audit_event("otp_verify_denied_unknown_email", actor_email=email, request=request)
        raise HTTPException(status_code=403, detail="No estás dado de alta. Solicita acceso.")

    # Verificar OTP
    ok, msg = otps_repo.verify(email=email, otp=body.otp.strip())
    if not ok:
        audit_event("otp_failed", actor_email=email, request=request)
        raise HTTPException(status_code=400, detail=msg)

    # Obtener user_id y asegurar enlaces básicos
    user_id = usuarios_repo.get_user_id_by_email(email)
    usuarios_repo.ensure_profile_links_if_exists(user_id, email)

    # Crear token
    token = create_token(sub=user_id, email=email, ttl_seconds=getattr(settings, "auth_token_ttl_seconds", 3600))

    audit_event("login_success", actor_user_id=user_id, actor_email=email, request=request)
    return {"verified": True, "message": msg, "access_token": token, "token_type": "bearer"}
