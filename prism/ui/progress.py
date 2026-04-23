"""Compact progress header shown at the top of each step view.

Also renders the staleness banner when the current step is stale, so the PM
can see at a glance that they need to re-run after upstream changes.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from prism import state as S
from prism.ui.labels import STATUS_BADGE, STEP_LABELS


def header(state: S.State, step: str) -> None:
    """Title bar + progress meter + stale banner for the current step."""
    summary = S.progress_summary(state)
    counts = summary["counts"]
    total_active = sum(v for k, v in counts.items() if k != "disabled")
    done = counts.get("complete", 0)
    status = state.step_status.get(step, S.StepStatus.PENDING)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"## {STATUS_BADGE[status]} {STEP_LABELS[step]}")
        st.caption(f"Run `{state.run_id}`")
    with col2:
        progress_value = done / total_active if total_active else 0.0
        st.progress(progress_value, text=f"{done}/{total_active} steps complete")

    # Stale banner
    if status == S.StepStatus.STALE:
        cause = stale_cause(state, step)
        cause_txt = f"`{STEP_LABELS.get(cause, cause)}`" if cause else "an earlier step"
        st.warning(
            f"⚠️ This step is **stale** — {cause_txt} was re-run after it was "
            "last completed. Re-run this step to refresh its output. Doing so "
            "will also mark any downstream steps stale."
        )


def stale_cause(state: S.State, step: str) -> Optional[str]:
    """Walk `state.history` backward to find the most recent upstream step whose
    re-run caused `step` to become stale. Returns the step key, or None."""
    for entry in reversed(state.history):
        if (
            entry.action == "downstream_stale"
            and step in entry.details.get("affected", [])
        ):
            return entry.details.get("triggered_by")
    return None


def count_stale(state: S.State) -> int:
    return sum(1 for s in state.step_status.values() if s == S.StepStatus.STALE)


def first_stale(state: S.State) -> Optional[str]:
    """Return the first stale step in pipeline order, or None."""
    for step in S.ALL_STEPS:
        if state.step_status.get(step) == S.StepStatus.STALE:
            return step
    return None
