# WatchfulEye V3 — Strategic Planning Session Summary
**Date:** 2026-01-09
**Session Type:** Strategic Planning, Rule Creation, Feedback Integration
**Agent:** Claude (Sonnet 4.5)
**Commit:** `13b868c` — docs(v3): add agent-agnostic rules + accuracy engine strategy (WS6.1)

---

## 🎯 **MISSION ACCOMPLISHED**

### ✅ Created Agent-Agnostic Development Framework
Your codebase now has **persistent context** that works seamlessly across:
- ✅ **Cursor** (your current IDE)
- ✅ **Claude Code** (CLI tool)
- ✅ **Any future coding agent** (Claude Desktop, Aider, Copilot, etc.)

**Result:** Switch agents mid-task without losing context. Every agent knows:
- Where you are
- What's done
- What's next
- How to ship code safely

---

## 📋 **NEW RULES CREATED** (in `.cursor/rules/`)

### 1. **`watchfuleye-context-memory.mdc`** — Context Preservation System
**Purpose:** Seamless agent switching with zero context loss

**Key Features:**
- **Critical context files** (always read first)
- **State tracking protocol** (update after every action)
- **Session start/end protocols** (standardized)
- **Relational positioning** (where we are in V3 roadmap)
- **Agent handoff checklist** (what next agent needs)
- **Memory artifacts** (persistent across sessions)
- **Figma design vision** (UI truth from master plan)
- **Non-negotiables** (sacred surfaces, flag discipline)

**Agent Responsibility:**
- Read `.cursor/state/current-position.md` FIRST
- Update state file AFTER every action
- Commit frequently with clear messages
- Never break sacred surfaces

---

### 2. **`watchfuleye-shipping-discipline.mdc`** — Version Control Mastery
**Purpose:** Rigorous git workflow for clean, reversible shipping

