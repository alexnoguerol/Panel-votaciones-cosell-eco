from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from ..deps.auth import get_current_user, UserCtx
from ..config import settings
from ..emailer import send_test_email
from ..repo import usuarios as usuarios_repo
from ..utils import backups

router = APIRouter(prefix="/_dev", tags=["_dev"])

class TestEmailIn(BaseModel):
    to: EmailStr | None = None

@router.post("/test-email")
async def dev_test_email(body: TestEmailIn, user: UserCtx = Depends(get_current_user)):
    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="DEV_MODE desactivado")
    to = str(body.to or (settings.admin_emails[0] if settings.admin_emails else settings.smtp_username))
    await send_test_email(to)
    return {"sent_to": to}

class RepairUserIn(BaseModel):
    email: EmailStr

@router.post("/repair-user")
async def repair_user(body: RepairUserIn, user: UserCtx = Depends(get_current_user)):
    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="Solo disponible con DEV_MODE=true")
    email = body.email.strip().lower()
    user_id = usuarios_repo.get_or_create_user_by_email(email)
    usuarios_repo.ensure_profile_links(user_id, email)
    return usuarios_repo.get_perfil(user_id)

@router.post("/backup/now")
async def backup_now(user: UserCtx = Depends(get_current_user)):
    path = backups.create_backup_zip()
    return {"ok": True, "zip": path}
