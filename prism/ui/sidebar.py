"""Sidebar: run metadata + pipeline navigation + module toggles + back-to-runs."""

from __future__ import annotations

import streamlit as st

from prism import state as S
from prism.ui import modules as modules_ui, progress as progress_ui
from prism.ui.labels import STATUS_BADGE, STATUS_LABEL, STEP_LABELS


def render(state: S.State) -> None:
    """Render the sidebar for an active run."""
    with st.sidebar:
        st.markdown(f"### 🔬 `{state.run_id}`")
        st.caption(f"Updated {state.updated_at}")

        # Staleness summary (only shown if there are stale steps)
        stale_count = progress_ui.count_stale(state)
        if stale_count:
            st.markdown("---")
            first_stale_step = progress_ui.first_stale(state)
            st.warning(
                f"⚠️ {stale_count} step{'s are' if stale_count != 1 else ' is'} stale. "
                "Upstream changes invalidated downstream work."
            )
            if first_stale_step and st.button(
                f"Jump to first stale step",
                key=f"jump_stale_{state.run_id}",
                use_container_width=True,
            ):
                st.session_state.current_step = first_stale_step
                st.rerun()

        st.markdown("---")
        st.markdown("**Pipeline**")

        current_step = st.session_state.get("current_step", S.STEP_SETUP)

        for step in S.ALL_STEPS:
            status = state.step_status.get(step, S.StepStatus.PENDING)
            badge = STATUS_BADGE[status]
            label = STEP_LABELS[step]

            is_current = current_step == step
            btn_type = "primary" if is_current else "secondary"

            if st.button(
                f"{badge} {label}",
                key=f"nav_{step}",
                use_container_width=True,
                type=btn_type,
                help=f"{STATUS_LABEL[status]}",
            ):
                st.session_state.current_step = step
                st.rerun()

        st.markdown("---")
        with st.expander("Modules", expanded=False):
            selected = modules_ui.checklist_inputs(
                defaults=state.modules_enabled,
                key_prefix=f"sidebar_mods_{state.run_id}",
            )
            if selected != state.modules_enabled.model_dump():
                changed = modules_ui.apply_toggles(state, selected)
                S.save(state)
                if changed:
                    st.toast(
                        f"Updated {len(changed)} step status"
                        f"{'es' if len(changed) != 1 else ''}."
                    )
                st.rerun()

        st.markdown("---")
        if st.button("← All runs", key="back_to_runs", use_container_width=True):
            st.session_state.current_run_id = None
            st.session_state.pop("current_step", None)
            st.rerun()
