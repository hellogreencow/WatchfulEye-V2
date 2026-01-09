## WS0 datasets

This directory contains **small, static datasets** that we vendor into the repo to keep WS0 seeding deterministic (no runtime network calls).

- **`iso3166_all.json`**: ISO-3166 country list used for seeding `entities`/`entity_identifiers`.
  - **Source**: `lukes/ISO-3166-Countries-with-Regional-Codes` (vendored snapshot).
  - **Why vendored**: ISO’s official list is not freely redistributable; this snapshot is a commonly used public dataset and is sufficient for resolver V1 behavior.


