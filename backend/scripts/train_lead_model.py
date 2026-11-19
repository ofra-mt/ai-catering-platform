"""Train the lead-scoring logistic regression and write app/ml/lead_model.json.

Run from backend/:  uv run python scripts/train_lead_model.py
Needs scikit-learn and numpy (dev group). The server itself needs neither.
"""

import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_synthetic_leads import TRUE_COEF  # noqa: E402

from app.services.lead_scoring import LABELS, contributions, extract_features  # noqa: E402

DATA = BACKEND / "data" / "synthetic_leads.csv"
OUT = BACKEND / "app" / "ml" / "lead_model.json"
VERSION = "synthetic-v1"


def load_rows(path: Path = DATA) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["created_on"] = date.fromisoformat(r["created_on"])
        r["event_date"] = date.fromisoformat(r["event_date"])
        r["guests"] = int(r["guests"])
        r["won"] = int(r["won"])
    return rows


def train(rows: list[dict], seed: int = 42) -> tuple[dict, dict]:
    """Return (model dict as saved in the JSON, extras for the report)."""
    names = list(extract_features(rows[0]))  # same features as in serving
    X = np.array([[extract_features(r)[n] for n in names] for r in rows])
    y = np.array([r["won"] for r in rows])
    idx = np.arange(len(rows))
    tr, te = train_test_split(idx, test_size=0.25, stratify=y, random_state=seed)

    mean = X[tr].mean(axis=0)
    std = X[tr].std(axis=0)
    std[std == 0] = 1.0
    Z = (X - mean) / std
    clf = LogisticRegression(class_weight="balanced", max_iter=1000).fit(Z[tr], y[tr])

    proba = clf.predict_proba(Z[te])[:, 1]
    auc = float(roc_auc_score(y[te], proba))
    cm = confusion_matrix(y[te], proba >= 0.5).tolist()
    model = {
        "version": VERSION,
        "synthetic": True,
        "trained_on": len(tr),
        "features": names,
        "coef": [float(w) for w in clf.coef_[0]],
        "intercept": float(clf.intercept_[0]),
        "mean": [float(m) for m in mean],
        "std": [float(s) for s in std],
        "metrics": {"auc": round(auc, 4), "test_size": len(te), "confusion_matrix": cm},
    }
    return model, {"test_rows": [rows[i] for i in te]}


def interpret(name: str, w: float) -> str:
    label = LABELS[name]
    ratio = math.exp(w)
    if abs(w) < 0.1:
        return f"כמעט אין השפעה של '{label}' על הסיכוי."
    word = "מגדילה" if w > 0 else "מקטינה"
    return f"עלייה של סטיית תקן אחת ב'{label}' {word} את היחס סיכוי-לאי-סיכוי פי {ratio:.2f}."


def report(model: dict, extras: dict) -> None:
    m = model["metrics"]
    print("=== דוח אימון: מודל דירוג לידים (נתונים סינתטיים) ===\n")
    print(f"אימון על {model['trained_on']} לידים, בדיקה על {m['test_size']}.")
    print(f"AUC על קבוצת הבדיקה: {m['auc']:.3f}  (0.5 = ניחוש, 1.0 = מושלם)")
    (tn, fp), (fn, tp) = m["confusion_matrix"]
    print(f"מטריצת בלבול (סף 0.5): נכון-הפסיד={tn}  שגוי-חזה-ייסגר={fp}")
    print(f"                        שגוי-חזה-יפסיד={fn}  נכון-ייסגר={tp}\n")

    print("--- מקדמים (על משתנים מנורמלים: z = (x - ממוצע) / סטיית תקן) ---")
    print("w = המקדם. e^w = odds ratio: פי כמה גדל היחס סיכוי-לאי-סיכוי כש-z עולה ב-1.\n")
    for name, w in sorted(
        zip(model["features"], model["coef"], strict=True), key=lambda p: -abs(p[1])
    ):
        print(f"{name:18} w={w:+.3f}  e^w={math.exp(w):.2f}  {interpret(name, w)}")

    print("\n--- מקדמים שנלמדו מול האמת שבסקריפט היצירה (על סקאלת הפיצ'ר המקורי: w / std) ---")
    print("ההתאמה לא מושלמת: יש רעש, מעט נתונים, והסדרה (regularization) מקטינה מקדמים.\n")
    print(f"{'פיצ׳ר':18}{'אמיתי':>9}{'נלמד':>9}")
    for name, w, s in zip(model["features"], model["coef"], model["std"], strict=True):
        print(f"{name:18}{TRUE_COEF[name]:>+9.2f}{w / s:>+9.2f}")

    lead = extras["test_rows"][0]
    parts = contributions(extract_features(lead), model)
    print("\n--- חישוב ציון של ליד אחד, צעד אחר צעד ---")
    print(f"ליד: {lead['event_type']}, {lead['guests']} אורחים, תקציב {lead['budget_band']}")
    features = extract_features(lead)
    for name, mean, std in zip(model["features"], model["mean"], model["std"], strict=True):
        z = (features[name] - mean) / std
        print(f"{name:18} x={features[name]:7.2f}  z={z:+.2f}  w*z={parts[name]:+.3f}")
    total = sum(parts.values())
    logit = model["intercept"] + total
    print(f"\nסכום w*z = {total:+.3f}")
    print(f"logit = intercept {model['intercept']:+.3f} + סכום = {logit:+.3f}")
    print(f"הסתברות = 1 / (1 + e^-logit) = {1 / (1 + math.exp(-logit)):.3f}")
    print(f"התוצאה האמיתית של הליד: {'נסגר' if lead['won'] else 'לא נסגר'}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    trained, extra = train(load_rows())
    report(trained, extra)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(trained, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nהמודל נשמר ב-{OUT}")
