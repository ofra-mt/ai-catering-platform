"""Generate synthetic leads (invented data) with a known "true" rule for winning.

Run from backend/:  uv run python scripts/make_synthetic_leads.py
Output: backend/data/synthetic_leads.csv

The true model is declared below. train_lead_model.py tries to learn it back, which is the exercise.
"""

import csv
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.lead_scoring import extract_features  # noqa: E402

OUT = BACKEND / "data" / "synthetic_leads.csv"
N_LEADS = 500
SEED = 42

# ---- ה"אמת" שהמחשב לא מכיר: המקדמים שלפיהם נקבע אם ליד נסגר ----
# כל מקדם הוא על סקאלת הפיצ'ר המקורי (לא מנורמל): "כמה עולה log-odds כשהפיצ'ר עולה ב-1".
TRUE_INTERCEPT = -4.2  # נקודת פתיחה: ליד "ממוצע" נסגר בסיכוי נמוך יחסית
TRUE_COEF = {
    "log_guests": 0.7,  # יותר אורחים = הזמנה גדולה יותר = הלקוח רציני יותר
    "months_ahead": -0.12,  # אירוע רחוק בכל חודש = פחות מחויבות עכשיו
    "budget_level": 0.55,  # תקציב גבוה = סיכוי גבוה לסגור
    "has_email": 0.5,  # מי שהשאיר אימייל השקיע מאמץ ורציני יותר
    "msg_len": 0.25,  # הודעה ארוכה (לכל 100 תווים) = עניין אמיתי
    "is_weekend": -0.4,  # שישי/שבת: הקייטרינג כבר תפוס לעיתים קרובות
    "type_birthday": -0.1,  # יום הולדת: קצת פחות סיכוי מ"אחר"
    "type_family": 0.2,  # אירוע משפחתי: קצת יותר
    "type_bar_mitzvah": 0.8,  # בר/בת מצווה: אירועים גדולים שמתוכננים מראש
    "type_shabbat": -0.4,  # ארוחת שבת: חד-פעמי וקטן, נסגר פחות
    "type_anniversary": 0.3,  # יום נישואין: מוכנים לשלם על חוויה
    "type_private": 0.1,  # חגיגה פרטית: כמעט כמו "אחר"
    "src_paid": -0.6,  # פרסום ממומן: הרבה גולשים סקרנים שלא קונים
    "src_referral": 0.9,  # המלצה: אמון מראש, נסגר הרבה יותר
}
NOISE_SD = 0.5  # רעש: דברים שאין לנו עליהם נתון (מצב רוח, מתחרים) ומטשטשים את הכלל

TYPES = [
    "יום הולדת",
    "אירוע משפחתי",
    "בר או בת מצווה",
    "ארוחת שבת",
    "יום נישואין",
    "חגיגה פרטית",
    "אחר",
]
SOURCES = ["", "", "google_cpc", "facebook_ads", "referral", "whatsapp", "instagram"]
BUDGETS = ["low", "mid", "high", "premium"]
FIELDS = [
    "created_on",
    "event_type",
    "event_date",
    "guests",
    "budget_band",
    "email",
    "source",
    "message",
    "won",
]


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def true_logit(lead: dict) -> float:
    features = extract_features(lead)
    return TRUE_INTERCEPT + sum(TRUE_COEF[name] * value for name, value in features.items())


def generate(n: int = N_LEADS, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security
    rows = []
    for _ in range(n):
        created_on = date(2026, 1, 1) + timedelta(days=rng.randint(0, 300))
        guests = min(max(round(math.exp(rng.gauss(math.log(50), 0.7))), 5), 600)
        # Bigger events tend to have bigger budgets.
        budget_index = min(3, max(0, round(rng.gauss(0.5 + math.log(guests / 20) * 0.7, 0.9))))
        n_chars = rng.randint(20, 400) if rng.random() < 0.5 else 0
        lead = {
            "created_on": created_on,
            "event_type": rng.choice(TYPES),
            "event_date": created_on + timedelta(days=rng.randint(3, 240)),
            "guests": guests,
            "budget_band": BUDGETS[budget_index],
            "email": "lead@example.com" if rng.random() < 0.6 else "",
            "source": rng.choice(SOURCES),
            "message": "א" * n_chars,
        }
        # Label: sample won/lost from the sigmoid of the true score plus noise.
        lead["won"] = int(rng.random() < sigmoid(true_logit(lead) + rng.gauss(0, NOISE_SD)))
        rows.append(lead)
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    leads = generate()
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(leads)
    won = sum(r["won"] for r in leads)
    print(f"נכתבו {len(leads)} לידים ל-{OUT} ({won} נסגרו, {won / len(leads):.0%})")
