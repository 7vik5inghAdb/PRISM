"""Step — Triangulated Report.

Compiles the final report from every enabled module that completed.
Renders both files (report.md + report.json) and shows the markdown inline
with download buttons.
"""

from __future__ import annotations

import streamlit as st

from prism import report as report_agent
from prism import state as S
from prism.schemas import TriangulatedReport
from prism.ui import progress
from prism.ui.labels import confidence_badge


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None:
        st.warning("Complete **Setup** first.")
        return

    # Minimum: need at least one per-market assessment
    from prism.aggregator import get_all_assessments

    per_market = get_all_assessments(state)
    if not per_market:
        st.warning("Complete at least one **Primary Assessment** before compiling the report.")
        return

    existing = report_agent.get_report(state)

    # Warn about any stale upstream steps. Report compilation against stale
    # inputs is allowed (PM might want a preview), but we want them to know.
    stale_upstream = [
        s
        for s in S.ALL_STEPS
        if s != S.STEP_REPORT and state.step_status.get(s) == S.StepStatus.STALE
    ]
    if stale_upstream:
        from prism.ui.labels import STEP_LABELS

        st.warning(
            "⚠️ Some upstream steps are stale: "
            + ", ".join(f"`{STEP_LABELS.get(s, s)}`" for s in stale_upstream)
            + ". Re-compiling the report now will use the previous outputs of those "
            "steps. Re-run them first for an up-to-date report."
        )

    c1, c2 = st.columns([1, 1])
    with c1:
        label = "📝 Recompile report" if existing is not None else "📝 Compile report"
        if st.button(label, type="primary", use_container_width=True, key=f"report_run_{state.run_id}"):
            _compile(state)

    # Display
    if existing is None:
        st.caption(
            "_No report yet. Click 'Compile report' to generate report.md + report.json "
            "from the current state._"
        )
        return

    # Badges
    verdict_badge = {
        "pass": "✅ PASS",
        "fail": "❌ FAIL",
        "needs_revision": "⚠️ NEEDS REVISION",
    }[existing.headline_verdict]
    st.markdown(f"### {verdict_badge} · confidence {confidence_badge(existing.confidence_0_100)}")

    # Download buttons
    md_path = S.run_dir(state.run_id) / "report.md"
    json_path = S.run_dir(state.run_id) / "report.json"

    dc1, dc2 = st.columns(2)
    if md_path.exists():
        with dc1:
            st.download_button(
                "⬇️ Download report.md",
                data=md_path.read_bytes(),
                file_name=f"{state.run_id}_report.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"dl_md_{state.run_id}",
            )
    if json_path.exists():
        with dc2:
            st.download_button(
                "⬇️ Download report.json",
                data=json_path.read_bytes(),
                file_name=f"{state.run_id}_report.json",
                mime="application/json",
                use_container_width=True,
                key=f"dl_json_{state.run_id}",
            )

    st.divider()

    # Inline rendering: text sections via st.markdown + charts via st.image.
    # We build the rendering from state directly (not by re-parsing the .md file).
    _render_inline(state, existing)

    # Mark complete
    if state.step_status.get(S.STEP_REPORT) != S.StepStatus.COMPLETE:
        st.divider()
        if st.button(
            "Mark report complete",
            type="primary",
            use_container_width=True,
            key=f"report_done_{state.run_id}",
        ):
            _mark_complete(state)


def _compile(state: S.State) -> None:
    with st.spinner("Compiling triangulated report..."):
        try:
            report = report_agent.compile_report(state)
            report_agent.save_report(state, report)
        except Exception as e:  # noqa: BLE001
            st.error(f"Report compilation failed: {e}")
            return
    st.success("Report compiled.")
    st.rerun()


def _mark_complete(state: S.State) -> None:
    S.mark_status(state, S.STEP_REPORT, S.StepStatus.COMPLETE)
    S.append_history(state, actor="pm", action="report_confirmed")
    S.save(state)
    st.toast("Report marked complete.")
    st.rerun()


# ---------------------------------------------------------------------------
# Inline rendering (Streamlit widgets, not raw MD)
# ---------------------------------------------------------------------------


