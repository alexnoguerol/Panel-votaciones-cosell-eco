from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps.auth import get_current_user, UserCtx
from ..repo import solicitudes as repo
from ..repo import usuarios as usuarios_repo

router = APIRouter(prefix="/admin/solicitudes", tags=["admin:solicitudes"])


def _require_admin(user: UserCtx):
    perfil = usuarios_repo.get_perfil(user.user_id)
    if not bool(perfil.get("es_admin")):
        raise HTTPException(status_code=403, detail="Solo administradores")


@router.get("")
async def listar(
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
    user: UserCtx = Depends(get_current_user),
):
    _require_admin(user)
    return {"items": repo.listar(estado=estado, tipo=tipo)}


class ResolverIn(BaseModel):
    estado: str
    comentario: Optional[str] = None


@router.post("/{sol_id}/resolver")
async def resolver(sol_id: str, body: ResolverIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        rec = repo.resolver(
            sol_id.strip(),
            estado=body.estado,
            admin_id=user.user_id,
            comentario=body.comentario,
        )
        return {"ok": True, "solicitud": rec}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps.auth import get_current_user, UserCtx
from ..repo import solicitudes as repo
from ..repo import usuarios as usuarios_repo

router = APIRouter(prefix="/admin/solicitudes", tags=["admin:solicitudes"])


def _require_admin(user: UserCtx):
    perfil = usuarios_repo.get_perfil(user.user_id)
    if not bool(perfil.get("es_admin")):
        raise HTTPException(status_code=403, detail="Solo administradores")


@router.get("")
async def listar(
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
    user: UserCtx = Depends(get_current_user),
):
    _require_admin(user)
    return {"items": repo.listar(estado=estado, tipo=tipo)}


class ResolverIn(BaseModel):
    estado: str
    comentario: Optional[str] = None


@router.post("/{sol_id}/resolver")
async def resolver(sol_id: str, body: ResolverIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        rec = repo.resolver(
            sol_id.strip(),
            estado=body.estado,
            admin_id=user.user_id,
            comentario=body.comentario,
        )
        return {"ok": True, "solicitud": rec}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))