from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field

from ..repo import solicitudes as solicitudes_repo
from ..repo import ajustes as ajustes_repo
from ..utils.ratelimit import limit_by_ip, limit_by_key
from ..utils.audit import audit_event
from ..emailer import send_email

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


class SolicitudAltaIn(BaseModel):
    email: EmailStr
    nombre: Optional[str] = Field(default=None)
    niu: Optional[str] = Field(default=None)
    mensaje: Optional[str] = Field(default=None)


def _clean(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v if v else None


@router.post("/alta")
async def solicitar_alta(body: SolicitudAltaIn, request: Request):
    """Permite que un usuario solicite su alta en el sistema."""
    email = body.email.strip().lower()

    # Rate-limit por IP y por email para evitar abuso
    limit_by_ip(request, scope="solicitud_alta", limit=5, window_s=60)
    limit_by_key(email, scope="solicitud_alta", limit=5, window_s=60)

    payload = {
        "email": email,
        "nombre": _clean(body.nombre),
        "niu": _clean(body.niu),
        "mensaje": _clean(body.mensaje),
    }

    sol_id = solicitudes_repo.crear_solicitud_alta(payload)

    # Notificar a administradores (si hay)
    try:
        admin_emails = ajustes_repo.get_admin_emails()
        if admin_emails:
            texto = (
                "Nueva solicitud de alta:\n"
                f"Email: {email}\n"
                f"Nombre: {payload['nombre'] or ''}\n"
                f"NIU: {payload['niu'] or ''}\n"
                f"Mensaje: {payload['mensaje'] or ''}"
            )
            for adm in admin_emails:
                asyncio.create_task(send_email(adm, "Nueva solicitud de alta", texto))
    except Exception:
        pass

    audit_event("solicitud_alta_creada", actor_email=email, request=request, details=payload)

    return {"ok": True, "solicitud_id": sol_id}

