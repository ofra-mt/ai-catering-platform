from app.repositories import leads as leads_repo
from app.schemas.leads import LeadIn
from app.services import lead_scoring


def create_lead(lead: LeadIn) -> dict:
    """Score the lead and store it. The score is computed here, never taken from the client."""
    probability, reasons = lead_scoring.score(lead.model_dump())
    row = {
        **lead.model_dump(mode="json", exclude={"website"}),
        "score": round(probability, 4),
        "score_model_version": lead_scoring.load_model()["version"],
        "score_reasons": reasons,
    }
    saved = leads_repo.insert_lead(row)
    return {"id": saved["id"], "status": saved.get("status", "new")}
