## WatchfulEye V3 — Master Plan (Single Source of Truth)

### Intent / Stakes / Success Criteria
- **Intent**: Ship a **billion‑dollar‑professional** intelligence platform by upgrading the **data plane + agent plane** under the existing UI so we don’t break the current look/feel.
- **Stakes**: Parallel work without boundaries causes merge conflicts, regressions, and “half‑wired” features that degrade trust.
- **Success Criteria**: Every feature is tracked as a **workstream card** with (interfaces → owned files → feature flags → acceptance criteria). We preserve **Main News Feed**, **Custom News Feed**, and **Telegram Intel Reports** while making the agent truly agentic across expanded sources.

---

### 0) Non‑Negotiables (do not delete, do not regress)
- **Main News Feed**: the canonical global briefing stream (fast, filterable, searchable).
- **Custom News Feed**: user‑defined topics/watchlists/saved searches + alert rules.
- **Telegram Intel Reports**: first‑class “intel report” feed + raw message evidence, usable as citations in reports.
- **Intel Reports are sacred**: preserve the current “Global Brief / Intelligence Report” experience and formatting; enhancements must be additive and ship behind flags.
- **AI Analysis Modal is sacred**: preserve the current per‑article AI analysis modal UX (speed, structure, send-to-chat, copy/share, perspectives); enhancements must not break existing behavior.
- **Existing Look & Navigation**: no big‑bang rewrite; changes ship behind flags and are progressively turned on.
- **No client secrets**: connectors and keys live on the server only.
- **Auditability**: every agent claim must be traceable to evidence; every tool run is logged.
- **Accountability**: when we predict, we must later measure what happened and score ourselves.

---

### 1) Current Product Shape (ground truth)
The current Figma Make direction is a **Command Center**:
- **Terminal‑style input** (the “Examine X” hook).
- **World map** with markers and hotspots.
- **Modular draggable panels** + a **module catalog**.

V3 keeps this shell and replaces simulation with real contracts and a professional architecture.

---

### 1.1) UX Contract (what the operator can do in <60 seconds)
**Principle**: the UI must make uncertainty legible and action possible, fast.

#### The operator loop (the only loop that matters)
- **Discover**: main feed + custom feed + telegram reports surface what’s new and what matters.
- **Examine**: a single input (“Examine X”) launches an investigation with streaming progress.
- **Decide**: the consolidated report provides predictions + scenarios + confidence + “what would change my mind”.
- **Monitor**: one click turns any report/topic/entity into a watch with alerts.

#### UX hard rules (billion‑dollar polish, no cosplay)
- **One global command surface**: omnibox/terminal always reachable (keyboard first).
- **Zero dead controls**: every click maps to a server effect or is removed.
- **Trust UI is non‑optional**: citations, source provenance, timestamps, confidence, dissent, missing data.
- **Speed is a feature**: progressive rendering; stream partial results; cache aggressively.
- **Progressive disclosure**: default to short, high‑signal outputs; expand only on request (or for “operator mode” users).
- **Pin + compose**: any report/widget can be pinned into the modular dashboard.
- **Consistent verbs** everywhere: **Examine**, **Monitor**, **Pin**, **Share**, **Export**.
- **No fake sentiment**: current sentiment distribution is known-flawed; any sentiment shown must declare method + confidence + data sources.

#### Baseline parity panel rule (sequencing brutality)
For any “baseline parity” panel (e.g., a **stock heatmap**), we do **not** overbuild early.
- **Must support exactly two actions**:
  - **Examine this mover**
  - **Monitor this ticker/sector**
- **Server contract is minimal and real**:
  - saved layout, pinned modules, user preferences (no client secrets)
- **Data surface may be embedded initially**:
  - v1 can be an embedded widget behind a flag
  - v2 becomes provider-backed via WS5 once the data plane is stable

---

### 1.2) Baseline Parity Pack (Situation Monitor‑class) + Leapfrog Pack (WatchfulEye‑class)
**Baseline parity** is what a serious competitor already has; **leapfrog** is what makes WatchfulEye uncatchable.

#### Baseline parity modules (ship early; these are table stakes)
- **Global Activity Monitor (Map)**:
  - Layers: **Shipping**, **Quakes**, **Cyber**, **Conflict**, **Markets** (toggleable).
  - UX: click hotspot → mini‑dossier → “Examine this” / “Monitor this”.
- **Livestream Desk**:
  - TBPN (and/or other sources) embedded, with **transcripts** stored as Evidence.
  - UX: clip‑to‑evidence + “Examine the claim in this clip”.
- **Intel Feed (Tech / Finance / Politics)**:
  - Unified feed with tags, dedupe, and “deep dive” action.
- **Stocks/Crypto Pulse**:
  - Real‑time quotes + volatility + regime hints.
- **Stock Heatmap (Option A: embed-first)**:
  - v1: embedded heatmap widget behind `V3_HEATMAP_EMBED` (parity, fast, zero licensing/constituent complexity in-house).
  - Must expose only two actions: **Examine this mover** / **Monitor this ticker/sector**.
  - v2: first‑party provider-backed heatmap once WS0 identifiers + WS5 markets connector are stable.
- **Prediction Markets**:
  - Polymarket odds + drift alerts + “why odds moved” evidence.
