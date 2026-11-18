# ADR 0005 — Lead scoring with logistic regression

Status: Accepted · Date: 2026-11-18

## Context
The owner wants to see the leads most likely to become orders first, and to understand why. This is an educational project: there is no real lead data yet, so all data is synthetic.

## Decision
- A form on the landing page posts to `POST /api/leads`. Only the backend inserts into `leads` (service role key). The admin reads and updates status through RLS.
- The model is a logistic regression: `p = sigmoid(b + sum w_i * z_i)`, with `z_i` standardized. Each score returns the 3 largest `|w_i * z_i|` as reasons, so the owner sees why.
- The model lives in `backend/app/ml/lead_model.json` (weights, mean, std, metrics). JSON, not pickle, because pickle runs code on load. The server computes the score in pure Python and adds no runtime dependency.
- Training is offline: `scripts/train_lead_model.py` (scikit-learn, dev group only) on `data/synthetic_leads.csv`. Training imports `extract_features` from the service, so training and serving use the same features.
- The model is marked `synthetic: true`. The admin UI labels the score "הערכה ראשונית (נתונים סינתטיים)". Retrain when at least 50 real closed leads (`won` or `lost`) exist.

## Consequences
+ Simple, explainable, no ML runtime on the server.
+ The synthetic generator declares the true coefficients, so training can be checked against them.
- The score reflects invented rules, not real customers, until retraining.
- The per-IP rate limit is in memory: per process, reset on restart.
