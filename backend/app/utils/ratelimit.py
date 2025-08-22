from __future__ import annotations

import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status

# Ventana deslizante en memoria (por proceso)
_BUCKETS: Dict[Tuple[str, str], list] = {}  # (scope, key) -> [timestamps]

def _hit(scope: str, key: str, limit: int, window_s: int) -> None:
    now = time.time()
    bucket = _BUCKETS.setdefault((scope, key), [])
    # limpia entradas fuera de ventana
    cutoff = now - window_s
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit excedido para {scope}. Inténtalo más tarde.",
        )
    bucket.append(now)

def limit_by_ip(req: Request, scope: str, limit: int, window_s: int) -> None:
    ip = (req.client.host if req.client else "unknown") or "unknown"
    _hit(scope, ip, limit, window_s)

def limit_by_key(key: str, scope: str, limit: int, window_s: int) -> None:
    _hit(scope, key.lower().strip(), limit, window_s)