- **Tech layoffs tracker**:
  - Layoffs.fyi feed + sector stress scoring.
- **AI Race news**:
  - arXiv + official announcements + curated “capability deltas”.
- **“Is the Fed printer on?” Liquidity Panel**:
  - Fed balance sheet + repo/RRP + TGA proxies + M2 trend, distilled into one signal.
- **Country dossiers (e.g., Venezuela + Greenland)**:
  - Region pages with “what changed since last week”, key risks, and watches.

#### Leapfrog modules (what your rival cannot easily copy)
- **Examine X → Consolidated Predictive Report** (WS4): evidence‑first, citeable, uncertainty‑explicit.
- **AI‑generated panels/plugins in‑app** (WS8): prompt → safe ModuleSpec → preview/approve → deploy/version/share.
- **Scenario campaigns** (WS10): COD‑style mission chains with branching outcomes and monitors.
- **Spice must flow overlays + attractor states** (WS9): flows + geopower dynamics rendered on the map with explainability.
- **Bias detection + counter‑view surfacing**: source diversity, narrative disagreement, and “what you’re not seeing”.

#### Default Command Center layout (UX baseline)
- **Top 60%**: Global Activity Monitor map with layer toggles + “Updated at” timestamp + refresh.
- **Bottom 40%**: draggable modules row:
  - Livestream Desk, Intel Feed, Markets/Crypto, Prediction Markets, Reports.

---

### 2) V3 Architecture (professional, scalable, safe)
**Principle**: Versioned contracts + server‑authoritative state + isolated workstreams.

#### 2.1 Planes (how the system is separated)
- **UI Plane**: React UI (existing look), module rendering, feature flags, optimistic UX.
- **API Plane**: versioned endpoints (`/api/v3/*`) with streaming where needed.
- **Data Plane**: canonical store (Postgres target), plus search/indexing (FTS + embeddings).
- **Execution Plane**: job runner/queue for investigations, monitors, ingest, scoring.
- **Tool/Connector Plane**: typed connectors (news, markets, datasets, telegram) + governed “tool execution”.
- **Observability Plane**: structured logs + metrics + traces per workflow.

#### 2.2 Canonical entities (what we persist and render)
- **IntelItem**: normalized item from any feed (news/telegram/market/event/dataset).
- **Evidence**: raw payload + normalized fields + provenance + timestamps.
- **Entity**: canonical identity with stable IDs (**V1 scope**: tickers, countries, sanctions targets; **later**: orgs/people as governed sources exist).
- **Identifier / Alias**: mappings for tickers/ISIN/CIK/domain/name variants → `Entity` (plus confidence + source).
- **Investigation**: user‑initiated “Examine X” mission (scope, timebox, status).
- **AgentRun / Step / ToolCall**: replayable run details + budgets + safety tags.
- **Report**: consolidated intelligence report with predictions + uncertainty + citations.
- **AlertRule**: user triggers (odds drift, narrative spikes, macro prints, etc.).
- **ModuleSpec**: declarative module definition (data source = connector reference).

---

### 3) Parallelization Rules (how we avoid conflicts)
#### 3.1 One contract owner
- Only **Workstream WS0** edits canonical schemas/contracts.
- All other workstreams consume those interfaces; if they need changes, they submit a request to WS0.

#### 3.2 File ownership boundaries
Each workstream owns a dedicated directory slice (or clearly named files). Avoid “everyone edits App.tsx / Dashboard.tsx”.

#### 3.3 Feature flags everywhere
- Every new surface is behind a flag: `V3_*`.
- Flags default off; we can deploy safely without breaking the current UI.

#### 3.4 Merge discipline
- Parallel work is fine, but **merge order is sequential** (WS0 → WS1 → WS2…).
- Acceptance criteria must be met before merging.

#### 3.5 Repo governance (non-negotiable)
- **Auto-merge**: disabled by default; only enable auto-merge when **CI + required approvals + CodeRabbit are green** (low-risk PRs only).
- **Protected `master`**:
  - no direct pushes
  - PR required + CI green + (at least) 1 approval
- **One PR = one workstream slice**: never mix infra + frontend animation + categorization fixes in one PR.
- **Branch naming**: `ws0/*`, `ws1/*`, `ws3/*`, `ws4/*`, `infra/*`, `docs/*`, `fix/*`.
- **Enforcement**: these rules are enforced via GitHub **branch protection** + required checks + reviewer approval (verify in repo settings once, then treat as locked).

#### 3.6 Staging discipline (do not break prod)
- **Staging is Cloudflare Access-gated** (Zero Trust → Access) and must present a login wall.
- **Origin is Cloudflare-only**: staging origin vhost denies non-Cloudflare source IPs (prevents bypassing Access via direct IP).
- **Service isolation**:
  - staging backend uses its own unit + port + DB snapshot (already `watchfuleye-backend-staging`, `127.0.0.1:5004`)
  - staging frontend uses its own unit + port + build directory (avoid sharing `/opt/.../frontend/build` with prod)
- **Deploy order**: staging first → validate → only then promote to prod when explicitly approved.

#### 3.7 Review + shipping discipline (CodeRabbit-first, fast, auditable)
**Goal**: PRs should be “merge-ready” on first open. We shift review left (CLI), but keep PRs for auditability + CI gating.

