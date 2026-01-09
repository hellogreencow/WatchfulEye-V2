## WS0 datasets

This directory contains **small, static datasets** that we vendor into the repo to keep WS0 seeding deterministic (no runtime network calls).

- **`iso3166_all.json`**: ISO-3166 country list used for seeding `entities`/`entity_identifiers`.
  - **Source**: `lukes/ISO-3166-Countries-with-Regional-Codes` (vendored snapshot).
  - **Why vendored**: ISO’s official list is not freely redistributable; this snapshot is a commonly used public dataset and is sufficient for resolver V1 behavior.
  - **Snapshot**: downloaded on **2026-01-09** from the upstream `all/all.json` path (treated as a vendored snapshot).
  - **Update process**:
    1. Re-download the upstream JSON into this path.
    2. Verify schema keys exist for all rows: `alpha-2`, `alpha-3`, `name`.
    3. Run unit tests and a staging seed + resolver smoke check.


