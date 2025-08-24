from __future__ import annotations

from typing import Optional, Dict
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
    # Todos los campos son opcionales: solo se tocan los que lleguen con valor no-nulo
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


def _cargar_reglas_perfil() -> Dict[str, Dict[str, str]]:
    """
    Intenta cargar reglas de edición desde ajustes_repo.
    Si no existen, aplica defaults razonables:
      - nombre/grupo/curso: libre
      - niu: aprobación (según comentario del esquema)
    El formato esperado es: { campo: {"edicion": "libre|aprobacion|bloqueado"} }
    """
    reglas: Dict[str, Dict[str, str]] = {}
    # Intentos de compatibilidad con distintas implementaciones del repo de ajustes
    getter = getattr(ajustes_repo, "get_reglas_perfil", None)
    if callable(getter):
        reglas = getter() or {}
    else:
        getter2 = getattr(ajustes_repo, "get", None)
        if callable(getter2):
            # prueba varias claves comunes
            for key in ("perfil.reglas", "reglas_perfil", "perfil_edicion"):
                try:
                    reglas = getter2(key) or {}
                    if reglas:
                        break
                except Exception:
                    pass

    defaults = {
        "nombre": {"edicion": "libre"},
        "grupo": {"edicion": "libre"},
        "curso": {"edicion": "libre"},
        "niu": {"edicion": "aprobacion"},
    }
    # Mezcla: lo que falte en reglas se completa con defaults
    for k, v in defaults.items():
        reglas.setdefault(k, v)
        reglas[k].setdefault("edicion", v["edicion"])
    return reglas


# --------- Endpoints ---------
@router.get("/perfil")
async def get_perfil(user: UserCtx = Depends(get_current_user)):
    """
    Devuelve el perfil del usuario autenticado.
    """
    perfil = usuarios_repo.get_perfil(user.user_id) or {}
    return {"ok": True, "perfil": perfil}


@router.patch("/perfil")
async def actualizar_perfil(body: PerfilUpdateIn, user: UserCtx = Depends(get_current_user)):
    """
    Actualiza campos del perfil según reglas de edición:
      - libre: se aplica directamente
      - aprobacion: se crea solicitud y queda pendiente
      - bloqueado (o desconocido): no se permite
    Solo se procesan campos enviados con valor no-nulo (tras trim).
    """
    reglas = _cargar_reglas_perfil()

    # Normaliza entrada
    entrada = {
        "nombre": _normaliza_val(body.nombre),
        "grupo": _normaliza_val(body.grupo),
        "curso": _normaliza_val(body.curso),
        "niu": _normaliza_val(body.niu),
    }

    # Estado inicial
    pendientes: list[str] = []
    bloqueados: list[str] = []
    cambios: Dict[str, str] = {}

    perfil_antes = usuarios_repo.get_perfil(user.user_id) or {}

    # Decide por campo
    for campo, nuevo_valor in entrada.items():
        if nuevo_valor is None:
            continue  # no cambiar este campo

        # Ignora campos que no cambian realmente
        if perfil_antes.get(campo) == nuevo_valor:
            continue

        conf = reglas.get(campo, {})
        ed = str(conf.get("edicion", "bloqueado")).lower()

        if ed == "libre":
            cambios[campo] = nuevo_valor
        elif ed == "aprobacion":
            pendientes.append(campo)
        else:
            bloqueados.append(campo)

    # Aplica cambios directos
    perfil_despues = perfil_antes
    if cambios:
        perfil_despues = usuarios_repo.update_perfil_fields(user.user_id, cambios)

    # Crea solicitud para pendientes (si el flujo existe)
    if pendientes:
        diff = {campo: entrada[campo] for campo in pendientes}
        try:
            solicitudes_repo.crear_solicitud_mod_perfil(user.user_id, user.email, diff)
        except AttributeError:
            # El repo de solicitudes no implementa el método: registra en auditoría pero no rompas.
            audit_event(
                "solicitud_repo_missing",
                actor_user_id=user.user_id,
                actor_email=user.email,
                details={"diff": diff},
            )

    # Auditoría
    audit_event(
        "perfil_update_attempt",
        actor_user_id=user.user_id,
        actor_email=user.email,
        details={
            "aplicados": list(cambios.keys()),
            "pendientes": pendientes,
            "bloqueados": bloqueados,
        },
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
    Exporta tus datos personales (perfil + asistencias + votos, etc.) a un JSON.
    Devuelve la ruta del fichero generado.
    """
    try:
        path = write_user_export(user.user_id)
    except Exception as e:
        audit_event("rgpd_export_failed", actor_user_id=user.user_id, actor_email=user.email, details={"error": str(e)})
        raise HTTPException(status_code=500, detail="No se pudo generar la exportación de datos.")
    else:
        audit_event("rgpd_export_requested", actor_user_id=user.user_id, actor_email=user.email)
        return {"ok": True, "file": path}
