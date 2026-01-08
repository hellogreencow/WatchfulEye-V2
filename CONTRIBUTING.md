## Contributing to WatchfulEye (V3 build discipline)

### Goals
- Preserve the current product experience while we upgrade the data + agent planes.
- Avoid parallel work collisions by enforcing contracts, ownership, and feature flags.

### Branching
- **One workstream per branch**.
- Branch name format:
  - `ws0-contracts/<short-slug>`
  - `ws1-main-feed/<short-slug>`
  - `ws2-custom-feed/<short-slug>`
  - `ws3-telegram/<short-slug>`
  - `ws4-investigations/<short-slug>`
  - `ws5-connectors/<short-slug>`
  - `ws6-alerts/<short-slug>`
  - `ws6-1-forecasting/<short-slug>`
  - `ws7-modules/<short-slug>`
  - `ws8-panel-builder/<short-slug>`
  - `ws9-map/<short-slug>`
  - `ws10-campaigns/<short-slug>`

### Commits (keep history readable)
- Use conventional commits:
  - `feat(wsX): ...`
  - `fix(wsX): ...`
  - `chore(wsX): ...`
  - `docs: ...`
- Keep PRs small: prefer multiple PRs over one monster PR.

### Merge order (parallel development, sequential merges)
1. **WS0 first** (contracts/schemas/flags).
2. Then any combination of **WS1/2/3/5/6/7**.
3. Then **WS4** (investigations) when connectors + feeds exist.
4. Then **WS8/9/10+**.

### Feature flags
- New features must be behind a `V3_*` flag by default.
- No UI breaking changes on main; flags make rollout safe.

### Do not touch (unless explicitly tasked)
- Legacy Chimera surfaces (`/chimera`) are treated as legacy/experimental.

### PR requirements
- Use the PR template.
- Declare ownership boundaries (files touched / not touched).
- Provide a rollback plan (usually: flip a flag off).
- Optional: use automated reviewers (e.g. CodeRabbit) and/or a second-pass LLM review (e.g. Claude Code) for risky changes, but CI is the hard gate.


