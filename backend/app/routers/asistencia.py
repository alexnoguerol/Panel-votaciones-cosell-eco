from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps.auth import get_current_user, UserCtx
from ..repo import usuarios as usuarios_repo
from ..repo import asistencia as asistencia_repo

router = APIRouter(prefix="/asistencia", tags=["asistencia"])

# ---------- MODELOS ----------
class NuevaActividadIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=160)
    inicio_iso: str
    fin_iso: str
    lugar: str | None = Field(default=None, max_length=160)
    ventana_antes_min: int = 15
    ventana_despues_min: int = 15
    permite_fuera_de_hora: bool = False

class ActividadOut(BaseModel):
    id: str
    titulo: str
    inicio_iso: str
    fin_iso: str
    inicio_ts: int
    fin_ts: int
    lugar: str | None
    ventana_antes_min: int
    ventana_despues_min: int
    permite_fuera_de_hora: bool
    estado: str

class CheckInOutIn(BaseModel):
    actividad_id: str
    accion: str = Field(pattern="^(in|out)$")

class EditActividadIn(BaseModel):
    titulo: Optional[str] = None
    inicio_iso: Optional[str] = None
    fin_iso: Optional[str] = None
    lugar: Optional[str] = Field(default=None, max_length=160)
    ventana_antes_min: Optional[int] = None
    ventana_despues_min: Optional[int] = None
    permite_fuera_de_hora: Optional[bool] = None
    cerrar_ahora: Optional[bool] = False
    eliminar: Optional[bool] = None  # más intuitivo que "estado"

class AjusteTiempoIn(BaseModel):
    user_id: str
    # O bien indicas delta (±segundos), o bien fijas un total exacto:
    ajuste_segundos: Optional[int] = None
    total_segundos: Optional[int] = None
    motivo: Optional[str] = Field(default="", max_length=240)

class EliminarParticipanteIn(BaseModel):
    user_id: str
    eliminar: bool = True
    motivo: Optional[str] = Field(default="", max_length=240)

# ---------- HELPERS ----------
def _require_admin(user: UserCtx):
    perfil = usuarios_repo.get_perfil(user.user_id)
    if not bool(perfil.get("es_admin")):
        raise HTTPException(status_code=403, detail="Solo administradores")

# ---------- ENDPOINTS ----------
@router.post("/actividades", response_model=ActividadOut)
async def crear_actividad(body: NuevaActividadIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        act = asistencia_repo.crear_actividad(
            creador_id=user.user_id,
            titulo=body.titulo.strip(),
            inicio_iso=body.inicio_iso.strip(),
            fin_iso=body.fin_iso.strip(),
            lugar=(body.lugar or "").strip() or None,
            ventana_antes_min=int(body.ventana_antes_min),
            ventana_despues_min=int(body.ventana_despues_min),
            permite_fuera_de_hora=bool(body.permite_fuera_de_hora),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return act

@router.get("/actividades", response_model=List[ActividadOut])
async def listar_actividades(_: UserCtx = Depends(get_current_user)):
    return asistencia_repo.listar_activas()

@router.patch("/actividades/{actividad_id}", response_model=ActividadOut)
async def editar_actividad(actividad_id: str, body: EditActividadIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        # SOLO enviamos lo que el cliente mandó (sin defaults no enviados)
        cambios = body.model_dump(exclude_none=True, exclude_unset=True)
        act = asistencia_repo.editar_actividad(actividad_id.strip(), cambios)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return act

@router.post("/check")
async def check_in_out(body: CheckInOutIn, user: UserCtx = Depends(get_current_user)):
    try:
        return asistencia_repo.registrar_check(
            user_id=user.user_id,
            actividad_id=body.actividad_id.strip(),
            accion=body.accion.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mis-checkins")
async def mis_checkins(
    actividad_id: Optional[str] = Query(default=None),
    user: UserCtx = Depends(get_current_user),
):
    return asistencia_repo.mis_checkins(user.user_id, actividad_id)

@router.get("/actividades/{actividad_id}/participantes")
async def participantes(actividad_id: str, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    return asistencia_repo.participantes_de_actividad(actividad_id.strip())

@router.post("/actividades/{actividad_id}/ajuste-tiempo")
async def ajuste_tiempo(actividad_id: str, body: AjusteTiempoIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    if body.ajuste_segundos is None and body.total_segundos is None:
        raise HTTPException(status_code=400, detail="Indica 'ajuste_segundos' o 'total_segundos'")
    if body.total_segundos is not None:
        rec = asistencia_repo.set_total(
            actividad_id.strip(), body.user_id.strip(),
            int(body.total_segundos), body.motivo or "", user.user_id
        )
    else:
        rec = asistencia_repo.set_ajuste_delta(
            actividad_id.strip(), body.user_id.strip(),
            int(body.ajuste_segundos or 0), body.motivo or "", user.user_id
        )
    return {"ok": True, "ajuste": rec}

@router.post("/actividades/{actividad_id}/eliminar-participante")
async def eliminar_participante(actividad_id: str, body: EliminarParticipanteIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    rec = asistencia_repo.set_eliminado(
        actividad_id.strip(), body.user_id.strip(),
        bool(body.eliminar), body.motivo or "", user.user_id
    )
    estado = "eliminado" if body.eliminar else "restaurado"
    return {"ok": True, "estado": estado, "registro": rec}


# backend/app/routers/asistencia.py  (añadir al final del archivo)
from ..repo import exports as exports_repo
from fastapi import Response

@router.get("/{reunion_id}/export")
async def export_reunion(reunion_id: str, user: UserCtx = Depends(get_current_user)):
    # Si quieres que sea solo admin, usa aquí tu verificación de admin
    csv_path = exports_repo.export_asistencia_csv(reunion_id.strip())
    return {"ok": True, "csv": csv_path}