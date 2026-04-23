"""Step — Competitive Analysis secondary sub-agent."""

from __future__ import annotations

import streamlit as st

from prism import secondary
from prism import state as S
from prism.schemas import CompetitiveAnalysisSynthesis
from prism.steps._secondary_common import gate_or_render, render_citations
from prism.ui.labels import confidence_badge


def render(state: S.State, step: str) -> None:
    gate_or_render(
        state,
        step,
        step_title="Competitive Analysis",
        run_button_label="🧠 Profile competitors",
        run_fn=lambda st_, on_search: secondary.run_competitive_analysis(st_, on_search=on_search),
        render_findings_fn=_render_findings,
        build_orchestrator_payload_fn=_orchestrator_payload,
        next_button_label="Proceed to Market Context",
        next_step=S.STEP_MARKET_CONTEXT,
        get_existing_fn=secondary.get_competitive,
    )


def _render_findings(syn: CompetitiveAnalysisSynthesis) -> None:
    st.subheader("Competitive Analysis")
    st.markdown(syn.landscape_summary)

    if syn.threats:
        st.markdown("**Threats:**")
        for t in syn.threats:
            st.markdown(f"- {t}")
    if syn.opportunities:
        st.markdown("**Opportunities:**")
        for o in syn.opportunities:
            st.markdown(f"- {o}")

    st.markdown("### Competitors")
    for c in syn.competitors:
        with st.expander(
            f"{c.name} · threat {confidence_badge(c.threat_level_0_100)}",
            expanded=False,
        ):
            st.markdown(f"**Positioning:** {c.positioning}")
            st.markdown("**Relevant offerings:**")
            for o in c.relevant_offerings:
                st.markdown(f"- {o}")
            st.markdown("**Citations:**")
            render_citations(c.citations)


def _orchestrator_payload(syn: CompetitiveAnalysisSynthesis) -> dict:
    return {
        "competitors_count": len(syn.competitors),
        "competitor_names": [c.name for c in syn.competitors],
        "threats_count": len(syn.threats),
        "opportunities_count": len(syn.opportunities),
        "total_citations": sum(len(c.citations) for c in syn.competitors),
    }
