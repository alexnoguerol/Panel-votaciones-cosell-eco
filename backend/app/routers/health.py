from fastapi import APIRouter
from ..utils.time import now_utc, isoformat_utc

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "time_utc": isoformat_utc(now_utc())}
