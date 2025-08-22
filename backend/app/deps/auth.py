# backend/app/deps/auth.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..utils.tokens import verify as verify_token
from ..repo import usuarios as usuarios_repo

# <-- Esto hace que FastAPI registre el esquema Bearer en OpenAPI,
#     y Swagger muestre el botón "Authorize".
security = HTTPBearer(auto_error=False)


@dataclass
class UserCtx:
    user_id: str
    email: str
    is_admin: bool = False


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserCtx:
    """
    Valida el token Bearer del header Authorization y devuelve el contexto de usuario.
    """
    if credentials is None or (credentials.scheme or "").lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    ok, data = verify_token(token)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {data}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(data.get("sub") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin 'sub' o 'email'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    perfil = usuarios_repo.get_perfil(user_id) or {}
    is_admin = bool(perfil.get("es_admin", False))
    return UserCtx(user_id=user_id, email=email, is_admin=is_admin)


async def require_admin(user: UserCtx = Depends(get_current_user)) -> UserCtx:
    """
    Dependencia para endpoints de admin.
    """
    if not usuarios_repo.user_exists(user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no encontrado")
    perfil = usuarios_repo.get_perfil(user.user_id) or {}
    if not bool(perfil.get("es_admin", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso restringido a administradores")
    return user
