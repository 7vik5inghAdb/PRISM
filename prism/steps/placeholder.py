"""Placeholder step — shown for any step whose implementation hasn't landed yet."""

from __future__ import annotations

import streamlit as st

from prism import state as S
from prism.ui import chat, progress
from prism.ui.labels import STEP_LABELS, STATUS_BADGE, STATUS_LABEL


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    status = state.step_status.get(step, S.StepStatus.PENDING)
    label = STEP_LABELS.get(step, step)

    if status == S.StepStatus.DISABLED:
        st.info(
            f"This step is disabled — the **{_module_name(step)}** module is "
            f"turned off in the run setup. Re-enable it to run this step."
        )
    else:
        st.info(
            f"**{label}** is not yet implemented in this checkpoint.\n\n"
            f"This view will be filled in during a later step of the PRISM v1 rebuild."
        )

    with st.expander("Details", expanded=False):
        st.markdown(f"- **Step key:** `{step}`")
        st.markdown(
            f"- **Status:** {STATUS_BADGE[status]} {STATUS_LABEL[status]}"
        )

    # Show any existing orchestrator messages for this step (e.g. from prior sessions).
    st.divider()
    had_any = False
    messages = [
        h
        for h in state.history
        if h.actor == "orchestrator" and h.details.get("step") == step
    ]
    for entry in messages:
        chat.render_orchestrator_message(entry.details)
        had_any = True
    if not had_any:
        st.caption("_No orchestrator messages for this step yet._")


def _module_name(step: str) -> str:
    return {
        S.STEP_CULTURAL_RISK: "Cultural Risk",
        S.STEP_COMPETITIVE: "Competitive Analysis",
        S.STEP_MARKET_CONTEXT: "Market Context",
        S.STEP_CHARTING: "Charting",
    }.get(step, step)
