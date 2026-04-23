"""PRISM v1 Streamlit entry point.

Run with: `streamlit run app.py` from the repo root.

The app is a thin router:
- If no run is selected, show the home/picker view.
- If a run is selected, load its state.json, render the sidebar, and dispatch
  to the current step's view.
"""

from __future__ import annotations

import streamlit as st

from prism import state as S
from prism.steps import render_step
from prism.ui import home, sidebar


def main() -> None:
    st.set_page_config(
        page_title="PRISM",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Session-scoped navigation state
    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None
    if "current_step" not in st.session_state:
        st.session_state.current_step = S.STEP_SETUP

    run_id = st.session_state.current_run_id

    if run_id is None:
        home.render()
        return

    try:
        state = S.load(run_id)
    except FileNotFoundError:
        st.error(f"Run '{run_id}' no longer exists on disk.")
        st.session_state.current_run_id = None
        if st.button("Back to runs"):
            st.rerun()
        return

    sidebar.render(state)

    current_step = st.session_state.get("current_step", S.STEP_SETUP)
    render_step(state, current_step)


if __name__ == "__main__":
    main()
