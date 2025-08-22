from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, dev_mode: bool = False) -> None:
        super().__init__(app)
        self.dev_mode = dev_mode

    async def dispatch(self, request, call_next):
        resp: Response = await call_next(request)
        path = request.url.path

        # HSTS solo en HTTPS y no en dev local
        if request.url.scheme == "https" and not self.dev_mode:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # Swagger/ReDoc necesitan inline/eval y recursos https (CDN)
        if path.startswith("/docs") or path.startswith("/redoc"):
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self' data: blob: https:; "
                "img-src 'self' data: https:; "
                "style-src 'self' 'unsafe-inline' https:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
                "connect-src 'self' https:; "
                "font-src 'self' data: https:; "
                "frame-ancestors 'none'"
            )
        else:
            # En dev permitimos inline/eval; en prod, no.
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self' data: blob:" + (" https:" if self.dev_mode else "") + "; "
                "img-src 'self' data:" + (" https:" if self.dev_mode else "") + "; "
                "style-src 'self' 'unsafe-inline'" + (" https:" if self.dev_mode else "") + "; "
                "script-src 'self' " + ("'unsafe-inline' 'unsafe-eval' https:" if self.dev_mode else "") + "; "
                "connect-src 'self'" + (" https:" if self.dev_mode else "") + "; "
                "font-src 'self' data:" + (" https:" if self.dev_mode else "") + "; "
                "frame-ancestors 'none'"
            )

        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return resp
