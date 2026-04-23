"""Agent 6 — Dynamic Report Compiler (v1, state-backed).

Two phases:

1. **Compile** (LLM): Opus 4.7 produces a `TriangulatedReport` with narrative
   sections — executive summary, per-module summaries (only for modules that
   actually ran), convergence analysis, recommendations, open questions.

2. **Render** (deterministic): Markdown + JSON output files with all the
   deterministic scaffolding the LLM doesn't need to write — setup tables,
   per-market score tables, chart embeds, citations, audit log.

Both files land under `runs/<run_id>/`:
- `report.md` — portable, shareable Markdown with `![](charts/X.png)` refs
- `report.json` — the TriangulatedReport as JSON (for downstream tooling)

Only modules that are enabled AND complete appear in the output. Disabled
modules are absent — no ghost sections.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from prism import aggregator as aggregator_agent
from prism import secondary as secondary_agent
from prism import state as S
from prism.llm import call_structured
from prism.persona import get_all_personas
from prism.schemas import (
    Assessment,
    CompetitiveAnalysisSynthesis,
    CrossMarketAssessment,
    CulturalRiskSynthesis,
    MarketContextSynthesis,
    SecondaryCitation,
    TriangulatedReport,
)
from prism.ui.labels import confidence_badge


_SYSTEM = (
    "Write a triangulated research report. Rules:\n"
    "- Fill *_summary fields ONLY for modules present below. Absent module → null summary.\n"
    "- confidence_0_100 reflects module agreement. Scale: 0-39 weak, 40-59 ambiguous, "
    "60-79 solid, 80-100 clear. Full range.\n"
    "- recommended_actions: concrete, prioritized top-down. No vague 'improve X' advice.\n"
    "- executive_summary: 3-5 sentences max, paste-into-Slack grade."
)


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_report(state: S.State) -> Optional[TriangulatedReport]:
    if state.report is None or state.report.json_path is None:
        return None
    path = S.run_dir(state.run_id) / state.report.json_path
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    inner = payload.get("report") if isinstance(payload, dict) else None
    if inner is None:
        # Backwards-compat: file might be a bare TriangulatedReport dump.
        inner = payload
    return TriangulatedReport.model_validate(inner)


# ---------------------------------------------------------------------------
# LLM compile
# ---------------------------------------------------------------------------


def _build_prompt(state: S.State) -> str:
    setup = state.setup
    assert setup is not None
    me = state.modules_enabled

    parts: list[str] = []

    # --- Setup + method context ---
    parts.append(f"# Run\nrun_id: {state.run_id}")
    parts.append(
        f"hypothesis: {setup.hypothesis}\n"
        f"source market: {setup.source_market.country} ({setup.source_market.locale})\n"
        f"target markets: "
        + ", ".join(f"{m.country} ({m.locale})" for m in setup.target_markets)
        + "\n"
        f"asset: {setup.product_context.application} · "
        f"{setup.product_context.asset_type} · "
        f"feature: {setup.product_context.feature}"
    )
    variants_str = "\n".join(
        f"- `{v.id}`: {v.label}" + (" (CONTROL)" if v.is_control else "")
        for v in setup.variants
    )
    parts.append(f"# Variants\n{variants_str}")

    if state.method is not None:
        m = state.method
        axes = [k for k, v in m.axes.model_dump().items() if v]
        parts.append(
            f"# Method\n"
            f"axes: {', '.join(axes)}\n"
            f"methods: {', '.join(m.selected_methods)}\n"
            f"research questions:\n" + "\n".join(f"- {q}" for q in m.research_questions)
        )

    # --- Primary assessments ---
    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)
    if per_market:
        rows = []
        for locale, a in per_market.items():
            shares_str = ", ".join(f"{vid}={share:.0%}" for vid, share in sorted(a.variant_top_rank_shares.items(), key=lambda kv: -kv[1]))
            scores_str = ", ".join(f"{vid}={score:.1f}" for vid, score in sorted(a.variant_mean_scores.items(), key=lambda kv: -kv[1]))
            flags_str = "; ".join(a.cultural_red_flags) if a.cultural_red_flags else "(none)"
            rows.append(
                f"## {locale}\n"
                f"- Verdict: {a.verdict}  (confidence {a.confidence_0_100}/100)\n"
                f"- Winning variant: {a.winning_variant_id}\n"
                f"- Top-rank shares: {shares_str}\n"
                f"- Mean scores: {scores_str}\n"
                f"- Red flags: {flags_str}\n"
                f"- Rationale: {a.rationale}\n"
                f"- Recommended next step: {a.recommended_next_step}"
            )
        parts.append("# Primary assessments (per-market)\n" + "\n\n".join(rows))

        if cross is not None:
            parts.append(
                f"# Cross-market synthesis\n"
                f"- Confidence: {cross.confidence_0_100}/100\n"
                f"- Consistent winners: {', '.join(cross.consistent_winners) or '(none)'}\n"
                f"- Divergent findings:\n" + "\n".join(f"  - {d}" for d in cross.divergent_findings) + "\n"
                f"- Rationale: {cross.cross_market_rationale}\n"
                f"- Recommended next step: {cross.recommended_next_step}"
            )

    # --- Secondary modules (only those enabled + complete) ---
    if me.cultural_risk:
        cr = secondary_agent.get_cultural_risk(state)
        if cr is not None:
            findings_str = "\n".join(
                f"- {f.title} (severity {f.severity_0_100}/100, markets: {', '.join(f.affected_markets)})\n"
                f"  {f.description}"
                for f in cr.findings
            )
            parts.append(
                f"# Cultural Risk (enabled, ran)\n"
                f"- Overall risk: {cr.overall_risk_0_100}/100\n"
                f"- Summary: {cr.summary}\n"
                f"- Findings:\n{findings_str}"
            )

    if me.competitive_analysis:
        ca = secondary_agent.get_competitive(state)
        if ca is not None:
            comps_str = "\n".join(
                f"- {c.name} (threat {c.threat_level_0_100}/100): {c.positioning}"
                for c in ca.competitors
            )
            parts.append(
                f"# Competitive Analysis (enabled, ran)\n"
                f"- Landscape: {ca.landscape_summary}\n"
                f"- Competitors:\n{comps_str}\n"
                f"- Threats:\n" + "\n".join(f"  - {t}" for t in ca.threats) + "\n"
                f"- Opportunities:\n" + "\n".join(f"  - {o}" for o in ca.opportunities)
            )

    if me.market_context:
        mc = secondary_agent.get_market_context(state)
        if mc is not None:
            parts.append(
                f"# Market Context (enabled, ran)\n"
                f"- Summary: {mc.summary}\n"
                f"- Sizing: {mc.sizing_qualitative}\n"
                f"- Growth signals:\n" + "\n".join(f"  - {g}" for g in mc.growth_signals) + "\n"
                f"- Audience behaviors:\n" + "\n".join(f"  - {b}" for b in mc.audience_behaviors) + "\n"
                f"- Adjacent trends:\n" + "\n".join(f"  - {t}" for t in mc.adjacent_trends)
            )

    # --- Module status ---
    disabled = [k for k, v in me.model_dump().items() if not v]
    if disabled:
        parts.append(f"# Modules DISABLED for this run\n{', '.join(disabled)}")
        parts.append(
            "For disabled modules, set the corresponding `*_summary` field to null."
        )

    parts.append(
        "Produce TriangulatedReport. Summary fields null for absent modules. "
        "headline_verdict defaults to cross-market verdict if present, else the "
        "single per-market verdict; override to needs_revision for severe "
        "secondary risks. cultural_red_flags aggregates primary per-variant "
        "flags + cultural risk findings with severity ≥70."
    )

    return "\n\n".join(parts)


def compile_report(state: S.State) -> TriangulatedReport:
    if state.setup is None:
        raise RuntimeError("state.setup is required before report compilation.")

    return call_structured(
        model="claude-haiku-4-5",
        system=_SYSTEM,
        user_content=_build_prompt(state),
        response_model=TriangulatedReport,
        max_tokens=6000,
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _verdict_badge(v: str) -> str:
    return {"pass": "✅ PASS", "fail": "❌ FAIL", "needs_revision": "⚠️ NEEDS REVISION"}.get(v, v)


def _md_citations_table(citations: list[SecondaryCitation]) -> str:
    if not citations:
        return "_No citations._"
    rows = ["| Type | Confidence | Claim | URL |", "| --- | --- | --- | --- |"]
    for c in citations:
        url = f"[link]({c.source_url})" if c.source_url else "_(no URL)_"
        claim = c.claim.replace("|", "\\|")
        rows.append(f"| {c.source_type} | {c.confidence_0_100}/100 | {claim} | {url} |")
    return "\n".join(rows)


def render_markdown(state: S.State, report: TriangulatedReport) -> str:
    setup = state.setup
    assert setup is not None
    me = state.modules_enabled

    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)

    v_badge = _verdict_badge(report.headline_verdict)
    c_badge = confidence_badge(report.confidence_0_100)

    # Header
    lines: list[str] = []
    lines.append(f"# PRISM Report — `{state.run_id}`")
    lines.append("")
    lines.append(f"**Generated:** {_today_utc()}")
    lines.append("")
    lines.append(f"**Verdict:** {v_badge}  ·  **Confidence:** {c_badge}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive summary + actions + open questions (LLM-generated)
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(report.executive_summary)
    lines.append("")
    lines.append("## Recommended Actions")
    lines.append("")
    for a in report.recommended_actions:
        lines.append(f"- {a}")
    lines.append("")
    if report.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in report.open_questions:
            lines.append(f"- {q}")
        lines.append("")
    lines.append("---")
    lines.append("")

    # Setup
    lines.append("## Setup")
    lines.append("")
    lines.append(f"**Hypothesis:** {setup.hypothesis}")
    lines.append("")
    lines.append("**Markets:**")
    lines.append(f"- Source: {setup.source_market.country} ({setup.source_market.locale})")
    for m in setup.target_markets:
        lines.append(f"- Target: {m.country} ({m.locale})")
    lines.append("")
    lines.append("**Variants:**")
    lines.append("")
    lines.append("| ID | Label | Control? | Path |")
    lines.append("| --- | --- | --- | --- |")
    for v in setup.variants:
        lines.append(f"| `{v.id}` | {v.label} | {'✓' if v.is_control else ''} | `{v.path}` |")
    lines.append("")
    lines.append("**Product context:**")
    pc = setup.product_context
    lines.append(f"- Application: {pc.application}")
    lines.append(f"- Product unit: {pc.product_unit}")
    lines.append(f"- Feature: {pc.feature}")
    lines.append(f"- Asset type: {pc.asset_type}")
    lines.append(f"- Use case: {pc.use_case}")
    lines.append("")

    # Method
    if state.method is not None:
        m = state.method
        axes = [k for k, vv in m.axes.model_dump().items() if vv]
        lines.append("## Method")
        lines.append("")
        lines.append(f"**Axes:** {', '.join(axes) or '(none)'}")
        lines.append("")
        lines.append(f"**Methods:** {', '.join(m.selected_methods) or '(none)'}")
        lines.append("")
        lines.append("**Research questions:**")
        for q in m.research_questions:
            lines.append(f"- {q}")
        lines.append("")

    # Primary findings
    lines.append("## Primary Findings (Synthetic Panel)")
    lines.append("")
    lines.append(report.primary_findings_summary)
    lines.append("")

    if per_market:
        lines.append("### Per-Market Assessments")
        lines.append("")
        for locale in sorted(per_market.keys()):
            a = per_market[locale]
            lines.append(
                f"#### {locale} — {_verdict_badge(a.verdict)} · "
                f"confidence {a.confidence_0_100}/100"
            )
            lines.append("")
            lines.append(f"**Winning variant:** `{a.winning_variant_id}`")
            lines.append("")
            lines.append("**Variant performance:**")
            lines.append("")
            lines.append("| Variant | Top-rank share | Mean score (0-100) |")
            lines.append("| --- | --- | --- |")
            all_vids = sorted(a.variant_top_rank_shares.keys())
            for vid in all_vids:
                lines.append(
                    f"| `{vid}` | {a.variant_top_rank_shares.get(vid, 0):.0%} | "
                    f"{a.variant_mean_scores.get(vid, 0):.1f} |"
                )
            lines.append("")
            if a.cultural_red_flags:
                lines.append("**Red flags:**")
                for f in a.cultural_red_flags:
                    lines.append(f"- {f}")
                lines.append("")
            lines.append(f"**Rationale:** {a.rationale}")
            lines.append("")
            lines.append(f"**Recommended next step:** {a.recommended_next_step}")
            lines.append("")

    if cross is not None:
        lines.append(
            f"### Cross-Market Synthesis — confidence {cross.confidence_0_100}/100"
        )
        lines.append("")
        lines.append(
            f"**Consistent winners:** {', '.join(cross.consistent_winners) or '(none)'}"
        )
        lines.append("")
        if cross.divergent_findings:
            lines.append("**Divergent findings:**")
            for d in cross.divergent_findings:
                lines.append(f"- {d}")
            lines.append("")
        lines.append(f"**Rationale:** {cross.cross_market_rationale}")
        lines.append("")
        lines.append(f"**Recommended next step:** {cross.recommended_next_step}")
        lines.append("")

    # Secondary (only modules that ran)
    secondary_rendered = False

    if me.cultural_risk and report.cultural_risk_summary:
        cr = secondary_agent.get_cultural_risk(state)
        if cr is not None:
            if not secondary_rendered:
                lines.append("## Secondary Synthesis")
                lines.append("")
                secondary_rendered = True
            lines.append(f"### Cultural Risk — overall {cr.overall_risk_0_100}/100")
            lines.append("")
            lines.append(report.cultural_risk_summary)
            lines.append("")
            for f in cr.findings:
                lines.append(
                    f"#### {f.title} · severity {f.severity_0_100}/100 · "
                    f"markets: {', '.join(f.affected_markets)}"
                )
                lines.append("")
                lines.append(f.description)
                lines.append("")
                lines.append(_md_citations_table(f.citations))
                lines.append("")

    if me.competitive_analysis and report.competitive_summary:
        ca = secondary_agent.get_competitive(state)
        if ca is not None:
            if not secondary_rendered:
                lines.append("## Secondary Synthesis")
                lines.append("")
                secondary_rendered = True
            lines.append("### Competitive Analysis")
            lines.append("")
            lines.append(report.competitive_summary)
            lines.append("")
            lines.append(f"**Landscape:** {ca.landscape_summary}")
            lines.append("")
            if ca.threats:
                lines.append("**Threats:**")
                for t in ca.threats:
                    lines.append(f"- {t}")
                lines.append("")
            if ca.opportunities:
                lines.append("**Opportunities:**")
                for o in ca.opportunities:
                    lines.append(f"- {o}")
                lines.append("")
            lines.append("**Competitors:**")
            lines.append("")
            for c in ca.competitors:
                lines.append(
                    f"#### {c.name} · threat {c.threat_level_0_100}/100"
                )
                lines.append("")
                lines.append(f"**Positioning:** {c.positioning}")
                lines.append("")
                lines.append("**Relevant offerings:**")
                for o in c.relevant_offerings:
                    lines.append(f"- {o}")
                lines.append("")
                lines.append(_md_citations_table(c.citations))
                lines.append("")

    if me.market_context and report.market_context_summary:
        mc = secondary_agent.get_market_context(state)
        if mc is not None:
            if not secondary_rendered:
                lines.append("## Secondary Synthesis")
                lines.append("")
                secondary_rendered = True
            lines.append("### Market Context")
            lines.append("")
            lines.append(report.market_context_summary)
            lines.append("")
            lines.append(f"**Qualitative sizing:** {mc.sizing_qualitative}")
            lines.append("")
            if mc.growth_signals:
                lines.append("**Growth signals:**")
                for g in mc.growth_signals:
                    lines.append(f"- {g}")
                lines.append("")
            if mc.audience_behaviors:
                lines.append("**Audience behaviors:**")
                for b in mc.audience_behaviors:
                    lines.append(f"- {b}")
                lines.append("")
            if mc.adjacent_trends:
                lines.append("**Adjacent trends:**")
                for t in mc.adjacent_trends:
                    lines.append(f"- {t}")
                lines.append("")
            lines.append("**Citations:**")
            lines.append("")
            lines.append(_md_citations_table(mc.citations))
            lines.append("")

    # Convergence
    lines.append("## Convergence Analysis")
    lines.append("")
    lines.append(report.convergence_analysis)
    lines.append("")

    # Cultural red flags
    if report.cultural_red_flags:
        lines.append("## Cultural Red Flags")
        lines.append("")
        for f in report.cultural_red_flags:
            lines.append(f"- {f}")
        lines.append("")

    # Charts
    if me.charting and state.charts:
        lines.append("## Charts")
        lines.append("")
        for c in state.charts:
            lines.append(f"### {c.title}")
            lines.append("")
            lines.append(f"![{c.title}]({c.path})")
            lines.append("")
            lines.append(f"_{c.description}_")
            lines.append("")

    # Appendix
    lines.append("---")
    lines.append("")
    lines.append("## Appendix A — Modules Enabled")
    lines.append("")
    for key, val in me.model_dump().items():
        lines.append(f"- {key}: {'✅' if val else '⬜'}")
    lines.append("")

    # Audit log (last 30 entries)
    recent_history = state.history[-30:] if len(state.history) > 30 else state.history
    if recent_history:
        lines.append(f"## Appendix B — Audit Log (last {len(recent_history)} entries)")
        lines.append("")
        lines.append("| Timestamp | Actor | Action |")
        lines.append("| --- | --- | --- |")
        for h in recent_history:
            action = h.action.replace("|", "\\|")
            lines.append(f"| {h.ts} | {h.actor} | {action} |")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated by PRISM v1. Secondary synthesis uses live web search via "
        "DuckDuckGo; always validate time-sensitive claims before shipping._"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_report(state: S.State, report: TriangulatedReport) -> S.ReportPaths:
    run_dir = S.run_dir(state.run_id)

    # Markdown
    md = render_markdown(state, report)
    md_file = run_dir / "report.md"
    md_file.write_text(md, encoding="utf-8")

    # JSON (structured report + minimal metadata)
    json_payload = {
        "run_id": state.run_id,
        "generated_at": _today_utc(),
        "modules_enabled": state.modules_enabled.model_dump(),
        "report": report.model_dump(mode="json"),
    }
    json_file = run_dir / "report.json"
    json_file.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    paths = S.ReportPaths(md_path="report.md", json_path="report.json")
    state.report = paths
    S.append_history(
        state,
        actor="report_agent",
        action="report_compiled",
        details={
            "verdict": report.headline_verdict,
            "confidence": report.confidence_0_100,
            "md_bytes": len(md.encode("utf-8")),
        },
    )
    S.save(state)
    return paths
