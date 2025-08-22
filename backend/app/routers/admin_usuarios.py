from __future__ import annotations
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field

from ..deps.auth import get_current_user, UserCtx
from ..repo import usuarios as usuarios_repo
from ..repo import admin_usuarios as repo

router = APIRouter(prefix="/admin/usuarios", tags=["admin:usuarios"])

# ---------- helpers ----------
def _require_admin(user: UserCtx):
    perfil = usuarios_repo.get_perfil(user.user_id)
    if not bool(perfil.get("es_admin")):
        raise HTTPException(status_code=403, detail="Solo administradores")

# ---------- modelos ----------
class AltaUsuarioIn(BaseModel):
    email: EmailStr
    niu: str = Field(min_length=3, max_length=50)
    nombre: str = Field(min_length=2, max_length=120)
    grupo: Optional[str] = None
    curso: Optional[str] = None
    es_admin: Optional[bool] = None

class EditUsuarioIn(BaseModel):
    nombre: Optional[str] = None
    grupo: Optional[str] = None
    curso: Optional[str] = None
    es_admin: Optional[bool] = None

class ImportCSVIn(BaseModel):
    csv: str

# ---------- endpoints ----------
@router.get("")
async def listar(
    q: Optional[str] = None,
    grupo: Optional[str] = None,
    curso: Optional[str] = None,
    es_admin: Optional[bool] = None,
    eliminado: Optional[bool] = None,
    user: UserCtx = Depends(get_current_user),
):
    _require_admin(user)
    return {
        "items": repo.listar(query=q, grupo=grupo, curso=curso, es_admin=es_admin, eliminado=eliminado)
    }

@router.post("")
async def alta(body: AltaUsuarioIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        p = repo.alta_o_actualiza(
            email=body.email,
            niu=body.niu,
            nombre=body.nombre,
            grupo=body.grupo,
            curso=body.curso,
            es_admin=body.es_admin,
            marcar_permitido=True,
        )
        return {"ok": True, "perfil": p}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{user_id}")
async def editar(user_id: str, body: EditUsuarioIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        p = repo.editar(user_id.strip(), body.model_dump(exclude_none=True, exclude_unset=True))
        return {"ok": True, "perfil": p}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{user_id}/rol")
async def set_rol(user_id: str, es_admin: bool, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        p = repo.set_admin(user_id.strip(), bool(es_admin))
        return {"ok": True, "perfil": p}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}")
async def baja(user_id: str, undo: bool = False, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        p = repo.baja_logica(user_id.strip(), undo=undo)
        return {"ok": True, "perfil": p}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/export.csv")
async def export_csv(user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    csv_str = repo.export_csv()
    return Response(
        content=csv_str,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="usuarios.csv"'}
    )

@router.post("/import-csv")
async def import_csv(body: ImportCSVIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        res = repo.import_csv_text(body.csv)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
