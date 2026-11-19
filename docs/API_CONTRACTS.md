# API Contracts (preliminary)

Status: **Draft v0.1**. `GET /health`, `GET /api/public-config` and `POST /api/leads` are implemented. Everything else is a design target and may change.

Base: same origin as the frontend. JSON only. All bodies validated with Pydantic.

## Error format

```json
{ "error": { "code": "order_version_conflict", "message": "Human readable", "details": {} } }
```

Common codes: `validation_error` (422), `not_found` (404), `forbidden` (403), `unauthenticated` (401), `invalid_transition` (409), `order_version_conflict` (409), `proposal_not_pending` (409).

## System

| Method | Path | Response | Phase |
|---|---|---|---|
| GET | `/health` | `{"status":"ok","env":"development"}` | **1 (implemented)** |

## Leads (public write)

| Method | Path | Response |
|---|---|---|
| POST | `/api/leads` | `201 {"id", "status": "new"}` |

Body: `full_name`, `phone`, `email?`, `event_type`, `event_date` (future), `guests` (1-5000), `budget_band` (`low|mid|high|premium`), `source?`, `message?` (max 1000), `consent` (must be `true`), `website` (honeypot, must be empty). The backend computes the score (ADR-0005); a client-sent score is ignored.

Errors use the standard shape: `422 validation_error` (details list field names only, never submitted values), `429 rate_limited` (5 per 10 minutes per IP, in memory), `502 storage_error`, `503 service_unavailable` (Supabase not configured).

## Catalog (public read)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/catalog/categories` | Active categories, ordered |
| GET | `/api/catalog/dishes?category_id=&vegan=&vegetarian=&kashrut=` | Available dishes with price, unit, dietary info (unknown fields returned as `null`) |
| GET | `/api/catalog/dishes/{id}` | Dish detail incl. allergen statuses |
| GET | `/api/availability?from=&to=` | Blocked dates + slots |

## Customer orders (auth model **[OPEN #1]**)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders` | Create draft from event config |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | Set quantity; requires `version` |
| DELETE | `/api/orders/{id}/items/{dish_id}` | Remove dish; requires `version` |
| GET | `/api/orders/{id}/pricing` | Itemized breakdown |
| GET | `/api/orders/{id}/recommendations` | Quantity recommendations (rules **[OPEN #3]**) |
| POST | `/api/orders/{id}/submit` | `draft → pending_approval`; freezes snapshot |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

## AI assistant (Phase 4)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders/{id}/chat` | `{message}` → `{reply, proposals:[...]}` |
| GET | `/api/orders/{id}/proposals?status=pending` | |
| POST | `/api/orders/{id}/proposals/{pid}/approve` | Executes in one transaction if `base_order_version == order.version` and status `pending` |
| POST | `/api/orders/{id}/proposals/{pid}/reject` | No mutation |

Proposal shape:

```json
{
  "id": "uuid",
  "base_order_version": 7,
  "changes": [
    {"op": "add_item", "dish_id": "uuid", "quantity": 2},
    {"op": "set_quantity", "dish_id": "uuid", "quantity": 4},
    {"op": "remove_item", "dish_id": "uuid"},
    {"op": "update_details", "fields": {"requested_at": "..."}}
  ],
  "diff": [{"label": "...", "current": "...", "proposed": "..."}],
  "price_before": "1200.00",
  "price_after": "1350.00",
  "status": "pending"
}
```

## Admin (owner only)

| Method | Path |
|---|---|
| GET/POST | `/api/admin/categories` · PATCH/DELETE `/api/admin/categories/{id}` |
| GET/POST | `/api/admin/dishes` · PATCH/DELETE `/api/admin/dishes/{id}` |
| POST | `/api/admin/dishes/{id}/image` (multipart → Supabase Storage) |
| PUT | `/api/admin/dishes/{id}/dietary` |
| GET/POST/PATCH/DELETE | `/api/admin/delivery-zones` |
| GET/POST/PATCH/DELETE | `/api/admin/time-slots` |
| GET/POST/DELETE | `/api/admin/blocked-dates` |
| GET | `/api/admin/orders?status=` · GET `/api/admin/orders/{id}` |
| POST | `/api/admin/orders/{id}/approve` · `/api/admin/orders/{id}/reject` `{note}` |

## Order status transitions

| Transition | Endpoint | Allowed actor |
|---|---|---|
| draft → pending_approval | `POST /api/orders/{id}/submit` | Order's customer |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | Owner |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | Owner |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
