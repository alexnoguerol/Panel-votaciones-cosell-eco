from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps.auth import get_current_user, UserCtx
from ..repo import usuarios as usuarios_repo
from backend.app.repo import asistencia as asistencia_repo
from backend.app.repo import solicitudes as solicitudes_repo

router = APIRouter(prefix="/asistencia", tags=["asistencia"])

# ---------- MODELOS ----------
class NuevaActividadIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=160)
    inicio_iso: str
    fin_iso: str
    lugar: str | None = Field(default=None, max_length=160)
    registro_automatico: bool = True

class ActividadOut(BaseModel):
    id: str
    titulo: str
    inicio_iso: str
    fin_iso: str
    inicio_ts: int
    fin_ts: int
    lugar: str | None
    registro_automatico: bool
    codigo: str | None = None
    estado: str

class CheckInCodigoIn(BaseModel):
    actividad_id: str
    codigo: str = Field(min_length=6, max_length=6)


class CheckOutIn(BaseModel):
    actividad_id: str

class EditActividadIn(BaseModel):
    titulo: Optional[str] = None
    inicio_iso: Optional[str] = None
    fin_iso: Optional[str] = None
    lugar: Optional[str] = Field(default=None, max_length=160)
    registro_automatico: Optional[bool] = None

class EliminarParticipanteIn(BaseModel):
    user_id: str
    eliminar: bool = True
    motivo: Optional[str] = Field(default="", max_length=240)


class TimeAdjustIn(BaseModel):
    user_id: str
    minutos: int


class ResolverSolicitudIn(BaseModel):
    estado: str
    comentario: Optional[str] = None

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
            registro_automatico=bool(body.registro_automatico),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return act

@router.get("/actividades", response_model=List[ActividadOut])
async def listar_actividades(_: UserCtx = Depends(get_current_user)):
    return asistencia_repo.listar_activas()

@router.get("/actividades/{actividad_id}", response_model=ActividadOut)
async def obtener_actividad(actividad_id: str, _: UserCtx = Depends(get_current_user)):
    try:
        return asistencia_repo.obtener_actividad(actividad_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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


@router.post("/actividades/{actividad_id}/cerrar", response_model=ActividadOut)
async def cerrar_actividad(actividad_id: str, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        act = asistencia_repo.cerrar_actividad(actividad_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return act


@router.delete("/actividades/{actividad_id}")
async def eliminar_actividad(actividad_id: str, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        asistencia_repo.eliminar_actividad(actividad_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

@router.post("/check-in")
async def check_in(body: CheckInCodigoIn, user: UserCtx = Depends(get_current_user)):
    try:
        return asistencia_repo.registrar_check_in_codigo(
            user.user_id, body.actividad_id.strip(), body.codigo.strip()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/check-out")
async def check_out(body: CheckOutIn, user: UserCtx = Depends(get_current_user)):
    try:
        return asistencia_repo.registrar_check(
            user_id=user.user_id,
            actividad_id=body.actividad_id.strip(),
            accion="out",
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


@router.get("/actividades/{actividad_id}/codigo")
async def obtener_codigo(actividad_id: str, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        codigo = asistencia_repo.obtener_codigo(actividad_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"codigo": codigo}


@router.get("/actividades/{actividad_id}/solicitudes")
async def solicitudes_actividad(actividad_id: str, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    return {"items": solicitudes_repo.listar_por_actividad(actividad_id.strip())}


@router.post("/actividades/{actividad_id}/solicitudes/{sol_id}/resolver")
async def resolver_solicitud(actividad_id: str, sol_id: str, body: ResolverSolicitudIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        rec = solicitudes_repo.resolver(
            sol_id.strip(), body.estado, user.user_id, body.comentario
        )
        if rec.get("estado") == "aceptada" and rec.get("tipo") == "asistencia":
            asistencia_repo.registrar_check(
                user_id=rec.get("user_id"),
                actividad_id=rec.get("actividad_id"),
                accion=rec.get("accion", "in"),
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "solicitud": rec}

@router.post("/actividades/{actividad_id}/time")
async def ajustar_tiempo_endpoint(actividad_id: str, body: TimeAdjustIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        participante = asistencia_repo.ajustar_tiempo(
            actividad_id.strip(), body.user_id.strip(), int(body.minutos)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "participante": participante}

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

