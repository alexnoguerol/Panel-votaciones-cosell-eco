from __future__ import annotations
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..deps.auth import get_current_user, UserCtx
from ..repo import usuarios as usuarios_repo
from ..repo import votaciones as repo

router = APIRouter(prefix="/votaciones", tags=["votaciones"])


# -------------------- Modelos --------------------
class NuevaVotacionIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=160)
    opciones: List[str] = Field(default_factory=list)
    inicio_iso: str
    fin_iso: str
    descripcion: Optional[str] = Field(default=None, max_length=400)
    permitir_cambiar: bool = False
    permite_fuera_de_hora: bool = False
    secreto: bool = True
    quorum_minimo: Optional[int] = None
    respuesta_abierta: bool = False
    respuesta_abierta_etiqueta: Optional[str] = None

class VotacionOut(BaseModel):
    id: str
    titulo: str
    descripcion: Optional[str]
    opciones: List[str]
    inicio_iso: str
    fin_iso: str
    inicio_ts: int
    fin_ts: int
    permitir_cambiar: bool
    permite_fuera_de_hora: bool
    secreto: bool
    quorum_minimo: Optional[int]
    respuesta_abierta: bool
    respuesta_abierta_etiqueta: Optional[str]
    estado: str

class EditVotacionIn(BaseModel):
    titulo: Optional[str] = None
    opciones: Optional[List[str]] = None
    inicio_iso: Optional[str] = None
    fin_iso: Optional[str] = None
    descripcion: Optional[str] = None
    permitir_cambiar: Optional[bool] = None
    permite_fuera_de_hora: Optional[bool] = None
    secreto: Optional[bool] = None
    quorum_minimo: Optional[int] = None
    cerrar_ahora: Optional[bool] = False
    eliminar: Optional[bool] = None
    respuesta_abierta: Optional[bool] = None
    respuesta_abierta_etiqueta: Optional[str] = None

class EmitirVotoIn(BaseModel):
    votacion_id: str
    opcion: Optional[str] = None
    texto_abierto: Optional[str] = None


# -------------------- Helpers --------------------
def _require_admin(user: UserCtx):
    perfil = usuarios_repo.get_perfil(user.user_id)
    if not bool(perfil.get("es_admin")):
        raise HTTPException(status_code=403, detail="Solo administradores")


# -------------------- Endpoints --------------------
@router.get("", response_model=List[VotacionOut])
async def listar(_: UserCtx = Depends(get_current_user)):
    return repo.listar_vigentes()

@router.post("", response_model=VotacionOut)
async def crear(body: NuevaVotacionIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        v = repo.crear_votacion(
            creador_id=user.user_id,
            titulo=body.titulo,
            opciones=body.opciones,
            inicio_iso=body.inicio_iso,
            fin_iso=body.fin_iso,
            descripcion=body.descripcion,
            permitir_cambiar=body.permitir_cambiar,
            permite_fuera_de_hora=body.permite_fuera_de_hora,
            secreto=body.secreto,
            quorum_minimo=body.quorum_minimo,
            respuesta_abierta=body.respuesta_abierta,
            respuesta_abierta_etiqueta=body.respuesta_abierta_etiqueta,
        )
        return v
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{votacion_id}", response_model=VotacionOut)
async def editar(votacion_id: str, body: EditVotacionIn, user: UserCtx = Depends(get_current_user)):
    _require_admin(user)
    try:
        cambios = body.model_dump(exclude_none=True, exclude_unset=True)
        v = repo.editar_votacion(votacion_id.strip(), cambios)
        return v
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/votar")
async def votar(body: EmitirVotoIn, user: UserCtx = Depends(get_current_user)):
    try:
        return repo.emitir_voto(
            user.user_id,
            body.votacion_id.strip(),
            opcion=(body.opcion.strip() if body.opcion else None),
            texto_abierto=(body.texto_abierto.strip() if body.texto_abierto else None),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{votacion_id}/resultados")
async def resultados(votacion_id: str, user: UserCtx = Depends(get_current_user)):
    # Si la votación es secreta, solo admins ven detalle; el resto, agregados.
    perfil = usuarios_repo.get_perfil(user.user_id)
    incluir_detalle = bool(perfil.get("es_admin"))
    try:
        return repo.resultados(votacion_id.strip(), incluir_detalle=incluir_detalle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mis")
async def mis_votos(user: UserCtx = Depends(get_current_user)):
    return repo.mis_votos(user.user_id)

# ---------- NUEVO: participación ----------
@router.get("/{votacion_id}/participacion")
async def participacion(votacion_id: str, user: UserCtx = Depends(get_current_user)):
    """
    Lista el último voto por usuario (si la votación es secreta, solo IDs y opción/texto;
    si no es secreta y eres admin, será lo mismo pero ya puedes exportar con detalle).
    """
    try:
        parts = repo.participantes(votacion_id.strip())
        # enriquecemos con perfil básico
        out = []
        for p in parts:
            perfil = usuarios_repo.get_perfil(p["user_id"])
            out.append({
                "user_id": p["user_id"],
                "email": perfil.get("email"),
                "nombre": perfil.get("nombre"),
                "opcion": p.get("opcion"),
                "texto_abierto": p.get("texto_abierto"),
                "ts": p.get("ts"),
            })
        return {"total": len(out), "items": out}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- NUEVO: export CSV ----------
@router.get("/{votacion_id}/export.csv")
async def export_csv(votacion_id: str, user: UserCtx = Depends(get_current_user)):
    """
    Exporta CSV:
    - Si la votación es NO secreta y eres admin -> detalle por usuario.
    - Si es secreta o no eres admin -> agregado.
    """
    perfil = usuarios_repo.get_perfil(user.user_id)
    incluir_detalle = bool(perfil.get("es_admin"))
    try:
        csv_str = repo.export_csv(votacion_id.strip(), incluir_detalle=incluir_detalle)
        return Response(
            content=csv_str,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="votacion_{votacion_id}.csv"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
# backend/app/routers/votaciones.py  (añadir al final del archivo)
from ..repo import exports as exports_repo

@router.get("/{votacion_id}/export")
async def export_votacion(votacion_id: str, user: UserCtx = Depends(get_current_user)):
    # Si quieres que sea solo admin, verifica rol aquí
    out = exports_repo.export_votacion_csv(votacion_id.strip())
    return {"ok": True, **out}