- **Local preflight (required before every push)**:
  - Run the relevant linters/typechecks/tests for the touched area.
- **PR hygiene (required)**:
  - Fill the PR template sections (briefly). Empty template sections are a merge blocker.
  - One PR = one workstream slice.
  - Include rollback (usually: flip flag off).
- **Auto-merge policy**:
  - Allowed only if: CI green + required approvals + CodeRabbit addressed + branch protection enforced.
  - If any check is flaky: disable auto-merge and fix the check first (CI reliability is WS0).

##### CodeRabbit (PR-only; no local pre-push gate)
- CodeRabbit runs on **pull requests** via the GitHub app/checks.
- We do **not** block pushes on CodeRabbit CLI auth (headless servers commonly fail secure credential storage).
- Watching without email:
  - Use `python3 scripts/dev/watch_coderabbit_pr.py <owner> <repo> <pr_number> --interval 60`
  - Or ask the Cursor agent: “check PR #N CodeRabbit” (agent will fetch via GitHub MCP).

---

### 3.8 Master handoff prompt (EXTREMELY DETAILED; paste into new agent chats)

Copy/paste everything below into a brand‑new agent chat so the agent has **zero ambiguity** about what to do, what not to do, and how to deploy safely.

```text
YOU ARE OPERATING INSIDE WATCHFULEYE. PRIME DIRECTIVE: Ship V3 without breaking existing production UI/surfaces.

Authoritative plan: WATCHFULEYE_V3_MASTER_PLAN.md (this file). Do not invent new architecture outside it.

Non‑negotiable existing surfaces (NEVER regress/remove):
- Main News Feed
- Custom News Feed
- Telegram Intel Reports
- Intel Reports
- AI Analysis Modal

Workstream discipline:
- One branch/PR = exactly one workstream slice (WS0..WS12).
- WS0 owns contracts/schemas. If you need a contract change, do it as WS0 (separate PR) or request it.
- New features must be behind flags `V3_*` and default OFF.

Repo discipline:
- No direct pushes to master.
- CI green required.
- CodeRabbit runs PR‑only (no local pre‑push gate).
- Auto‑merge disabled by default; only enable when CI + approvals + CodeRabbit are green for low‑risk diffs.

Two working directories (DO NOT MIX):
1) DEV workspace (feature work): /opt/watchfuleye2
   - You create branches here.
   - You never deploy staging from here.
   - Note: `master` is checked out in the staging worktree, so create branches from `origin/master`.
2) STAGING deploy worktree (master-only): /opt/watchfuleye2-staging
   - This worktree must stay on origin/master.
   - You deploy staging from here only.

Safe staging deploy commands (run ONLY in /opt/watchfuleye2-staging):
- git pull --ff-only origin master
- sudo systemctl restart watchfuleye-backend-staging
- sudo systemctl restart watchfuleye-frontend-staging

How master evolves:
- Feature work merges into master via PRs (sequential order, one slice at a time).
- Staging is always “whatever is currently on origin/master”, pulled into the staging worktree.
- If a feature is behind a flag, merging to master does NOT turn it on; staging enables flags explicitly via service env/config.

What “next step” means in this repo:
- Identify the next workstream slice from this plan.
- Implement it behind a flag with tests.
- Push a branch, open PR, resolve CodeRabbit + CI, then merge.
- After merge: deploy to staging via the worktree; enable flag(s) in staging; validate.

CURRENT STATE (as of this chat):
- WS0 entity resolution API exists:
  - Endpoint: POST /api/v3/entities/resolve
  - Flag gate: V3_ENTITY_IDS (default OFF)
  - Behavior (flag ON): attempts exact match resolution in Postgres; never hard-fails app if Postgres missing.
- Postgres schema includes WS0 entity tables:
  - entities
  - entity_identifiers
  - entity_aliases
  - entity_same_as_edges
- Staging seeding (WS0.5) exists as an **operator tool** (not on request paths):
  - `python -m watchfuleye.v3.seed_entities --pg-dsn "$PG_DSN"`
  - Seeds ISO-3166 from vendored JSON + OFAC SDN from official SDN CSV (downloaded + cached + provenance recorded)
- On this server, staging backend should run from the staging worktree:
  - `systemctl cat watchfuleye-backend-staging.service` should show `WorkingDirectory=/opt/watchfuleye2-staging`

CURRENT NEXT SLICE (execute this first unless told otherwise):
- WS4.0 “Examine X” MVP skeleton (flagged): create the minimal investigation/run loop that produces a consolidated report (even if v1 uses existing news/RAG as evidence).

Acceptance criteria for WS4.0:
- Flagged endpoint exists (default OFF) and cannot break V1:
  - Suggested: `V3_EXAMINE_MVP` and `POST /api/v3/examine`
- When flag OFF: endpoint is hidden (404).
- When flag ON: endpoint returns a stable investigation id + trace id, and produces a minimal report payload (even if first version is stubbed).
- Tests exist for flag OFF/ON behavior.
- Rollback is “flag OFF” (no user-visible regression when OFF).

Operational verification steps for agent:
1) Confirm you are in DEV workspace (/opt/watchfuleye2) before coding.
2) Confirm git status is clean before creating a branch.
3) Create a correctly named branch from origin/master:
   - git fetch origin master && git checkout -b wsX/<slice> origin/master
4) Implement changes + add/adjust tests.
5) Commit with a clear message (scope prefix recommended).
6) Push branch and open PR using template; fill required sections (Intent, owned files, flags, verification, rollback).
7) Check PR for:
   - CI checks (backend + frontend)
   - CodeRabbit comments (resolve or explicitly justify)
8) Merge only when green + reviewed.
9) Deploy staging only from /opt/watchfuleye2-staging via ff-only pull + systemctl restarts.
10) Enable flags only in staging service env/config; validate endpoints.

Safety constraints:
- No secrets in repo.
- No scraping without governance.
- All “intel claims” must remain evidence-first and auditable.
```

