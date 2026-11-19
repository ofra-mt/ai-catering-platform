from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import leads
from app.core.config import get_settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Error shape from docs/API_CONTRACTS.md. Field names only: never echo submitted values."""
    details = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
    ]
    body = {
        "error": {
            "code": "validation_error",
            "message": "הנתונים שנשלחו אינם תקינים.",
            "details": details,
        }
    }
    return JSONResponse(status_code=422, content=body)


app.include_router(leads.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


@app.get("/api/public-config")
def public_config() -> dict[str, str]:
    """Values the browser needs. Only the publishable key belongs here, never a secret."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_publishable_key):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    return {
        "supabaseUrl": settings.supabase_url,
        "supabasePublishableKey": settings.supabase_publishable_key,
    }


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
