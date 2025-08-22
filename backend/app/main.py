from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .middleware.security import SecurityHeadersMiddleware
from .config import settings

from .routers import (
    auth as auth_router,
    me as me_router,
    asistencia as asistencia_router,
    votaciones as votaciones_router,
    ajustes as ajustes_router,
    admin_usuarios as admin_usuarios_router,
    admin_solicitudes as admin_solicitudes_router,
    solicitudes_public as solicitudes_router,
    dev as dev_router,
)
from .utils import backups

app = FastAPI(
    title="Panel de Votaciones y Asistencia",
    default_response_class=ORJSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS (ajusta orígenes si necesitas restringir)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cabeceras seguras (CSP, HSTS en prod, etc.)
app.add_middleware(
    SecurityHeadersMiddleware,
    dev_mode=bool(getattr(settings, "dev_mode", False)),
)

@app.on_event("startup")
async def _startup():
    # Programa backup diario si APScheduler está instalado (inofensivo si no)
    backups.start_scheduler()

# Routers
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(asistencia_router.router)
app.include_router(votaciones_router.router)
app.include_router(ajustes_router.router)
app.include_router(admin_usuarios_router.router)
app.include_router(admin_solicitudes_router.router)
app.include_router(solicitudes_router.router)
app.include_router(dev_router.router)
app.add_middleware(SecurityHeadersMiddleware, dev_mode=bool(getattr(settings, "dev_mode", False)))

@app.get("/health")
def health():
    return {"ok": True}