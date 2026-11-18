import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from make_synthetic_leads import generate  # noqa: E402
from train_lead_model import train  # noqa: E402


def test_training_on_synthetic_leads_beats_chance():
    model, _ = train(generate(500, seed=42))
    assert model["metrics"]["auc"] > 0.7
    assert model["synthetic"] is True
    assert len(model["coef"]) == len(model["features"]) == len(model["mean"]) == len(model["std"])
