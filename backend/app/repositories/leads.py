import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings


class LeadStorageNotConfigured(Exception):
    pass


class LeadStorageError(Exception):
    pass


def insert_lead(row: dict[str, Any]) -> dict[str, Any]:
    """Insert one lead via the Supabase REST API with the service role key (server side only)."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise LeadStorageNotConfigured
    url = settings.supabase_url.rstrip("/") + "/rest/v1/leads"
    if not url.startswith(("https://", "http://")):
        raise LeadStorageNotConfigured
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        data=json.dumps(row).encode(),
        method="POST",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read())[0]
    except (urllib.error.URLError, TimeoutError, ValueError, IndexError) as exc:
        # Never include the row (phone, email) in the error.
        raise LeadStorageError(type(exc).__name__) from None
