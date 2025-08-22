from __future__ import annotations

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps.auth import get_current_user, UserCtx
from ..repo import usuarios as usuarios_repo
from ..repo import ajustes as ajustes_repo
from ..repo import solicitudes as solicitudes_repo
from ..repo.rgpd import write_user_export
from ..utils.audit import audit_event

router = APIRouter(prefix="/me", tags=["me"])


# --------- Schemas ---------
class PerfilUpdateIn(BaseModel):
    nombre: Optional[str] = Field(default=None)
    grupo: Optional[str] = Field(default=None)
    curso: Optional[str] = Field(default=None)
    niu: Optional[str] = Field(default=None)  # normalmente == user_id; puede requerir aprobación


# --------- Helpers ---------
def _normaliza_val(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v if v else None


# --------- Endpoints ---------
@router.get("/perfil")
async def get_perfil(user: UserCtx = Depends(get_current_user)):
    """
    Devuelve tu perfil y (opcionalmente) las reglas de campos configuradas.
    """
    perfil = usuarios_repo.get_perfil(user.user_id) or {}
    reglas = ajustes_repo.get_perfil_reglas() or {}
    return {"perfil": perfil, "reglas": reglas}


@router.post("/perfil/actualizar")
async def actualizar_perfil(body: PerfilUpdateIn, user: UserCtx = Depends(get_current_user)):
    """
    Aplica cambios de perfil respetando las reglas de edición:
      - edicion: "libre" -> se aplica directamente
      - edicion: "aprobacion" -> queda pendiente (no se aplica aquí)
      - edicion: "bloqueado" -> se ignora
    Reglas se leen de `ajustes.perfil_campos.json` (get_perfil_reglas).
    """
    cambios: Dict[str, Any] = {}
    pendientes: List[str] = []
    bloqueados: List[str] = []

    reglas = ajustes_repo.get_perfil_reglas() or {}
    entrada = {
        "nombre": _normaliza_val(body.nombre),
        "grupo": _normaliza_val(body.grupo),
        "curso": _normaliza_val(body.curso),
        "niu": _normaliza_val(body.niu),
    }

    for campo, nuevo_valor in entrada.items():
        if nuevo_valor is None:
            continue  # no cambiar
        conf = reglas.get(campo, {})
        ed = str(conf.get("edicion", "bloqueado")).lower()

        if ed == "libre":
            cambios[campo] = nuevo_valor
        elif ed == "aprobacion":
            pendientes.append(campo)
            # Aquí podrías crear una "solicitud de modificación" si ya tienes ese flujo.
            # De momento, solo lo marcamos como pendiente.
        else:
            bloqueados.append(campo)

    perfil_antes = usuarios_repo.get_perfil(user.user_id) or {}

    perfil_despues = perfil_antes
    if cambios:
        perfil_despues = usuarios_repo.update_perfil_fields(user.user_id, cambios)

    if pendientes:
        diff = {campo: entrada[campo] for campo in pendientes}
        solicitudes_repo.crear_solicitud_mod_perfil(user.user_id, user.email, diff)

    # Auditoría
    audit_event(
        "perfil_update_attempt",
        actor_user_id=user.user_id,
        actor_email=user.email,
        details={"aplicados": list(cambios.keys()), "pendientes": pendientes, "bloqueados": bloqueados},
    )

    return {
        "ok": True,
        "aplicados": list(cambios.keys()),
        "pendientes_aprobacion": pendientes,
        "bloqueados": bloqueados,
        "perfil": perfil_despues,
    }


@router.get("/export")
async def exportar_mis_datos(user: UserCtx = Depends(get_current_user)):
    """
    Exporta tus datos personales (perfil + asistencias + votos) a un JSON en `Datos/usuarios/`.
    """
    path = write_user_export(user.user_id)
    audit_event("rgpd_export_requested", actor_user_id=user.user_id, actor_email=user.email)
    return {"ok": True, "file": path}
