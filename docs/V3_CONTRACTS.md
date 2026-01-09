## WatchfulEye V3 — Contracts (WS0)

This document is the **versioned contract surface** for `/api/v3/*`.

### Principles
- **Flagged rollout**: V3 surfaces are OFF by default and enabled explicitly via `V3_*` env flags.
- **Server authoritative**: clients do not hold secrets; contracts are stable and versioned.
- **Auditable**: every request should be traceable via `trace_id` (and later `workflow_id`).

---

## Feature Flags
- `V3_ENTITY_IDS`:
  - **default**: OFF
  - **effect**: enables V3 entity-resolution endpoints (WS0)
- `V3_EXAMINE_MVP`:
  - **default**: OFF
  - **effect**: enables `POST /api/v3/examine` (WS4 entrypoint; WS0 contract scaffold)

---

## API: Entity Resolution (WS0)

### `POST /api/v3/entities/resolve`

#### Behavior
- If `V3_ENTITY_IDS` is OFF: **404** (surface hidden)
- If `V3_ENTITY_IDS` is ON:
  - validates request
  - returns a deterministic response shape (stub matches until resolver ships)

#### Request JSON
- Schema: `contracts/v3/entities.resolve.schema.json`

#### Response JSON (stub v1)
```json
{
  "matches": [],
  "trace_id": "uuid",
  "q": "AAPL",
  "k": 10,
  "types": ["ticker", "country", "sanctions_target"]
}
```

#### Notes
- Resolver logic is intentionally minimal at first (exact match only) and will expand in WS0 slices.

---

## API: Examine (WS4 entrypoint; WS0 contract scaffold)

### `POST /api/v3/examine`

#### Behavior
- If `V3_EXAMINE_MVP` is OFF: **404** (surface hidden)
- If `V3_EXAMINE_MVP` is ON:
  - validates request
  - returns a stable response shape (`investigation_id`, `report_id`, `trace_id`)
  - persists minimal rows to Postgres if `PG_DSN` is configured (never fails if Postgres is unavailable)

#### Request/Response JSON
- Schema: `contracts/v3/examine.schema.json`