---

### 3.9 Low-credit agent mode (when you need “lesser agents”)

If you are low on credits, run agents in **low-credit mode**: smaller slices, fewer tool calls, and strict stop conditions.

#### Low-credit mode rules (for the agent)
- **Scope**: one micro-task only (1–2 files, or ≤150 LOC touched).
- **Stop condition**: if the task expands beyond the owned paths or requires WS0 contracts, stop and ask for confirmation.
- **No broad refactors**: no “cleanup”, no reformatting, no drive-by dependency bumps.
- **No hot files unless required**: `web_app.py`, `watchfuleye/storage/postgres_schema.py`, `.github/workflows/ci.yml`, `frontend/src/App.tsx`.
- **Verification**:
  - run exactly one targeted test/command for the slice (not a full suite)
  - include a single curl/smoke check command if it’s an API surface
- **Deliverable**: a PR with a filled template and a short rollback note.

#### What to give the agent (copy/paste)
- The “Master handoff prompt” (3.8)
- The slice name + owned paths + explicit NOT-touched paths
- The acceptance criteria (3 bullets max)
- The exact commands to run (start branch, run one test, push, open PR)
- Full prompt template (recommended): `docs/V3_LOW_CREDIT_AGENT_MODE.md`

### 4) Workstreams (modular steps you can run as separate coding‑agent chats)
Each workstream below is designed to be **independently implemented** with minimal overlap.

#### Workstream execution playbook (parallel-safe)
See `docs/V3_WORKSTREAM_EXECUTION_PLAYBOOK.md` for:
- branch creation (worktree-aware)
- owned paths map (backend + frontend)
- “hot files” list
- slice checklist (flags, tests, rollback, staging verify)

#### WS0 — V3 Contracts + Safety Envelope (MUST DO FIRST)
- **Why**: without stable interfaces, parallel work will collide.
- **Delivers**:
  - `/api/v3/*` endpoint map + request/response schemas.
  - Canonical DB schema for IntelItem/Evidence/Investigation/Report/AlertRule/ModuleSpec.
  - **Entity Resolution + Identifiers (contract-level dependency)**:
    - Schemas:
      - `Entity` (canonical identity)
      - `EntityIdentifier` (ticker/ISIN/CIK/ISO codes → entity)
      - `EntityAlias` (name variants/aliases → entity)
    - **Resolver contract** (single, explicit surface):
      - `POST /api/v3/entities/resolve`
      - request: `{ "q": string, "k": number=10, "types": ["ticker"|"org"|"country"|"sanctions_target"] }`
      - response: `{ "matches": [{ "entity_id": string, "entity_type": string, "label": string, "confidence": number(0..1), "provenance": {...} }], "trace_id": string }`
    - **Confidence**:
      - numeric \(0..1\)
      - computed as: `confidence = base_source_weight * string_sim * type_consistency`
        - `base_source_weight`: 1.0 for authoritative lists (OFAC/ISO), 0.7 for market data providers, 0.5 for extracted-from-text
        - `string_sim`: normalized string similarity (e.g., Jaro-Winkler/Levenshtein ratio) with explicit default thresholds (configurable per `entity_type`)
          - default thresholds:
            - **0.90** for exact/normalized identifiers
            - **0.80** for tickers/symbols
            - **0.75** for fuzzy/name matches
        - `type_consistency`: 1.0 if identifier type matches entity type, else 0.0
    - **Provenance fields (returned on every match / stored on identifiers+aliases)**:
      - `source_system` (e.g., `ofac_sdn`, `iso3166`, `provider_markets`)
      - `source_record_id` (the upstream identifier if available)
      - `ingest_timestamp` (UTC ISO)
      - `match_algorithm` (e.g., `exact`, `normalized_exact`, `fuzzy_jw`, `manual`)
      - `match_inputs` (normalized query + any parsed tokens)
      - `curator_id` (nullable; set if a human overrides/merges)
    - **Same-as linking semantics (dedupe without losing auditability)**:
      - default: **link**, don’t merge (store `same_as` edges) unless confidence is high
      - merge only when:
        - authoritative identifier collision (same CIK/ISIN/OFAC id), OR
        - confidence ≥ 0.95 and no conflicting authoritative identifiers
      - conflicts: keep separate entities + create a `same_as` link marked `conflicted=true`
      - audit trail: every merge/link/unlink is an append-only event with `who/when/why`
  - Event schema for structured logs (`event_type`, `workflow_id`, `latency_ms`, `user_id`, `trace_id`).
  - Budgets for agent runs (max steps, max tool calls, max time).
