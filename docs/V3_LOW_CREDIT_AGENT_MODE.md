## Intent
Allow WatchfulEye V3 to keep shipping even if you have to use **lower-quality agents** (or you run low on credits).

This doc defines a strict “safe mode” where agents can only execute small, contract-first slices with minimal ambiguity.

## Core idea
When agent capability is limited, we win by:
- **Shrinking slices** (smaller PRs)
- **Hardening contracts** (WS0 does interfaces; others consume them)
- **Reducing hot-file edits** (avoid merge conflicts)
- **Enforcing checklists** (no “creative guessing”)

## Safety rules (non-negotiable)
- One PR = one slice (one workstream).
- Flags default OFF. No new surface ships without a `V3_*` flag.
- Do not touch hot files unless explicitly allowed in the prompt.
- If something is unclear, stop and ask the verifier (Oli/you).

## Allowed task types for low-credit agents
Pick tasks that are deterministic and bounded:
- Add a new V3 endpoint **stub** behind a flag (WS0 only).
- Add tests that lock in response shape / flag behavior.
- Add a connector skeleton that returns **empty** results + logging (WS5).
- Add a UI component behind a flag that renders mock data (WS7/WS1) **without removing V1 UI**.
- Improve docs/playbooks/templates (docs/*).

Avoid tasks requiring deep refactors, concurrency, or multi-module architecture decisions.

## “Slice prompt template” (copy/paste)
Use this template verbatim when instructing a low-credit agent:

```text
Workstream: WSX.Y (single slice only)

Owned paths (ONLY edit these):
- <path1>
- <path2>

Explicitly do NOT touch:
- web_app.py
- watchfuleye/storage/postgres_schema.py
- .github/workflows/ci.yml
- frontend/src/App.tsx
- any other file not listed above

Flags:
- Add/Use: V3_<FLAG_NAME> (default OFF)

Contracts:
- If contract/schema needed: STOP and ask verifier (WS0 owns contracts).

Acceptance criteria:
- Exact endpoint(s)/UI behavior:
  - When flag OFF: returns 404 / hidden
  - When flag ON: returns 200 with exact JSON keys: [...]
- Tests added/updated: <tests and what they assert>
- Rollback: flag OFF (no regression)

Commands (run exactly):
- git status --porcelain
- <test commands>

Deliverable:
- One commit, one PR, fill PR template sections.
```

## Verifier workflow (you = judge/connector)
When low-credit agents finish a slice:
- You (verifier) run the “merge gate”:
  - CI green
  - CodeRabbit addressed or clearly non-blocking
  - slice obeys owned paths + flags
- Then you merge and deploy to staging via the worktree.


