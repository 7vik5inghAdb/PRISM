# PRISM v1

Synthetic research agency for Adobe culturalization A/B validation. Streamlit web app backed by Claude (Opus 4.7 + Sonnet 4.6) with agentic web search and multimodal panel simulation.

## What it does

A PM walks into the app, configures a run (hypothesis, source/target markets, variants, methods), and PRISM runs an 11-step pipeline that produces a triangulated report with a pass/fail verdict and numerical confidence. Each step is a conversational checkpoint — the orchestrator summarizes what was captured, flags inconsistencies, and the PM confirms before moving on.

## Pipeline

| Step | Module | Agent | Output |
|------|--------|-------|--------|
| 0 | **Setup** | — | hypothesis, source + target markets (N), n variants (≥2), product context, pass criteria |
| 1 | **Method** | research-questions agent | axes (qual/quant · behavioral/attitudinal), methods, 4-6 research questions |
| 2 | **Persona** | Persona Architect | per-market persona + archetype roster (panel_size per market) |
| 3 | **Instrument** | Instrument Designer | per-market research instrument matching chosen methods |
| 4 | **Panel** | Synthetic Panel | per-market respondent rankings (1..N) + 0-100 appropriateness scores + per-variant red flags |
| 5 | **Assessment** | Aggregator | per-market verdict + confidence (0-100); cross-market synthesis for multi-market runs |
| 6a | *Cultural Risk* ○ | sub-agent + web search | risks, severity, citations with URLs |
| 6b | *Competitive Analysis* ○ | sub-agent + web search | competitors, threat levels, citations with URLs |
| 6c | *Market Context* ○ | sub-agent + web search | sizing, growth signals, behaviors, citations with URLs |
| 7 | *Charting* ○ | matplotlib | 6 chart builders (top-rank, mean scores, heatmap, confidence, red flags, risk severity) |
| 8 | **Report** | Report Compiler | `report.md` + `report.json` with only enabled modules rendered |

○ = optional modules, toggleable at run creation or in the sidebar.

## Architecture

- **Single source of truth:** `runs/<run_id>/state.json` holds the full pipeline state + append-only audit log. Every agent reads and writes through `prism/state.py`.
- **Conversational orchestrator:** `prism/orchestrator.py` — Opus 4.7 confirms every step submission, flags inconsistencies, allows edits. Messages persisted to `state.history`.
- **Back-navigation:** dependency graph auto-marks downstream steps stale when an upstream step is re-run. Sidebar shows stale count + jump-to-first-stale; every step view shows a banner when stale.
- **Agentic web search:** secondary sub-agents use Claude's tool-use API to search DuckDuckGo (`ddgs` library). Every claim in the report carries a `source_url`.
- **Multimodal + parallel panel:** each archetype is a Sonnet 4.6 call that sees all variant images as base64-encoded content blocks. `ThreadPoolExecutor` parallelizes respondents within a market; prompt caching on the shared persona/instrument/research block means repeated calls hit the cache.
- **Multi-market:** one panel per target market, then a cross-market assessment compares them.
- **Numerical confidence throughout:** 0-100 scores on assessments, cross-market synthesis, secondary citations, and the final report. Color bands: 🔴 <40 · 🟠 40-60 · 🟡 60-80 · 🟢 80+.

### Models

| Role | Model | Notes |
|------|-------|-------|
| Orchestrator | `claude-opus-4-7` | thinking off for UI snappiness |
| Persona / Instrument / Method / Aggregator / Secondary / Report | `claude-opus-4-7` | adaptive thinking |
| Synthetic panel respondent | `claude-sonnet-4-6` | cost-efficient per-respondent; cached shared context |

## Setup

```bash
cd /Users/satviks/Desktop/PRISM-v0
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY
```

## Run

```bash
streamlit run app.py
```

The app opens at [http://localhost:8501](http://localhost:8501) (Streamlit's default). From there:

1. **Home:** create a new run (with module toggles) or reopen an existing one.
2. **Setup:** fill in hypothesis, markets, variants (with image paths), product context, pass criteria.
3. **Method:** pick axes + methods, click "Generate questions" to seed research questions from the hypothesis, edit inline, submit.
4. **Persona / Instrument / Panel / Assessment:** "Generate for all markets" buttons drive the per-market flow; each step shows a status table and progress bar during generation.
5. **Secondary (optional):** three sub-agents run agentic web-search loops. Live search log streams each DDG query as it happens.
6. **Charts (optional):** deterministic matplotlib PNGs generated from whatever is in state.
7. **Report:** compiles `report.md` + `report.json`. Download buttons for both; the `.md` can be opened in any Markdown viewer with its embedded chart refs.

## Outputs per run

```
runs/<run_id>/
├── state.json              # full pipeline state + history (source of truth)
├── report.md               # shareable Markdown with chart embeds
├── report.json             # structured report + run metadata
└── charts/
    ├── top_rank_per_market.png
    ├── mean_scores_per_market.png
    ├── cross_market_heatmap.png      # only if ≥2 markets
    ├── confidence_summary.png
    ├── red_flags_per_variant.png
    └── cultural_risk_severity.png    # only if cultural_risk ran
```

## Reusing across features/markets

A PRISM run is fully defined by `state.json`. To run against a new feature or market, just start a new run with different setup. The app remembers every prior run and lists them on the home page.

## Project layout

```
app.py                     # Streamlit entry point
prism/
├── state.py               # State schema + load/save/history/staleness
├── orchestrator.py        # Conversational step confirmations
├── llm.py                 # Anthropic SDK wrapper (streaming, JSON extraction)
├── client.py              # .env loader + Anthropic() factory
├── schemas.py             # Pydantic models owned by each agent
├── method.py              # Research-questions agent + axis/method taxonomy
├── persona.py             # Persona Architect (per-market)
├── instrument.py          # Instrument Designer (per-market)
├── panel.py               # Synthetic Panel (parallel, cached, multimodal)
├── aggregator.py          # Per-market + cross-market assessments
├── secondary.py           # Web-search tool + 3 sub-agents (cultural, competitive, market)
├── charting.py            # matplotlib chart builders
├── report.py              # Report compiler + Markdown renderer
├── ui/                    # Streamlit helpers (sidebar, progress, chat, labels, modules, home)
└── steps/                 # Per-step render modules (setup, method, persona, …)
```

## Out of scope (intentional)

- Discovery-phase research — PRISM is validation-only
- Quantitative effect sizes beyond share-preferring-top-variant (no stat-sig machinery)
- Non-image asset types (the panel assumes visual variants)

## Legacy v0 runs

Old `runs/` subdirectories that have per-step JSON files but no `state.json` are v0 artifacts. They're preserved on disk for reference and listed separately on the home page but can't be reopened in v1 — create a new run to work in the current format.