- **Owns**:
  - `contracts/` (new) + `db/migrations/` (new) + `docs/V3_CONTRACTS.md` (new).
- **Feature flags**:
  - `V3_API_ENABLED`, `V3_AUDIT_LOGS`.
  - `V3_ENTITY_IDS` (planned in WS0: gates Entity/Identifier/Alias APIs; default OFF in prod)
  - `V3_HEATMAP_EMBED` (planned in WS0: enables embedded heatmap panel v1; default OFF in prod; used by WS7 modules)
- **Acceptance**:
  - Contract docs exist, schemas compile, no production endpoints broken.
  - Coverage (minimum viable, explicit):
    - **Tickers**: top **5,000** US equities by liquidity/market cap (ingested from a single chosen provider list)
    - **Countries**: ISO-3166 country codes + common names
    - **Sanctions**: OFAC SDN (and one consolidated sanctions list source, e.g. EU/UK/UN as available)
  - Resolver behavior:
    - returns **k** matches sorted by confidence
    - returns confidence \(0..1\) + provenance object on every match
    - enforces dedupe rules (exact id collisions collapse to 1; otherwise same-as links)
  - Same-as semantics:
    - merges are audited; links are reversible; conflicts never silently overwrite authoritative identifiers.

#### WS1 — Main News Feed (Global Briefing) — Preserve + Professionalize
- **Goal**: keep the existing main feed experience, but make the data plane authoritative.
- **Delivers**:
  - Ingestion pipeline for primary news sources (licensed + open feeds).
  - Dedupe + clustering + ranking (“narrative velocity” optional later).
  - `/api/v3/news/main` (list/search/filter) + `/api/v3/news/item/:id` (detail).
- **Owns**:
  - `watchfuleye/v3/feeds/news/*` (new) + feed storage tables
  - Integration touchpoints (hot; only if required): `news_ingest_worker.py`, `fulltext_worker.py`
- **Flags**:
  - `V3_MAIN_FEED`.
- **Acceptance**:
  - Main feed renders from `/api/v3/news/main` with pagination + search.

#### WS1.1 — Intelligence Reports v2 (Curation + Differentiation)
- **Goal**: make reports feel **non-generic** and operationally useful (they should not read like the same template every time).
- **Why (current weakness)**:
  - The UI previews are mostly `content_preview`/first-line extraction; if the model prompt is stable, the outputs converge.
  - There is no explicit **“what changed since last report”** constraint or novelty gating.
- **Delivers**:
  - A **Report Spec** that forces differentiation:
    - **Delta-first**: “What changed since last cycle” (top 3 deltas with evidence IDs)
    - **Thesis**: 1 central causal model (mechanism → transmission → second-order effects)
    - **Predictions**: 3–5 forecast claims with probabilities + horizons + “what would change my mind”
    - **Actionability**: concrete monitors + triggers + hedges (or “no trade” explicitly)
    - **Evidence**: citations required for each major claim; missing-data section mandatory
  - A **Curation Engine** for geopolitical intel:
    - Cluster articles into narratives (entity + embedding + time)
    - Select a diversified set (regions/sectors/sources) rather than “top N by recency”
    - Anti-dup: block near-identical reports using embedding similarity against prior reports
  - A **Quality Gate**:
    - minimum evidence density
    - minimum novelty vs previous N reports
    - minimum actionable monitors per report (or explicit reason for none)
- **Owns**:
  - `watchfuleye/v3/reports/*` (new) + report prompt/spec + curation logic
- **Flags**:
  - `V3_REPORTS_V2`
- **Acceptance**:
  - Two consecutive reports must differ meaningfully (measurable novelty) and each must include deltas + forecast claims + monitors.
  - The existing “Global Brief” section layout remains available as the default view (no regressions); new views are additive.

#### WS1.2 — AI Analysis Modal v2 (Make it a king, no regressions)
- **Goal**: keep the current AI analysis modal experience, but upgrade depth, citations, and usefulness.
- **Delivers**:
  - Preserve current modal behaviors:
    - fast open, streaming analysis, structured sections, “send to chat”, copy/export
    - political perspectives panel (kept, improved)
  - Additions (behind flags):
    - citations from RAG evidence (InlineCitationCard/SourcesHoverChip)
    - “delta since last analysis” for the same topic/entity
    - explicit confidence + dissent + “what would change my mind”
- **Flags**:
  - `V3_ANALYSIS_MODAL_V2`
- **Acceptance**:
  - Users who love the current modal should feel it’s the same modal—just sharper and more trustworthy.

#### WS2 — Custom News Feed (My Wire) — User Personalization
- **Goal**: user topics/watchlists/saved searches, backed by server state.
- **Delivers**:
  - Topic model + saved searches.
  - `/api/v3/news/custom` and `/api/v3/topics/*`.
  - Optional: per-topic scoring + alert hooks.
- **Owns**:
  - `watchfuleye/v3/feeds/custom/*` (new) + DB tables for topics and subscriptions
- **Flags**:
  - `V3_CUSTOM_FEED`.
- **Acceptance**:
  - User can create a topic and see a stable custom feed; survives refresh/device change.

