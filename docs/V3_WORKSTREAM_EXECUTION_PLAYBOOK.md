## Intent
Make **every WatchfulEye V3 workstream** executable as a **standalone slice** (one branch/PR), while still allowing **parallel development** without conflicts.

## Non‑negotiables (always true)
- **Do not break existing production UI/surfaces**: Main News Feed, Custom News Feed, Telegram Intel Reports, Intel Reports, AI Analysis Modal.
- **Flags default OFF**: any new surface behind `V3_*` and OFF by default.
- **One PR = one workstream slice**: do not mix unrelated fixes.
- **Contracts are WS0-owned**: if you need a schema/contract change, do it via WS0 in its own PR.
- **Staging deploy safety**: staging is deployed from a **master-only worktree**, not from the dev workspace.

## Two directories rule (server discipline)
- **DEV workspace**: `/opt/watchfuleye2`
  - You do feature work here on branches.
  - **Important**: because `master` is checked out in the staging worktree, you create branches from `origin/master`.
- **STAGING deploy worktree**: `/opt/watchfuleye2-staging`
  - Must stay on `master` and track `origin/master`.
  - You deploy staging from here only.

## Standard commands (copy/paste)

### Start a new workstream slice (DEV workspace)
Run in `/opt/watchfuleye2`:

```bash
cd /opt/watchfuleye2
git fetch origin master
git checkout -b wsX/<slice-name> origin/master
```

Where:
- `wsX/` is the workstream prefix (`ws0/`, `ws1/`, `ws4/`, `docs/`, `infra/`, `fix/`)
- `<slice-name>` is short and specific (e.g., `ws4/examine-mvp-skeleton`)

### Deploy `master` to staging (STAGING worktree)
Run in `/opt/watchfuleye2-staging`:

```bash
cd /opt/watchfuleye2-staging
git pull --ff-only origin master
sudo systemctl restart watchfuleye-backend-staging
sudo systemctl restart watchfuleye-frontend-staging
```

## Parallelization model (how multiple agents work safely)

### “Parallel build, sequential merge”
- Multiple workstreams can develop **in parallel** on separate branches.
- Merges to `master` remain **sequential** to keep staging/prod stable.
- WS0 changes land first when they are dependencies for others.

### Shared “hot files” (touch only with explicit justification)
Avoid drive-by edits to these. If you must touch them, call it out explicitly in the PR template.
- `web_app.py` (Flask app wiring)
- `watchfuleye/storage/postgres_schema.py` (shared schema)
- `.github/workflows/ci.yml` (CI gate)
- `frontend/src/App.tsx` / app-wide routing
- systemd/nginx files (infra-only; typically not in repo)

## Workstream ownership map (recommended)
Use these **owned path conventions** so each WS can ship independently.

### Backend (Python) V3 paths
- **WS0**: `contracts/v3/**`, `docs/V3_CONTRACTS.md`, `watchfuleye/v3/**`, `watchfuleye/storage/postgres_schema.py`
- **WS1 (Main feed)**: `watchfuleye/v3/feeds/news/**`
- **WS1.1 / WS1.2 (Reports / AI modal)**: `watchfuleye/v3/reports/**`
- **WS2 (Custom feeds)**: `watchfuleye/v3/feeds/custom/**`
- **WS3 (Telegram feed)**: `watchfuleye/v3/telegram_feed/**`
- **WS3.1 (Telegram agent)**: `watchfuleye/v3/telegram_agent/**`
- **WS4 (Investigations / Examine X)**: `watchfuleye/v3/investigations/**`
- **WS5 (Connectors)**: `watchfuleye/v3/connectors/**`
- **WS6 (Alerts/Monitoring)**: `watchfuleye/v3/alerts/**`
- **WS6.1 (Forecast accountability)**: `watchfuleye/v3/forecast/**`
- **WS7 (Modules v2)**: `watchfuleye/v3/modules/**`
- **WS8 (AI panel builder/store)**: `watchfuleye/v3/panel_builder/**`
- **WS9 (Map layers)**: `watchfuleye/v3/map_layers/**`
- **WS10 (Campaigns)**: `watchfuleye/v3/campaigns/**`
- **WS11 (Multi-display)**: `watchfuleye/v3/multidisplay/**`
- **WS12 (Immersion)**: `watchfuleye/v3/immersion/**`

### Frontend (React) V3 paths
Recommended: put all V3 UI behind a clear subtree so V1 UI doesn’t get churned.
- `frontend/src/v3/**` (root for all V3 UI)
- Mirror workstreams:
  - `frontend/src/v3/reports/**`, `frontend/src/v3/investigations/**`, `frontend/src/v3/modules/**`, etc.

## “Slice definition” checklist (what makes a PR merge-safe)
Every slice must declare:
- **Owned paths** (what this PR owns)
- **Explicitly NOT touched** (hot files avoided)
- **Flags** (new or existing; default OFF)
- **Contracts** (if any; WS0-only)
- **Verification**:
  - unit tests added/updated
  - staging smoke check steps (curl / UI clicks)
- **Rollback** (almost always: flip flag OFF)

---

## Low-credit / junior-agent mode
If you run out of credits (or are using a weaker agent), enforce “safe mode”:
- Only allow **bounded** slices with deterministic acceptance criteria.
- Provide an explicit owned-files list and explicit “do not touch” list.
- Force flag gates + response shape tests.

See: `docs/V3_LOW_CREDIT_AGENT_MODE.md`