**Key Features:**
- **Branch strategy** (naming conventions: `wsX/<slice-name>`)
- **Commit discipline** (early, often, descriptive)
- **Pre-commit checklist** (lint, typecheck, tests BEFORE commit)
- **Push frequency** (after every commit, never wait)
- **PR workflow** (template, CI green, CodeRabbit review)
- **Merge discipline** (requirements, methods, post-merge cleanup)
- **Staging deployment** (server workflow via SSH)
- **Conflict resolution** (rebase, force-push-with-lease)
- **Emergency rollback** (revert, flag toggle, hotfix)
- **Best practices** (DOs and DON'Ts)

**Agent Responsibility:**
- Run tests before committing
- Write clear commit messages
- Open PRs with complete descriptions
- Address CI failures immediately
- Update state files post-merge

---

### 3. **`watchfuleye-feedback-loop.mdc`** — Accuracy Engine (WS6.1 Strategy) 🔥
**Purpose:** Transform "AI analysis" → "proven track record" with measurable accuracy

**Strategic Importance:**
> **Advisor feedback:** "The feedback loop/accuracy engine is the **single biggest differentiator**. Ship WS6.1 ASAP."

**Closes the Loop:**
```
OLD (incomplete):
Analyze → Predict → User Consumption → ❌ (loop not closed)

NEW (complete):
Analyze → Predict (+ store with timestamps)
  ↓
User Consumption
  ↓
Outcome Measurement (automated: markets, events, odds)
  ↓
Accuracy Scoring (Brier, calibration, hit rate)
  ↓
Feedback (improve model + build user trust)
  ↑___________________|
```

**Value Proposition Shift:**
- FROM: "AI analyzes news"
- TO: **"Proven 73% accuracy on geopolitical predictions over 6 months"**

**Key Components:**
1. **Forecast storage** — Persist every prediction with probability, horizon, evidence
2. **Outcome measurement** — Automated via market data, event feeds, odds resolution
3. **Accuracy scoring** — Brier scores, calibration curves, hit rates by horizon
4. **User-facing metrics** — Track Record panel, confidence badges, performance trends
5. **Adaptive learning** — Use accuracy to optimize scoring weights over time

**Implementation (WS6.1):**
- DB tables: `forecasts`, `forecast_updates` (audit trail)
- Backend: `watchfuleye/v3/forecast/*` (extractor, tracker, scorer, metrics API)
- Frontend: `frontend/src/v3/forecast/*` (AccuracyPanel, CalibrationChart)
- Timeline: 2-3 weeks (TOP PRIORITY)

**Success Metrics:**
- Avg Brier score < 0.20 (industry benchmark: 0.25)
- Calibration error < 0.10 (near-perfect)
- 70%+ forecasts resolved within horizon + 7 days
- User trust score > 4.0/5.0

---

## 📊 **ADVISOR FEEDBACK ADDRESSED** (5 Critical Questions)

### 1. ✅ **Feedback Loop** (Closing the Loop)
**Question:** "How are you closing the loop? Creating a feedback loop to track accuracy?"

**Answer:**
- WS6.1 implements full feedback loop: Predict → Measure → Score → Improve
- Brier scores, calibration curves, hit rates tracked automatically
- Outcome measurement via market data, event feeds, prediction markets
- Users see "Track Record" panel with proven accuracy over time
- **Result:** Builds trust, transforms product positioning

---

### 2. ✅ **Scoring Model** (Weights Definition)
**Question:** "How are scoring weights defined? Are they set by you or adaptive? Can users set their own?"

**Answer — 3-Phase Roadmap:**

**Phase 1: Expert-Defined (Current)**
```python
DEFAULT_WEIGHTS = {
    "source_trust": 0.35,      # Most important (fake news filter)
    "content_quality": 0.25,    # Well-structured, evidence-rich
    "recency": 0.20,            # Breaking news matters
    "entity_relevance": 0.15,   # Matches user watchlist
    "user_feedback": 0.05,      # Saved articles, upvotes
}
```
- Rationale: Source trust is paramount (35%), quality + recency follow

**Phase 2: Adaptive (Future)**
- Use Bayesian optimization to minimize Brier score
- Re-optimize weights every 100 resolved forecasts
- Objective: Find weights that maximize prediction accuracy

**Phase 3: User-Defined (Future)**
- Slider interface in settings
- Questions like: "How much do you trust mainstream vs. alternative sources?"
- "Do you prefer depth or breadth?"
- Personalized scoring based on user preferences

---

### 3. ✅ **Data Sources** (PhantomBuster + Ripts)
**Question:** "Social sentiment (PhantomBuster) and alternative data (Ripts) mentioned. Plans?"

**Answer — Integrated into WS5 Connectors Roadmap:**

**PhantomBuster (Social Sentiment):**
- **Use Case:** Track narrative velocity, brigading detection, influencer tracking
- **Implementation:** WS5 Tier B connector (non-standard signals)
- **Governance:** Rate limits (1000 posts/day), caching (1hr TTL), anti-brigading filters
- **Confidence gating:** Only show when confidence > 0.6
- **Platforms:** Twitter, Reddit (compliant APIs)

**Ripts (Alternative Data):**
- **Use Case:** Satellite imagery, supply chain, mobility data, port activity
- **Implementation:** WS5 Tier C connector (gated, expensive)
- **Governance:** Explicit user consent, cost tracking per query
- **Usage:** Only for high-value investigations
- **Examples:** Shipping activity at ports, foot traffic, supply chain disruptions

**Integration:** Both feed into evidence ranking + forecast scoring

---

### 4. ✅ **Target User & Usage Patterns**
**Question:** "Who is your target user? Traders, researchers? Morning brief, alerts, war room?"

**Answer — 3 User Personas:**

#### **Trader (Primary)**
- **Needs:** Actionable predictions, risk alerts, market-moving events
- **Timeline:** Intraday to 30-day horizons
- **Usage:**
  - **Morning:** Global Brief (5-10 min) + "Movers & Shakers" panel + set alerts
  - **Intraday:** Telegram alerts → deep dive → decide trade
  - **End of Day:** Review accuracy metrics (build trust)
- **Key Features:** Fast signal-to-action (< 30s), confidence badges, track record
- **Default view:** War room dashboard

#### **Researcher (Secondary)**
- **Needs:** Deep analysis, evidence trails, scenario modeling
- **Timeline:** Weekly to 90-day horizons
- **Usage:**
  - **Weekly:** "Examine X" investigations (30-60 min)
  - **Monthly:** Scenario campaigns, export reports with citations
- **Key Features:** Evidence-first reports, dissent sections, PDF export
- **Default view:** Investigate page

#### **Analyst (Tertiary)**
- **Needs:** Curated intel feed, geopolitical monitoring, early warning
- **Timeline:** 7-day to 90-day horizons
- **Usage:**
  - **Daily:** Intelligence Report (15 min) + monitor dashboard
  - **Weekly:** Ad-hoc investigations, team sharing
- **Key Features:** Custom feed curation, monitor dashboard, export/Slack
- **Default view:** Brief page

**Usage Pattern Matrix:**
| User       | Morning Brief | Alerts | War Room | Accuracy | Export |
|------------|---------------|--------|----------|----------|--------|
| Trader     | ✅ Daily      | ✅ Yes | ✅ Yes   | ✅ High  | ❌ No  |
| Researcher | ❌ No         | ❌ No  | ❌ No    | ✅ Med   | ✅ Yes |
| Analyst    | ✅ Daily      | ✅ Yes | ✅ Yes   | ✅ Med   | ✅ Yes |

**Future:** Personalization engine adapts UI based on persona + preferences

---

### 5. ✅ **Infrastructure** (Postgres Hybrid)
**Question:** "Is Postgres doing vector + relational? Or hybrid with separate vector DB?"

**Answer — Postgres-First Hybrid (No Separate Vector DB):**

**Decision:** Stay with **Postgres + pgvector** (currently pg16)

**Rationale:**
1. **Simplicity:** One database, one connection pool, one backup strategy
2. **Performance:** pgvector HNSW fast enough for < 10M vectors (~50-100ms)
3. **Joins:** Can join vector search with relational filters (source, date, category)
4. **Cost:** $0 vs. $200+/month for Pinecone/Weaviate/Qdrant
5. **Maturity:** pgvector is production-ready, well-maintained

**Current Setup:**
- Vector embeddings: `article_embeddings` (1536-dim OpenAI), `article_embeddings_voyage` (1024-dim)
- FTS (full-text search): `tsvector` with GIN index
- Vector similarity: HNSW index with cosine distance (`<=>`)
- Hybrid query: Combine FTS (keywords) + vector (semantic) + relational filters

**Hybrid Query Example:**
```python
# FTS matches (fast, keyword-based)
# + Vector matches (semantic similarity)
# + Relational filters (source, date, category)
# = Combined score (0.3 * FTS + 0.7 * vector)
```

**When to Reconsider:**
- Vector count > 10M (performance degradation)
- Sub-10ms latency required (pgvector is ~50-100ms)
- Need advanced vector features (multi-vector search, filtering, etc.)

**Verdict:** Postgres-first is optimal for current scale + feature set.

---

## 🔄 **UPDATED MASTER PLAN** (Strategic Re-Prioritization)

### **NEW TOP PRIORITY: WS6.1 (Forecast Accountability) 🔥**

**Before:**
```
CURRENT NEXT SLICE:
- WS4.0 COMPLETE ✅
- Next: WS4.1 (Enhance Examine runner)
```

**After (Updated Today):**
```
CURRENT NEXT SLICE:
- WS4.0 COMPLETE ✅
- NEW TOP PRIORITY: WS6.1 (Forecast Accountability) — "Single biggest differentiator"
- Next after WS6.1: WS4.1 (Enhance Examine runner)
```

**Rationale:**
- Advisor feedback: **"The feedback loop/accuracy engine is the single biggest differentiator."**
- Transforms product: "AI analysis" → **"Proven track record"**
- Builds user trust faster than any other feature
- Enables adaptive learning (optimize weights based on accuracy)
- Competitive moat: Hard to copy without historical data

**Timeline:**
- WS6.1: 2-3 weeks (highest priority)
- WS4.1: 1-2 weeks (after WS6.1)
- WS5: 2-3 weeks (can run parallel with WS6.1)

---

## 📁 **STATE TRACKING SYSTEM** (Real-Time Context)

### **`.cursor/state/current-position.md`** (Always Updated)
- Real-time snapshot of project state
- Updated after every significant action
- Contains:
  - Current workstream
  - Files modified in session
  - Next immediate steps
  - Blockers (if any)
  - Git status
  - Completed/pending workstreams
  - Dependencies
  - Advisor feedback summary
  - Next session instructions

**Note:** `.cursor/state/` is in `.gitignore` (ephemeral, not committed)

**Agent Responsibility:**
- Read this file FIRST when starting session
- Update this file AFTER every action
- Document next steps clearly

---

## 🚀 **PARALLEL AGENT EXECUTION PLAN**

### **Immediately Parallelizable (No Conflicts)**
1. **Agent 1:** WS6.1 (forecast accountability) — owns `watchfuleye/v3/forecast/*`
2. **Agent 2:** WS5 (connectors Tier A) — owns `watchfuleye/v3/connectors/*`
3. **Agent 3:** WS1 (main feed v2) — owns `watchfuleye/v3/feeds/news/*`

### **Next Wave (After WS6.1 + WS5 Land)**
4. **Agent 4:** WS4.1 (enhance examine) — depends on WS5 connectors
5. **Agent 5:** WS1.1 (reports v2) — owns `watchfuleye/v3/reports/*`
6. **Agent 6:** WS2 (custom feed) — owns `watchfuleye/v3/feeds/custom/*`

### **Conflict-Free Guarantees:**
- Each workstream owns its own paths (no file conflicts)
- All features behind flags (independent enablement)
- Sequential merge to master (even if parallel dev)
- CI validates correctness (no broken state)

---

## 📚 **DOCUMENTATION SUMMARY**

### **Rules Created Today:**
1. ✅ `.cursor/rules/watchfuleye-context-memory.mdc` (agent-agnostic state)
2. ✅ `.cursor/rules/watchfuleye-shipping-discipline.mdc` (version control)
3. ✅ `.cursor/rules/watchfuleye-feedback-loop.mdc` (accuracy engine strategy)

### **Existing Rules (Reviewed & Integrated):**
4. ✅ `.cursor/rules/watchfuleye-v3.mdc` (operating rules)
5. ✅ `.cursor/rules/watchfuleye-laptop-clone.mdc` (laptop workflow)

### **State Files:**
6. ✅ `.cursor/state/current-position.md` (real-time snapshot)

### **Master Plan:**
7. ✅ `WATCHFULEYE_V3_MASTER_PLAN.md` (updated with WS6.1 priority)

---

## 🎯 **NEXT STEPS (Actionable)**

### **Immediate (Next Session):**

1. **Start WS6.1 Implementation:**
   ```bash
   git fetch origin master
   git checkout -b ws6.1/forecast-accountability origin/master
   ```

2. **Implement Forecast Schema:**
   - Edit `watchfuleye/storage/postgres_schema.py`
   - Add `forecasts` + `forecast_updates` tables
   - Run tests

3. **Implement Forecast Extraction:**
   - Create `watchfuleye/v3/forecast/extractor.py`
   - Integrate into `examine_api.py`
   - Extract predictions from report content

4. **Implement Outcome Tracker:**
   - Create `watchfuleye/v3/forecast/outcome_tracker.py`
   - Automated measurement via markets/events/odds

5. **Implement Scoring:**
   - Create `watchfuleye/v3/forecast/scorer.py`
   - Brier, log score, calibration

6. **Implement Metrics API:**
   - Create `watchfuleye/v3/forecast/metrics_api.py`
   - Endpoint: `GET /api/v3/forecast/metrics`

7. **Implement Frontend Panel:**
   - Create `frontend/src/v3/forecast/AccuracyPanel.tsx`
   - Calibration chart, performance trend

8. **Write Tests + Open PR:**
   - Backend tests: `tests/test_v3_forecast_*.py`
   - Frontend tests
   - PR with complete description

---

## 🛡️ **NON-NEGOTIABLES (Reminder)**

### **Sacred Surfaces (Never Break):**
1. ✅ Main News Feed
2. ✅ Custom News Feed
3. ✅ Telegram Intel Reports
4. ✅ Intel Reports
5. ✅ AI Analysis Modal

### **Flag Discipline:**
- All V3 features behind `V3_*` flags
- Default OFF in production
- Rollback = flip flag OFF

### **File Ownership:**
- Each workstream owns its paths
- Hot files require justification
- WS0 owns contracts/schemas

### **CI Discipline:**
- Green required for merge
- CodeRabbit review addressed
- One workstream slice per PR

### **Production Isolation:**
- NEVER deploy V3 to prod until ready
- Prod is FROZEN
- Staging only via master-only worktree

---

## 🎨 **FIGMA DESIGN VISION** (UI Truth)

**URL:** https://www.figma.com/make/yGEihhyU0cCiVNi3DILbAt/Landing-Page-for-WatchfulEye

**Key Design Elements:**
- **Command Center aesthetic:** Terminal-style input, world map, draggable panels
- **Core verbs:** Examine, Monitor, Pin, Share, Export (consistent everywhere)
- **Layout baseline:** Top 60% = map + layers, Bottom 40% = draggable modules
- **Trust UI:** Citations, confidence, dissent, provenance always visible
- **Keyboard-first:** Omnibox/terminal always reachable (⌘K or /)
- **Progressive disclosure:** Short high-signal by default, expand on request
- **Zero dead controls:** Every click maps to server effect or is removed
- **Speed is a feature:** Progressive rendering, streaming, aggressive caching

---

## 💡 **KEY INSIGHTS FROM ADVISOR FEEDBACK**

### **"Single Biggest Differentiator":**
> The feedback loop/accuracy engine alone would turn your product from "AI analysis" into "proven track record". This is your competitive moat.

### **Trust Factor:**
> Not only will this help make predictions better, but adds a "trust factor" for users over time. Accuracy %'s matter.

### **Product Positioning:**
> Everything feels very powerful but a bit broad - the accuracy engine gives you a sharp, defensible positioning: "We have a proven track record."

### **Business Impact:**
> Users who see your track record will:
- Stay longer (+30% retention)
- Refer more often (+50% referral rate)
- Convert faster (+40% free → paid)
- Rate you higher (+20 NPS points)

---

## ✅ **DELIVERABLES (Completed Today)**

1. ✅ **Agent-agnostic rules** (3 new files)
2. ✅ **State tracking system** (real-time snapshot)
3. ✅ **Accuracy engine strategy** (WS6.1 detailed spec)
4. ✅ **Advisor feedback addressed** (all 5 questions)
5. ✅ **Master plan updated** (WS6.1 promoted to top priority)
6. ✅ **Git commit** (`13b868c` — docs(v3): add agent-agnostic rules)
7. ✅ **Strategic planning session summary** (this document)

---

## 📞 **AGENT HANDOFF CHECKLIST**

If switching to a new agent:
1. [ ] Read `.cursor/state/current-position.md` (real-time snapshot)
2. [ ] Read `.cursor/rules/watchfuleye-feedback-loop.mdc` (WS6.1 strategy)
3. [ ] Read `WATCHFULEYE_V3_MASTER_PLAN.md` (architecture + workstreams)
4. [ ] Check `git status` and `git branch`
5. [ ] Run tests to verify baseline: `pytest && npm test`
6. [ ] Ask clarifying questions if state is ambiguous

---

## 🎉 **MISSION STATUS**

**✅ COMPLETE — Ready for Implementation**

You now have:
- ✅ **Persistent context system** (seamless agent switching)
- ✅ **Rigorous shipping discipline** (version control mastery)
- ✅ **Strategic clarity** (WS6.1 is the differentiator)
- ✅ **Advisor feedback addressed** (all 5 questions answered)
- ✅ **Parallel execution plan** (3+ agents can work safely)
- ✅ **Premier system foundation** (accuracy, trust, scalability)

**Next:** Execute WS6.1 (Forecast Accountability) → ship in 2-3 weeks → transform product positioning → build competitive moat.

---

**End of Summary**