#### WS3 — Telegram Intel Reports (First‑Class)
- **Goal**: Telegram remains a first‑class intel stream, not an afterthought.
- **Delivers**:
  - Telegram ingest → `IntelItem(type=telegram)` + `Evidence`.
  - `/api/v3/telegram/reports` (digests) + `/api/v3/telegram/messages` (raw).
  - Citations: reports can cite telegram evidence IDs.
- **Owns**:
  - `watchfuleye/v3/telegram_feed/*` (new) + bot pipeline integration
  - Integration touchpoints (hot; only if required): `main.py`
- **Flags**:
  - `V3_TELEGRAM_FEED`.
- **Acceptance**:
  - Telegram reports show in UI; raw message is retrievable and citeable.

#### WS3.1 — Two‑Way Telegram Agent (Conversational RAG → Investigations → Monitors)
- **Goal**: Telegram becomes an operator console: ask naturally, get fast citeable answers, and one‑tap into the full dossier on the site.
- **Important constraint**: We do **not** ship dark patterns or covert manipulation. “Hooks” must be **value‑driven and transparent** (quick answer here; deeper work on the site).
- **Delivers**:
  - **Inbound** (DMs / allowlisted group chats):
    - Commands: `/examine <topic>`, `/monitor <topic>`, `/brief`, `/sources`, `/status`
    - Natural language fallback: “what’s up with X?” → treated as `/examine X`
  - **Agent modes**:
    - **Fast RAG reply** (seconds): embeddings + FTS retrieval → 5‑bullet answer + citations
    - **Escalation** (agentic): “go deeper” → create `Investigation` (WS4) and stream updates back to Telegram
    - **Monitoring**: “watch this” → create alert rules (WS6) and confirm in Telegram
  - **Don’t overload the user**:
    - Default replies are concise (5 bullets max + citations).
    - Extra detail is opt‑in via buttons (“Show more”, “Sources”, “Red‑team”) or explicit prompts.
    - Optional per-user verbosity setting (brief vs operator mode).
  - **Deep links (ethical traffic driver)**:
    - Every Telegram answer includes a single explicit link: **“Open full dossier on dashboard”**
    - Link format: `/dashboard?examine=<query>&origin=telegram` (or equivalent) to pre‑load context
  - **Operator‑grade presentation hooks (transparent, not manipulative)**:
    - “Delta‑first”: what changed since last cycle for this topic
    - “Confidence + dissent”: show confidence and best counter‑case
    - “Next actions”: one‑tap buttons (Open dossier / Monitor / Sources / Red‑team)
  - **Security + abuse controls**:
    - Allowlist chat IDs / user tokens; rate limits; audit logs for every command
    - Prompt‑injection defense: strict tool gating; evidence‑only answers when in RAG mode
    - Cost/latency budgets per request; graceful fallback to “fast reply only”
- **Owns**:
  - `watchfuleye/v3/telegram_agent/*` (new) + webhook/poller integration
  - Minimal UI deep-link handler in dashboard (`origin=telegram`)
- **Flags**:
  - `V3_TELEGRAM_AGENT`, `V3_TELEGRAM_INBOUND`, `V3_TELEGRAM_DEEPLINKS`
- **Acceptance**:
  - A user can DM: “Examine Venezuela” → receive a citeable brief in <10s.
  - One tap opens a pre‑filled dossier on the site.
  - “Monitor this” creates a real alert rule and confirms it.

#### WS4 — Investigations (“Examine X”) + Consolidated Report Output (Core Loop)
- **Goal**: the terminal input triggers a real mission with evidence + predictions.
- **Hard dependency**: WS0 identifiers/entity-resolution must exist so investigations don’t fragment (“same entity” across sources).
- **Delivers**:
  - `/api/v3/investigations` create/run/status + `/api/v3/reports/:id`.
  - Agent planner → evidence pack → synthesis → red‑team check → final report.
  - Streaming updates for progress (SSE/WebSocket).
- **Owns**:
  - `watchfuleye/v3/investigations/*` + job runner integration.
- **Flags**:
  - `V3_INVESTIGATIONS`, `V3_REPORTS`.
- **Acceptance**:
  - “Examine X” produces a report with citations and explicit uncertainty.

