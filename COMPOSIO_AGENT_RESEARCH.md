# Composio → WatchfulEye War Room Agent (Research + Build Options)

- **Intent**: Evaluate Composio as the “external tools + auth + MCP” layer for WatchfulEye’s War Room agents, and propose a backend-first integration path that a Figma coding agent can wire cleanly.
- **Stakes**: Without a disciplined tool/auth/approval model, “AI agents” become either useless (read-only) or dangerous (silent external actions).
- **Success criteria**: A clear decision on **how** we use Composio (SDK vs Tool Router MCP), what we allow by default, and what endpoints/contracts we expose so UI integration is trivial.

## Frame the problem (1–3 lines)
Dexter shows how to run an agent with planning/iteration; AutoHedge shows how not to wire dangerous execution; Composio is the missing middle: a clean, scalable way to give agents **real integrations** via tool calling and MCP ([`ComposioHQ/composio`](https://github.com/ComposioHQ/composio.git)).

## First-principles deconstruction
### Definitions (in our context)
- **Agent**: a system that turns intent → plan → tool calls → result, with logging and safety gates.
- **Toolkit** (Composio): an integration namespace (e.g., gmail, slack, github).
- **Tool** (Composio): a single callable capability (e.g., `GMAIL_SEND_EMAIL`).
- **Tool Router session**: a per-user, scoped “capability sandbox” that exposes an MCP server URL + headers and only includes approved toolkits/tools.
- **MCP server**: a standardized interface for listing tools and invoking them; Composio can expose an MCP endpoint per session.
- **Tags**: Composio supports tool filtering tags like `readOnlyHint`, `idempotentHint`, `destructiveHint`, `openWorldHint` (useful for safety defaults).

### The core question
Do we use Composio to make WatchfulEye agents *actionable* (alerts, tickets, docs, workflows), without turning the system into an un-auditable “agent free-for-all”?

## Meaning audit (why Composio matters here)
- **What Dexter gives us**: a strong loop (plan → execute → reflect) and dependency-aware parallel task execution.
- **What Composio gives us**: a huge catalog of integrations + consistent tool schemas + managed auth flows + MCP endpoints, so we don’t build/maintain 20 brittle connectors ourselves.
- **What WatchfulEye already has**: RAG/chat, structured analysis streaming, and a growing Chimera feature set—*but not* a safe, product-grade “external action layer”.

## What Composio supports (relevant findings)
### Tool Router (Python) — the key primitive for us
Composio’s **Tool Router** creates isolated per-user sessions with explicit toolkit/tool allowlists and exposes an MCP URL + headers. It also supports starting auth flows and checking connection state (docs extracted from Composio repo `python/docs/tool-router.md`).

High-signal capabilities we should directly exploit:
- **Per-user capability sandbox**: `composio.tool_router.create(user_id=..., toolkits=[...], tools={...}, tags=[...])`
- **Safety by construction**: allowlist only the tools we want; filter by tag (e.g. default `readOnlyHint`, `idempotentHint`)
- **Auth UX**: `session.authorize(toolkit)` returns a `redirect_url`; we can embed this in WatchfulEye Settings.
- **Connection state**: `session.toolkits(is_connected=True/False)` gives us a clean “connected integrations” status panel.

### MCP API (TypeScript) — useful if we ever want FE-managed servers
The TS SDK can create MCP server configs + generate per-user instances (docs in `ts/docs/api/mcp.md`). This is relevant if we ever want a fully “MCP-native” workflow.

## The right way to use Composio in WatchfulEye (options)
### Variant A — Minimalist (recommended first)
Use Composio **only** as an integration hub for a few high-value actions, with strict allowlists and explicit user approval for anything non-read-only.

- **Example toolkits**: `slack`, `gmail`, `github`, `linear`/`jira`, `notion`/`google drive`
- **Default allowed tags**: `readOnlyHint`, `idempotentHint`
- **Disallowed by default**: `destructiveHint`
- **UI pattern**: Agent proposes action → user clicks “Approve” → backend executes via Composio → backend logs result → UI shows receipt.

Why this is the best start:
- Gives “AI everywhere” *real leverage* without turning the product into an uncontrolled automation platform.

### Variant B — Orthogonal (clean architecture for “War Room OS”)
Make Composio a first-class “Tool Plane” behind a WatchfulEye **Tool Gateway**:

- WatchfulEye exposes `/api/tools/catalog` to the UI/agent
- Under the hood, the gateway aggregates:
  - Composio tools (external)
  - WatchfulEye tools (internal: articles, search, analyses, portfolio, scenarios)
- The agent only sees one coherent tool schema.

This is the most scalable approach, but it’s more engineering up front.

### Variant C — Edge (MCP-native terminal)
Operator Terminal becomes an MCP client that can connect to:
- WatchfulEye MCP server (internal tools)
- Composio Tool Router MCP URL (external tools)

Cool, but easy to overcomplicate. Only do this if “terminal-first ops” is a core product bet.

## Safety + governance model (non-negotiable)
### Core safety rules
- **Tool allowlists only**: no “enable everything”.
- **Tag-based defaults**:
  - Default: `readOnlyHint`, `idempotentHint`
  - Require explicit approval: `destructiveHint`, and anything that sends/creates external artifacts
- **Human approval gate**:
  - Add a “preview” step: what tool, what args, what it will do
  - Log an approval record with user_id, timestamp, and tool call payload hash
- **Audit trail**:
  - Store every external tool call: tool name, args, result metadata, latency, success/failure, and a link back to the initiating chat/agent run.
- **Rate limiting**:
  - Per user + per toolkit; prevent runaway loops.

### Why this matters (AutoHedge lesson)
AutoHedge includes patterns we should *avoid* (e.g., hardcoded auth tokens and unsafe “execution” posture). Composio gives better primitives, but **we still must enforce product-level approvals**.

## Backend-first integration plan (so the Figma coding agent can wire UI cleanly)
### Minimal backend endpoints to add
1) **Create/ensure Composio Tool Router session**
- `POST /api/integrations/composio/session`
- Request: `{ toolkits: string[], tools?: {...}, tags?: string[] }`
- Response: `{ session_id, mcp_url, connected_toolkits: [...], missing_toolkits: [...] }`

2) **Start OAuth/auth for a toolkit**
- `POST /api/integrations/composio/authorize`
- Request: `{ session_id, toolkit }`
- Response: `{ redirect_url }`

