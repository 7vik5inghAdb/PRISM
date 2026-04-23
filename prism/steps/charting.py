"""Step — Charting.

Runs the deterministic chart builder over whatever is in state. Displays the
generated PNGs inline and lets the PM proceed to Report.
"""

from __future__ import annotations

import streamlit as st

from prism import charting as charting_agent
from prism import state as S
from prism.ui import progress


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    status = state.step_status.get(step, S.StepStatus.PENDING)
    if status == S.StepStatus.DISABLED:
        st.info("Charting is disabled. Enable it in the sidebar to run this step.")
        return

    if state.setup is None:
        st.warning("Complete **Setup** first.")
        return

    existing = state.charts or []

    c1, c2 = st.columns([1, 1])
    with c1:
        label = "🎨 Regenerate charts" if existing else "🎨 Generate charts"
        if st.button(label, type="primary", use_container_width=True, key=f"charts_run_{state.run_id}"):
            _run_charts(state)

    # Display current charts
    if existing:
        st.divider()
        st.subheader(f"Charts ({len(existing)})")
        for chart in existing:
            full_path = S.run_dir(state.run_id) / chart.path
            if not full_path.exists():
                st.warning(f"Chart file missing on disk: `{chart.path}`")
                continue
            with st.container(border=True):
                st.markdown(f"**{chart.title}**")
                st.image(str(full_path), use_container_width=True)
                st.caption(chart.description)

    if not existing:
        st.caption(
            "_No charts yet. Click 'Generate charts' to build PNGs from the current "
            "assessments and secondary findings._"
        )
        return

    # Proceed
    st.divider()
    if st.button(
        "Proceed to Report",
        type="primary",
        use_container_width=True,
        key=f"charts_proceed_{state.run_id}",
    ):
        _proceed(state)


def _run_charts(state: S.State) -> None:
    with st.spinner("Generating charts..."):
        try:
            charts = charting_agent.build_charts(state)
        except Exception as e:  # noqa: BLE001
            st.error(f"Chart generation failed: {e}")
            return
    st.success(f"Generated {len(charts)} chart(s).")
    st.rerun()


def _proceed(state: S.State) -> None:
    was_complete = state.step_status.get(S.STEP_CHARTING) == S.StepStatus.COMPLETE
    S.mark_status(state, S.STEP_CHARTING, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_CHARTING)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action="charting_confirmed")
    S.save(state)
    st.session_state.current_step = S.STEP_REPORT
    st.rerun()