#### WS5 — Connectors Registry (Expanded Data Sources, Governed)
- **Goal**: make “scan across all sources” precise, safe, and composable.
- **Delivers**:
  - Connector registry with typed capabilities, rate limits, caching, compliance tags.
  - Connector tiers (to keep scope sharp and quality high):
    - **Tier A (ship first: low‑risk, high‑leverage)**:
      - **Markets**: Yahoo Finance / Alpha Vantage (plus a fallback source if one fails)
      - **Crypto**: CoinGecko / CoinMarketCap
      - **Prediction markets**: Polymarket (and optionally Kalshi later)
      - **Macro**: FRED (plus key central‑bank calendars/announcements as feeds)
      - **Liquidity (“Fed printer”)**: Fed H.4.1 balance sheet, NY Fed repo/RRP, TGA proxies (via FRED where possible)
      - **Disasters**: USGS (plus GDACS/NOAA later if needed)
      - **Conflict/events**: ACLED + UN public reporting (optionally UCDP later)
      - **Supply chain/resources**: EIA + WTO (optionally UN Comtrade later)
      - **Telegram**: handled in WS3, but exposed via the same connector interface for investigations
      - **Open global events/news index (fallback + geo‑tagging)**: GDELT (or equivalent open event graph)
      - **Sanctions/regulatory (critical for “Iran sanctions”‑class queries)**: OFAC SDN + EU/UK/UN sanctions lists
      - **Corporate filings/official docs**: SEC EDGAR + press releases / official statements feeds
      - **Cyber advisories (safe intel feed)**: CISA alerts/advisories + vendor security advisories (as Evidence)
      - **Tech layoffs**: layoffs.fyi (optional but high signal for sector stress)
    - **Tier B (non‑standard signals: big upside, medium complexity)**:
      - **Social/narrative signals**: X/Reddit/YouTube (via compliant APIs/feeds), with bias + brigading defenses
      - **Social sentiment ingestion tool (optional)**: Phantombuster (job-driven scraping/collection) → treated as a governed connector with strict terms-of-service and rate limits
      - **Trends**: Wikipedia pageviews + Google Trends‑style interest proxies
      - **Livestream intel**: TBPN (store metadata + transcripts as Evidence)
      - **Geo mobility**: maritime AIS + flight ADS‑B (where licensed/allowed)
      - **Satellite/public earth observation**: Sentinel/NASA feeds for verification overlays
      - **Weather/climate disruption**: NOAA storms + NASA FIRMS (wildfires) for supply chain and energy shock overlays
      - **Shipping/port stress**: container indices / port congestion / freight rates (for chokepoint monitoring)
      - **Policy/legislation trackers**: US/EU/UK public bill trackers + regulator updates (as feeds)
    - **Tier C (gated / high‑risk / enterprise)**:
      - **Asset exposure intel**: Censys/Shodan → **authorized targets only**
      - **Threat intel + vuln feeds**: CISA KEV / NVD CVE (safe), but any “active testing” is gated/off by default
      - **PII/recon tools**: **off by default**; only via explicit governance if ever added
  - High‑risk classes are gated by default:
    - “Asset exposure / scanning” (Censys/Shodan) → **authorized targets only**
    - PII/recon tools → **off by default**
- **Owns**:
  - `watchfuleye/v3/connectors/*` + caching layer.
- **Flags**:
  - `V3_CONNECTORS`, `V3_HIGH_RISK_CONNECTORS`.
- **Acceptance**:
  - Investigation planner can call connectors deterministically based on query intent.

#### WS6 — Alerts + Monitoring (Retention Engine)
- **Goal**: turn investigations into ongoing monitoring; automate notifications.
- **Delivers**:
  - Alert rules engine + scheduler.
  - Triggers: odds drift, narrative spike, macro print, earthquake threshold, conflict escalation.
  - Notification channels: in‑app + Telegram + email (if configured).
- **Owns**:
  - `watchfuleye/v3/alerts/*` + worker/scheduler.
- **Flags**:
  - `V3_ALERTS`.
- **Acceptance**:
  - A user sets an alert; system fires it with evidence and a short explanation.

#### WS6.1 — Forecast Accountability (Track predictions vs outcomes)
- **Goal**: measure what we produce against what actually happens (no self-delusion).
- **Delivers**:
  - Persist every forecast from investigations/reports as a `Forecast` object:
    - claim, probability, horizon, entities, assumptions, evidence_ids, created_at
  - Outcome tracking jobs:
    - market outcomes (price moves), event outcomes (e.g., sanctions added), odds outcomes (Polymarket resolution)
  - Scoring + calibration:
    - Brier score, calibration curves, hit rate by horizon, “confidence vs accuracy”
  - UX surfaces:
    - “Track record” panel + per-report “how past forecasts performed”
- **Owns**:
  - `watchfuleye/v3/forecast/*` (new) + DB tables (in WS0 schema)
- **Flags**:
  - `V3_FORECAST_TRACKING`
- **Acceptance**:
  - Any forecast shown to users can be found later in a track record view with outcome status.

#### WS7 — Modular Panels v2 (ModuleSpec + Server‑Backed, No Client Secrets)
- **Goal**: keep the draggable dashboard UX, but make modules real and safe.
- **Delivers**:
  - `ModuleSpec` schema + server persistence.
  - Module catalog wired to server connectors (no raw endpoint/headers in client).
  - User layouts saved server‑side.
  - Baseline Parity Pack modules implemented as first‑class ModuleSpecs (map, livestream, intel feed, markets, polymarket, layoffs, AI race, liquidity, dossiers).
  - **Baseline parity embed allowance**:
    - panels may embed a data surface in v1, but must still use server-backed state (layout/pin/preferences)
    - embeds must still route actions through the core verbs (**Examine**, **Monitor**) so they feed WS4/WS6
- **Owns**:
  - `watchfuleye/v3/modules/*` (new) + `/api/v3/modules/*`
  - `frontend/src/v3/modules/*` (new)
- **Flags**:
  - `V3_MODULES`.
