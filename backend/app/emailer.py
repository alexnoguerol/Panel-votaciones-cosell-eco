from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Optional

from .repo import ajustes as ajustes_repo


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    cfg = ajustes_repo.get_smtp_runtime()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to_email
    msg.set_content(body)

    if cfg["use_starttls"]:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            if cfg["username"] and cfg["password"]:
                s.login(cfg["username"], cfg["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as s:
            if cfg["username"] and cfg["password"]:
                s.login(cfg["username"], cfg["password"])
            s.send_message(msg)


async def send_email(to_email: str, subject: str, body: str) -> None:
    await asyncio.to_thread(_send_email_sync, to_email, subject, body)


async def send_test_email(to_email: str) -> None:
    await send_email(to_email, "Prueba SMTP", "Este es un correo de prueba del Panel.")
