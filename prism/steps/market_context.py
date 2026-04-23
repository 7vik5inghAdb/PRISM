"""Step — Market Context secondary sub-agent."""

from __future__ import annotations

import streamlit as st

from prism import secondary
from prism import state as S
from prism.schemas import MarketContextSynthesis
from prism.steps._secondary_common import gate_or_render, render_citations


def render(state: S.State, step: str) -> None:
    gate_or_render(
        state,
        step,
        step_title="Market Context",
        run_button_label="🧠 Research market context",
        run_fn=lambda st_, on_search: secondary.run_market_context(st_, on_search=on_search),
        render_findings_fn=_render_findings,
        build_orchestrator_payload_fn=_orchestrator_payload,
        next_button_label="Proceed to Charts",
        next_step=S.STEP_CHARTING,
        get_existing_fn=secondary.get_market_context,
    )


def _render_findings(syn: MarketContextSynthesis) -> None:
    st.subheader("Market Context")
    st.markdown(syn.summary)

    st.markdown("**Qualitative sizing:**")
    st.markdown(syn.sizing_qualitative)

    if syn.growth_signals:
        st.markdown("**Growth signals:**")
        for g in syn.growth_signals:
            st.markdown(f"- {g}")
    if syn.audience_behaviors:
        st.markdown("**Audience behaviors:**")
        for b in syn.audience_behaviors:
            st.markdown(f"- {b}")
    if syn.adjacent_trends:
        st.markdown("**Adjacent trends:**")
        for t in syn.adjacent_trends:
            st.markdown(f"- {t}")

    st.markdown("### Citations")
    render_citations(syn.citations)


def _orchestrator_payload(syn: MarketContextSynthesis) -> dict:
    return {
        "growth_signals_count": len(syn.growth_signals),
        "audience_behaviors_count": len(syn.audience_behaviors),
        "adjacent_trends_count": len(syn.adjacent_trends),
        "total_citations": len(syn.citations),
        "web_sourced_citations": sum(1 for c in syn.citations if c.source_type == "web_source"),
    }