- **Acceptance**:
  - Add/remove modules with no dead controls; layout persists across sessions.
  - **Embed constraints (enforced)**:
    - Layout + pins + user preferences are persisted **server-side** (no client-only `localStorage` as source of truth).
    - Any user action inside an embed routes through **Examine**/**Monitor** and is logged (WS4 investigations feed-through + WS6 alert determinism).
    - Embeds may not make raw, ungoverned client-side data calls. Data must come from **WS5 connector surfaces** (rate limits + compliance tags + Tier A/B approval), OR the embed is a sandboxed third-party surface with **no client secrets** and clearly treated as “display-only” (actions still route through Examine/Monitor).

#### WS8 — AI Panel Builder + Panel Store (Your Differentiator)
- **Goal**: “Create a panel for Iran sanctions” → generated module spec + preview + deploy.
- **Delivers**:
  - Prompt → ModuleSpec proposal → preview → approve → deploy → versioning.
  - Panel Store: share modules; moderation rules; compatibility checks.
- **Owns**:
  - `watchfuleye/v3/panel_builder/*` (new)
  - `frontend/src/v3/panel_store/*` (new)
- **Flags**:
  - `V3_PANEL_BUILDER`, `V3_PANEL_STORE`.
- **Acceptance**:
  - Generated panel uses connectors safely and renders in dashboard.

#### WS9 — Map Overlays (Spice Flows + Attractor States + Search)
- **Goal**: map becomes an intelligence canvas (layers like a weather app).
- **Delivers**:
  - Map search + clickable event clusters.
  - “Spice must flow” overlays (resource/trade/influence flows).
  - “Attractor state” geopower visualization (graph‑derived metrics).
  - Country/region dossiers surfaced from map context (e.g., Venezuela, Greenland) with “Examine” + “Monitor”.
- **Owns**:
  - `watchfuleye/v3/map_layers/*` (new)
  - `frontend/src/v3/map_layers/*` (new)
- **Flags**:
  - `V3_MAP_LAYERS`.
- **Acceptance**:
  - Layers can be toggled, are explainable, and cite their sources.

#### WS10 — Campaign Generator (COD‑style missions)
- **Goal**: investigations become scenario chains with branching outcomes.
- **Delivers**:
  - Scenario templates + simulation hooks + report outputs.
  - Replay + “what would change my mind?” conditions.
- **Flags**:
  - `V3_CAMPAIGNS`.

#### WS11 — Multi‑Display / Large Screen (Operational Setup)
- **Goal**: command center works on TVs and multi‑monitor walls.
- **Delivers**:
  - Responsive layout modes + synchronized views + “presentation lock”.
- **Flags**:
  - `V3_MULTIDISPLAY`.

#### WS12 — Optional Immersion (VR/AR)
- **Goal**: only after everything above is addictive‑by‑necessity.
- **Flags**:
  - `V3_IMMERSIVE`.

---

### 5) “Don’t Kill the Site” Rollout Strategy
- **Dual‑stack APIs**: keep existing endpoints; introduce `/api/v3/*` alongside.
- **Feature flags**: UI flips module‑by‑module, not page‑by‑page.
- **Progressive replacement**:
  - First replace data sources under existing UI (feeds, telegram).
  - Then enable investigations and reports behind flags.
  - Then migrate modules and custom builder away from client endpoints.

---

### 6) Quality Gates (when a workstream is “done”)
- **E2E happy path** for the feature (including search/indexing where relevant).
- **Failure modes**: timeouts, missing sources, rate limits, partial results.
- **Security**: no secrets in client; gated high‑risk connectors; audit logs.
- **Observability**: structured events + latency; ability to replay investigations.
- **Forecast evaluation** (where applicable): predictions must be stored and scored later (Brier/calibration) before we claim “accuracy”.

---

### 7) Sentiment (Fix the current flawed approach)
Current sentiment distribution is **known to be unreliable** and should not be trusted as “market truth”.

V3 approach:
- **Separate two concepts**:
  - **Article tone** (how the writing sounds)
  - **Market impact sentiment** (bullish/bearish implications)
- **Use multiple signals**:
  - news-based impact scoring (source trust + recency + evidence weight)
  - market data confirmation (price/vol/regime)
  - **optional** social sentiment (governed connectors; anti-brigading; confidence gating)
- **Always show confidence + method** (and allow the user to toggle the feature off).

---

### 8) Report Quality (how we stop “generic” output)
**Definition**: A report is “powerful” only if it changes an operator’s decision-making.

Quality constraints we enforce:
- **Delta requirement**: must state what changed since last cycle (and cite it).
- **Forecast requirement**: at least 3 explicit probabilistic claims (or explain why forecasting is inappropriate).
- **Evidence requirement**: every major claim must cite evidence IDs (no free-floating assertions).
- **Dissent requirement**: at least one counter-case / disconfirming evidence.
- **Uniqueness requirement**: embedding similarity against prior reports must be below a threshold, or the report is rejected/regenerated.

### Rigid Self‑Check
- **Why this?** It’s the minimum structure that lets multiple agents build in parallel without conflict while preserving the current UI.
- **What does it change?** Ad hoc feature building → contract‑driven, flagged rollout with isolated ownership.
- **Humanity Furtherance**: **+1** — safer, clearer intelligence synthesis at scale.
- **First‑Principles Trace (load-bearing)**:
  - Stable contracts prevent collision.
  - Server authority prevents trust collapse.
  - Evidence + uncertainty prevent “fake intelligence”.
- **Next Bold Variant**: Map selection auto‑spawns an “Examine region” investigation plan (connectors + hypotheses) with one click.


