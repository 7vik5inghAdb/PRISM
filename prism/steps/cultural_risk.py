"""Step — Cultural Risk secondary sub-agent."""

from __future__ import annotations

import streamlit as st

from prism import secondary
from prism import state as S
from prism.schemas import CulturalRiskSynthesis
from prism.steps._secondary_common import gate_or_render, render_citations
from prism.ui.labels import confidence_badge


def render(state: S.State, step: str) -> None:
    gate_or_render(
        state,
        step,
        step_title="Cultural Risk",
        run_button_label="🧠 Research cultural risks",
        run_fn=lambda st_, on_search: secondary.run_cultural_risk(st_, on_search=on_search),
        render_findings_fn=_render_findings,
        build_orchestrator_payload_fn=_orchestrator_payload,
        next_button_label="Proceed to Competitive Analysis",
        next_step=S.STEP_COMPETITIVE,
        get_existing_fn=secondary.get_cultural_risk,
    )


def _render_findings(syn: CulturalRiskSynthesis) -> None:
    st.subheader(f"Cultural Risk — overall {confidence_badge(syn.overall_risk_0_100)}")
    st.markdown(syn.summary)

    for i, f in enumerate(syn.findings):
        markets_str = ", ".join(f.affected_markets)
        with st.expander(
            f"{f.title} · severity {confidence_badge(f.severity_0_100)} · markets: {markets_str}",
            expanded=False,
        ):
            st.markdown(f.description)
            st.markdown("**Citations:**")
            render_citations(f.citations)


def _orchestrator_payload(syn: CulturalRiskSynthesis) -> dict:
    return {
        "overall_risk_0_100": syn.overall_risk_0_100,
        "findings_count": len(syn.findings),
        "findings_titles": [f.title for f in syn.findings],
        "total_citations": sum(len(f.citations) for f in syn.findings),
        "web_sourced_citations": sum(
            1 for f in syn.findings for c in f.citations if c.source_type == "web_source"
        ),
    }
