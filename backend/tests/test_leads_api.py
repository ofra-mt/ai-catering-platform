from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import leads as leads_api
from app.core.config import Settings
from app.main import app

client = TestClient(app)

VALID = {
    "full_name": "נועה לוי",
    "phone": "050-123 4567",
    "email": "noa@example.com",
    "event_type": "בר או בת מצווה",
    "event_date": (date.today() + timedelta(days=30)).isoformat(),
    "guests": 80,
    "budget_band": "mid",
    "source": "referral",
    "message": "שלום",
    "consent": True,
    "website": "",
}


@pytest.fixture(autouse=True)
def reset_rate_limit():
    leads_api._hits.clear()


@pytest.fixture
def stored(monkeypatch):
    rows = []

    def fake_insert(row):
        rows.append(row)
        return {"id": "11111111-1111-1111-1111-111111111111", "status": "new"}

    monkeypatch.setattr("app.repositories.leads.insert_lead", fake_insert)
    return rows


def test_valid_lead_created_and_scored_server_side(stored):
    response = client.post("/api/leads", json={**VALID, "score": 1})
    assert response.status_code == 201
    assert response.json() == {"id": "11111111-1111-1111-1111-111111111111", "status": "new"}
    row = stored[0]
    assert row["phone"] == "0501234567"
    assert 0 < row["score"] < 1 and row["score"] != 1
    assert len(row["score_reasons"]) == 3
    assert "website" not in row


@pytest.mark.parametrize(
    "change",
    [
        {"phone": "12345"},
        {"consent": False},
        {"message": "א" * 1001},
        {"event_date": (date.today() - timedelta(days=1)).isoformat()},
        {"website": "http://spam.example"},
        {"guests": 0},
        {"event_type": "לא קיים"},
        {"email": "not-an-email"},
        {"full_name": "א"},
    ],
)
def test_invalid_lead_rejected(stored, change):
    response = client.post("/api/leads", json={**VALID, **change})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "0501234567" not in str(error)
    assert stored == []


def test_503_when_supabase_not_configured(monkeypatch):
    monkeypatch.setattr("app.repositories.leads.get_settings", lambda: Settings(_env_file=None))
    response = client.post("/api/leads", json=VALID)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_rate_limit(stored):
    codes = [client.post("/api/leads", json=VALID).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]