3) **List connection status**
- `GET /api/integrations/composio/status?session_id=...`

4) **Tool call preview**
- `POST /api/agent/tools/preview`

5) **Tool call execute (requires approval token)**
- `POST /api/agent/tools/execute`

These endpoints let the Figma coding agent build UI flows without touching Composio details.

### DB tables (suggested)
- `user_integrations` (per user, stores composio session_id + selected toolkits)
- `tool_call_audit` (append-only audit log)
- `tool_call_approvals` (approval records)

## Novelty engine (3 useful-but-unusual moves)
1) **“Read-first War Room” mode**: ship with only `readOnlyHint` tools enabled; unlock “write tools” as a user-controlled tier/setting.
2) **Capability-based pricing**: War Room tier unlocks more *action* tools (alerts, ticketing, publishing), not just more “analysis”.
3) **Agent “action budget”**: per day/week allowance of destructive tools; forces deliberate use and makes the system safer + more legible.

## Decision & synthesis (recommended path)
Start with **Variant A** (Minimalist): Composio Tool Router sessions + strict allowlists + human approval + audit logs. Then layer in Dexter-style planning and iterative research internally. This yields “AI everywhere” that can actually *do things* without creating a liability machine.

## Rigid self-check
- **Why this?** Composio is the fastest way to give agents real-world integrations while keeping auth and scoping sane.
- **What does it change?** WatchfulEye stops being “analysis only” and becomes “analysis → action”, with explicit governance.
- **Humanity Furtherance**: **+1** — increases capability and reduces operational toil if done safely.
- **First-principles trace**:
  - Agents need tools to matter.
  - Tools need scoping + auth.
  - Scoping + auth need approvals + audit to be safe.
- **Next bold variant**: MCP-native Operator Terminal that can switch between WatchfulEye tools and Composio tools, but only after Variant A proves safe.



