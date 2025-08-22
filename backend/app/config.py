from pydantic_settings import BaseSettings
from pydantic import Field, EmailStr, field_validator
from typing import List
import os

class Settings(BaseSettings):
    app_name: str = Field(default="Panel Votaciones y Asistencia")
    tz: str = Field(default="Europe/Madrid")
    data_dir: str = Field(default="Datos")
    dev_mode: bool = Field(default=True)

    # SMTP
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    admin_emails: List[EmailStr] = Field(default_factory=list)

    # OTP
    otp_length: int = Field(default=6)
    otp_ttl_seconds: int = Field(default=600)
    otp_rate_limit_seconds: int = Field(default=30)
    otp_max_attempts: int = Field(default=5)

    # Auth (Fase 2)
    auth_secret: str = Field(default="dev-secret-cambia-esto")
    auth_token_ttl_seconds: int = Field(default=86400)  # 24h

    @field_validator("admin_emails", mode="before")
    @classmethod
    def split_admin_emails(cls, v):
        if isinstance(v, list):
            return v
        if not v:
            return []
        return [e.strip() for e in str(v).split(",") if e.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
settings.data_dir = os.path.abspath(settings.data_dir)
