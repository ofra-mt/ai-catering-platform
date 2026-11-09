# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ordering and management web app for a **single catering business**. Customers plan an event, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes apply only after the customer approves them. The owner manages the catalog and approves or rejects every quotation. The product spec lives in `docs/` (PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC, OPEN_DECISIONS, ADR/). Read the relevant doc before building a feature. Items marked **[OPEN]** are undecided and should not be decided silently.

## Commands

All backend commands run from `backend/` with [uv](https://docs.astral.sh/uv/):

```bash
cp .env.example .env                 # from repo root; config reads .env or ../.env
cd backend
uv sync                              # install deps (CI uses: uv sync --frozen)
uv run uvicorn app.main:app --reload # http://127.0.0.1:8000  (/health, /customer/, /admin/)

uv run ruff check .                  # lint (rules E,F,I,B,UP,S; line length 100)
uv run ruff format --check .         # format check (drop --check to apply)
uv run pytest                        # all tests
uv run pytest tests/test_health.py::test_health_ok   # single test
```

CI (`.github/workflows/ci.yml`) runs exactly these lint/format/test steps on pushes and PRs to `dev` and `main`. The frontend has no build step, linter or tests: open the pages through the running server.

## Architecture

**One FastAPI process serves both the API and the frontend.** `backend/app/main.py` defines the API routes and then mounts `frontend/` as static files at `/`. That mount must stay last so API routes take precedence. Everything is same-origin, so there is no CORS setup.

**Backend layers** (`backend/app/`): `api → services → repositories → models`. Lower layers never import upper ones. `schemas/` holds the Pydantic DTOs and AI-tool argument schemas, and `core/` holds the config (`pydantic-settings`, `get_settings()` is cached). Most of these packages are still empty scaffolding (the project is in Phase 1). See the phase table in `docs/ARCHITECTURE.md`.

Non-negotiable rules (ADR-0003, ARCHITECTURE §2):
- **Backend is authoritative.** Prices, quantities, availability and order state are computed only in `services/`. The frontend and the LLM only display or request them.
- **The AI agent (`agents/`) is a client of services, never of the DB.** It can only *create proposals*. Executing a proposal happens through a customer-only HTTP endpoint, never through an AI tool. Execution is transactional, with optimistic locking on `orders.version` and single-use proposals.
- Submitting an order freezes a price snapshot on `order_items`.
- Error responses use the shape `{ error: { code, message, details } }` (`docs/API_CONTRACTS.md`).

**Frontend** (`frontend/`): plain HTML/CSS and vanilla ES modules, Hebrew RTL, no framework (a confirmed decision). Pages: `index.html` (landing), `customer/`, `admin/`.
- The customer app (`js/customer/`) is a small store plus views: `store.js` holds state (persisted to localStorage, with `subscribe`/`commit`). `main.js` renders one view per step (`event → menu → summary → status`) and registers it in `VIEWS`.
- **`js/customer/mock-backend.js` currently stands in for the real API.** It mirrors the shapes in `API_CONTRACTS.md`, so views can switch to `api()` (`js/api.js`) without markup changes. Values marked PLACEHOLDER there are not business rules.
- Build DOM with `h()` from `js/lib/dom.js`. It sets text only and never uses `innerHTML`. Keep it that way for anything that comes from the user or the API.
- Motion goes through `js/lib/motion.js`, which no-ops under `prefers-reduced-motion`.
- Allergens: an array means a verified list (`[]` = verified none), and `null` means unknown. Unknown must never be shown as safe.
- Design-review shortcuts: `/customer/?demo=pending|approved|rejected` and `?occasion=<event type>`.

## Branches, environments, deploy

- `main` = production and `dev` = integration (ADR-0004). Feature work goes as a PR into `dev`, and a release is a PR from `dev` to `main`. CI must pass.
- This checkout is a fork: `origin` = `ofra-mt/ai-catering-platform`, and `upstream` = `JonathanZouari/ai-catering-platform` (the course's main repo).
- Hosting is Railway via `Dockerfile` (uv, `--no-dev`, `uvicorn` on `$PORT`) and `railway.json` (healthcheck `/health`). Railway and Supabase are not connected yet.
- Config comes only from env vars (`.env.example`). `SUPABASE_SERVICE_ROLE_KEY` is server-side only.
