import time
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.repositories.leads import LeadStorageError, LeadStorageNotConfigured
from app.schemas.leads import LeadIn
from app.services import leads as leads_service

router = APIRouter()

RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 600
# shortcut: in-memory per-IP counter. It is per process and resets on restart. Behind a proxy the
# IP is the proxy's. Upgrade to a shared store (Redis or a DB table) when running several workers.
_hits: dict[str, list[float]] = defaultdict(list)


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": {}}}
    return JSONResponse(status_code=status, content=body)


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    if len(_hits) > 10_000:  # drop stale IPs so many distinct clients cannot grow memory forever
        for stale in [k for k, v in _hits.items() if not v or now - v[-1] >= RATE_WINDOW_SECONDS]:
            del _hits[stale]
    recent = [t for t in _hits[ip] if now - t < RATE_WINDOW_SECONDS]
    limited = len(recent) >= RATE_LIMIT
    if not limited:
        recent.append(now)
    _hits[ip] = recent
    return limited


@router.post("/api/leads", status_code=201)
def create_lead(lead: LeadIn, request: Request):
    if _rate_limited(request.client.host if request.client else "unknown"):
        return _error(429, "rate_limited", "יותר מדי פניות. נסו שוב בעוד כמה דקות.")
    try:
        return leads_service.create_lead(lead)
    except LeadStorageNotConfigured:
        return _error(503, "service_unavailable", "השירות אינו זמין כרגע.")
    except LeadStorageError:
        return _error(502, "storage_error", "לא הצלחנו לשמור את הפנייה. נסו שוב.")