def _render_inline(state: S.State, report: TriangulatedReport) -> None:
    from prism.aggregator import get_all_assessments, get_cross_market
    from prism.secondary import get_competitive, get_cultural_risk, get_market_context
    from prism.steps._secondary_common import render_citations

    me = state.modules_enabled

    # Executive
    st.markdown("## Executive Summary")
    st.markdown(report.executive_summary)

    st.markdown("## Recommended Actions")
    for a in report.recommended_actions:
        st.markdown(f"- {a}")

    if report.open_questions:
        st.markdown("## Open Questions")
        for q in report.open_questions:
            st.markdown(f"- {q}")

    st.divider()

    # Primary
    st.markdown("## Primary Findings (Synthetic Panel)")
    st.markdown(report.primary_findings_summary)

    per_market = get_all_assessments(state)
    for locale in sorted(per_market.keys()):
        a = per_market[locale]
        v_emoji = {"pass": "🟢", "fail": "🔴", "needs_revision": "🟡"}[a.verdict]
        with st.expander(
            f"{v_emoji} {locale} — {a.verdict.upper()} · confidence {a.confidence_0_100}/100",
            expanded=False,
        ):
            st.markdown(f"**Winning variant:** `{a.winning_variant_id}`")
            rows = []
            for vid in sorted(a.variant_top_rank_shares.keys()):
                rows.append(
                    {
                        "Variant": vid,
                        "Top-rank share": f"{a.variant_top_rank_shares.get(vid, 0):.0%}",
                        "Mean score": f"{a.variant_mean_scores.get(vid, 0):.1f}",
                    }
                )
            st.dataframe(rows, hide_index=True, use_container_width=True)
            st.markdown(f"**Rationale:** {a.rationale}")
            st.markdown(f"**Recommended next step:** {a.recommended_next_step}")
            if a.cultural_red_flags:
                st.markdown("**Red flags:**")
                for f in a.cultural_red_flags:
                    st.markdown(f"- {f}")

    cross = get_cross_market(state)
    if cross is not None:
        with st.expander(
            f"🔀 Cross-market — confidence {cross.confidence_0_100}/100",
            expanded=False,
        ):
            st.markdown(
                f"**Consistent winners:** {', '.join(cross.consistent_winners) or '(none)'}"
            )
            st.markdown(f"**Rationale:** {cross.cross_market_rationale}")
            st.markdown(f"**Recommended next step:** {cross.recommended_next_step}")
            if cross.divergent_findings:
                st.markdown("**Divergent findings:**")
                for d in cross.divergent_findings:
                    st.markdown(f"- {d}")

    # Secondary
    secondary_shown = False
    if me.cultural_risk and report.cultural_risk_summary:
        cr = get_cultural_risk(state)
        if cr is not None:
            if not secondary_shown:
                st.divider()
                st.markdown("## Secondary Synthesis")
                secondary_shown = True
            st.markdown(f"### Cultural Risk — overall {cr.overall_risk_0_100}/100")
            st.markdown(report.cultural_risk_summary)
            for f in cr.findings:
                with st.expander(
                    f"{f.title} · severity {f.severity_0_100}/100 · markets: "
                    f"{', '.join(f.affected_markets)}",
                    expanded=False,
                ):
                    st.markdown(f.description)
                    render_citations(f.citations)

    if me.competitive_analysis and report.competitive_summary:
        ca = get_competitive(state)
        if ca is not None:
            if not secondary_shown:
                st.divider()
                st.markdown("## Secondary Synthesis")
                secondary_shown = True
            st.markdown("### Competitive Analysis")
            st.markdown(report.competitive_summary)
            st.markdown(f"**Landscape:** {ca.landscape_summary}")
            if ca.threats:
                st.markdown("**Threats:**")
                for t in ca.threats:
                    st.markdown(f"- {t}")
            if ca.opportunities:
                st.markdown("**Opportunities:**")
                for o in ca.opportunities:
                    st.markdown(f"- {o}")
            for c in ca.competitors:
                with st.expander(
                    f"{c.name} · threat {c.threat_level_0_100}/100",
                    expanded=False,
                ):
                    st.markdown(f"**Positioning:** {c.positioning}")
                    st.markdown("**Relevant offerings:**")
                    for o in c.relevant_offerings:
                        st.markdown(f"- {o}")
                    render_citations(c.citations)

    if me.market_context and report.market_context_summary:
        mc = get_market_context(state)
        if mc is not None:
            if not secondary_shown:
                st.divider()
                st.markdown("## Secondary Synthesis")
                secondary_shown = True
            st.markdown("### Market Context")
            st.markdown(report.market_context_summary)
            st.markdown(f"**Qualitative sizing:** {mc.sizing_qualitative}")
            if mc.growth_signals:
                st.markdown("**Growth signals:**")
                for g in mc.growth_signals:
                    st.markdown(f"- {g}")
            if mc.audience_behaviors:
                st.markdown("**Audience behaviors:**")
                for b in mc.audience_behaviors:
                    st.markdown(f"- {b}")
            if mc.adjacent_trends:
                st.markdown("**Adjacent trends:**")
                for t in mc.adjacent_trends:
                    st.markdown(f"- {t}")
            st.markdown("**Citations:**")
            render_citations(mc.citations)

    st.divider()

    # Convergence
    st.markdown("## Convergence Analysis")
    st.markdown(report.convergence_analysis)

    # Cultural red flags
    if report.cultural_red_flags:
        st.markdown("## Cultural Red Flags")
        for f in report.cultural_red_flags:
            st.markdown(f"- {f}")

    # Charts
    if me.charting and state.charts:
        st.divider()
        st.markdown("## Charts")
        for c in state.charts:
            full = S.run_dir(state.run_id) / c.path
            if not full.exists():
                continue
            with st.container(border=True):
                st.markdown(f"**{c.title}**")
                st.image(str(full), use_container_width=True)
                st.caption(c.description)
