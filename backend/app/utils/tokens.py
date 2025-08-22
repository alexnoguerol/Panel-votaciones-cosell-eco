# backend/app/utils/tokens.py
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import time
from typing import Any, Dict, Tuple

from ..config import settings  # import relativo correcto


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("utf-8"))


def _get_secret_value() -> str:
    """
    Soporta ambas claves de settings:
      - settings.auth_secret_key (nueva)
      - settings.auth_secret     (antigua)
    Fallback seguro de desarrollo.
    """
    return (
        getattr(settings, "auth_secret_key", None)
        or getattr(settings, "auth_secret", None)
        or "dev-secret-change-me"
    )


def _sign(msg: bytes, secret: bytes) -> str:
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_token(
    sub: str,
    email: str,
    ttl_seconds: int | None = None,
    extra: Dict[str, Any] | None = None,
) -> str:
    """
    Crea un token tipo JWT (HS256) sin dependencias externas.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    ttl = int(ttl_seconds if ttl_seconds is not None else getattr(settings, "auth_token_ttl_seconds", 3600))
    payload: Dict[str, Any] = {
        "sub": sub,
        "email": (email or "").strip().lower(),
        "iat": now,
        "exp": now + ttl,
    }
    if extra:
        payload.update(extra)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    secret = _get_secret_value().encode("utf-8")
    signature_b64 = _sign(signing_input, secret)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify(token: str) -> Tuple[bool, Dict[str, Any] | str]:
    """
    Verifica firma y expiración. Devuelve (ok, payload | motivo).
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False, "formato inválido"
        header_b64, payload_b64, signature_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        secret = _get_secret_value().encode("utf-8")
        expected_sig = _sign(signing_input, secret)
        if not hmac.compare_digest(signature_b64, expected_sig):
            return False, "firma inválida"

        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))

        exp = int(payload.get("exp", 0))
        if exp and int(time.time()) > exp:
            return False, "token expirado"

        return True, payload
    except Exception as e:
        return False, f"error de verificación: {e}"


# alias por si algún módulo espera estos nombres
verify_token = verify
decode_token = verify
