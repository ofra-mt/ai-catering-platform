"""Lead scoring with a logistic-regression model, in pure Python (no numpy at runtime).

p = sigmoid(intercept + sum_i w_i * z_i), where z_i = (x_i - mean_i) / std_i.
The model file is JSON, never pickle (pickle runs code on load). See ADR-0005.
"""

import json
import math
from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "lead_model.json"

BUDGET_LEVEL = {"low": 0, "mid": 1, "high": 2, "premium": 3}
# One-hot event types. "אחר" is the baseline: all type_* features are 0.
TYPE_FEATURES = {
    "יום הולדת": "type_birthday",
    "אירוע משפחתי": "type_family",
    "בר או בת מצווה": "type_bar_mitzvah",
    "ארוחת שבת": "type_shabbat",
    "יום נישואין": "type_anniversary",
    "חגיגה פרטית": "type_private",
}
PAID_WORDS = ("google", "facebook", "instagram", "cpc", "ads", "paid")
REFERRAL_WORDS = ("referral", "friend", "whatsapp", "המלצה")

# Hebrew label per feature, used to explain a score to the business owner.
LABELS = {
    "log_guests": "מספר אורחים",
    "months_ahead": "זמן עד האירוע",
    "budget_level": "רמת תקציב",
    "has_email": "השאיר אימייל",
    "msg_len": "אורך ההודעה",
    "is_weekend": "אירוע בסוף שבוע",
    "type_birthday": "יום הולדת",
    "type_family": "אירוע משפחתי",
    "type_bar_mitzvah": "בר או בת מצווה",
    "type_shabbat": "ארוחת שבת",
    "type_anniversary": "יום נישואין",
    "type_private": "חגיגה פרטית",
    "src_paid": "הגיע מפרסום ממומן",
    "src_referral": "הגיע בהמלצה",
}


def extract_features(lead: Mapping[str, Any], today: date | None = None) -> dict[str, float]:
    """Numeric features from a lead dict. Missing or odd values fall back to neutral numbers."""
    today = lead.get("created_on") or today or date.today()
    event_date = lead.get("event_date")
    days = (event_date - today).days if isinstance(event_date, date) else 0
    source = (lead.get("source") or "").lower()
    features = {
        "log_guests": math.log(max(int(lead.get("guests") or 1), 1)),
        "months_ahead": min(max(days, 0), 365) / 30,
        "budget_level": float(BUDGET_LEVEL.get(lead.get("budget_band"), 0)),
        "has_email": float(bool(lead.get("email"))),
        "msg_len": min(len(lead.get("message") or ""), 1000) / 100,
        # Israel's weekend: Friday (4) and Saturday (5) in Python's Monday=0 numbering.
        "is_weekend": float(isinstance(event_date, date) and event_date.weekday() in (4, 5)),
    }
    for event_type, name in TYPE_FEATURES.items():
        features[name] = float(lead.get("event_type") == event_type)
    features["src_paid"] = float(any(w in source for w in PAID_WORDS))
    features["src_referral"] = float(any(w in source for w in REFERRAL_WORDS))
    return features


@lru_cache
def load_model() -> dict[str, Any]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def contributions(features: Mapping[str, float], model: Mapping[str, Any]) -> dict[str, float]:
    """w_i * z_i for each feature."""
    return {
        name: w * ((features[name] - mean) / (std or 1.0))
        for name, w, mean, std in zip(
            model["features"], model["coef"], model["mean"], model["std"], strict=True
        )
    }


def score(lead: Mapping[str, Any]) -> tuple[float, list[dict[str, str]]]:
    """Return (probability of winning, top 3 reasons by |w_i * z_i|)."""
    model = load_model()
    parts = contributions(extract_features(lead), model)
    logit = model["intercept"] + sum(parts.values())
    probability = 1 / (1 + math.exp(-logit))
    top = sorted(parts, key=lambda n: abs(parts[n]), reverse=True)[:3]
    reasons = [{"label": LABELS[n], "direction": "+" if parts[n] >= 0 else "−"} for n in top]
    return probability, reasons
