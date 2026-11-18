from datetime import date, timedelta

from app.services.lead_scoring import extract_features, load_model, score

TODAY = date(2026, 6, 1)


def lead(**over):
    base = {
        "event_type": "בר או בת מצווה",
        "event_date": TODAY + timedelta(days=60),
        "guests": 80,
        "budget_band": "mid",
        "email": "a@example.com",
        "source": "referral",
        "message": "שלום",
        "created_on": TODAY,
    }
    return {**base, **over}


def test_features_for_empty_input():
    f = extract_features({}, today=TODAY)
    assert set(f) == set(load_model()["features"])
    assert f["log_guests"] == 0 and f["has_email"] == 0 and f["months_ahead"] == 0


def test_features_for_extreme_input():
    f = extract_features(
        lead(guests=5000, message="א" * 5000, event_date=TODAY + timedelta(days=9999))
    )
    assert f["msg_len"] == 10 and f["months_ahead"] == 365 / 30


def test_score_is_probability_with_three_reasons():
    p, reasons = score(lead())
    assert 0 < p < 1
    assert len(reasons) == 3
    assert all(r["direction"] in ("+", "−") and r["label"] for r in reasons)


def test_score_is_deterministic():
    assert score(lead()) == score(lead())


def test_more_guests_scores_higher():
    # The true (and learned) coefficient of log_guests is positive.
    assert score(lead(guests=300))[0] > score(lead(guests=10))[0]
