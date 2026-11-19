import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Same list as EVENT_TYPES in frontend/js/customer/mock-backend.js and the migration check.
EventType = Literal[
    "יום הולדת",
    "אירוע משפחתי",
    "בר או בת מצווה",
    "ארוחת שבת",
    "יום נישואין",
    "חגיגה פרטית",
    "אחר",
]
BudgetBand = Literal["low", "mid", "high", "premium"]

PHONE_RE = re.compile(r"^0(5\d|[2-489])\d{7}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LeadIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    phone: str
    email: str | None = Field(default=None, max_length=254)
    event_type: EventType
    event_date: date
    guests: int = Field(ge=1, le=5000)
    budget_band: BudgetBand
    source: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=1000)
    consent: Literal[True]
    website: str = ""  # honeypot: real users never see or fill it

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("name too short")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = re.sub(r"[\s-]", "", v)
        if not PHONE_RE.fullmatch(digits):
            raise ValueError("invalid Israeli phone number")
        return digits

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not EMAIL_RE.fullmatch(v):
            raise ValueError("invalid email")
        return v

    @field_validator("event_date")
    @classmethod
    def _future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("event_date must be in the future")
        return v

    @field_validator("website")
    @classmethod
    def _honeypot(cls, v: str) -> str:
        if v:
            raise ValueError("rejected")
        return v
