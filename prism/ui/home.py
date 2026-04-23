"""Home view — create new run or open an existing one."""

from __future__ import annotations

import re

import streamlit as st

from prism import state as S
from prism.ui import modules as modules_ui


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def render() -> None:
    st.title("🔬 PRISM")
    st.caption(
        "Synthetic research agency for culturalization A/B validation. "
        "Start a new run or reopen an existing one."
    )

    col_new, col_list = st.columns([1, 1])

    with col_new:
        st.subheader("Start a new run")
        with st.form("new_run", clear_on_submit=False):
            run_id = st.text_input(
                "Run ID",
                placeholder="express_jp_2026_04",
                help="Letters, numbers, dots, underscores, and hyphens only.",
            )
            st.markdown("---")
            selected = modules_ui.checklist_inputs(
                defaults=S.ModulesEnabled(),
                key_prefix="new_run",
            )
            submitted = st.form_submit_button("Create run", type="primary")
            if submitted:
                if not run_id:
                    st.error("Run ID is required.")
                elif not _RUN_ID_RE.match(run_id):
                    st.error("Run ID must be [A-Za-z0-9_.-]+.")
                elif S.exists(run_id):
                    st.error(f"Run '{run_id}' already exists. Pick a different ID or open the existing one.")
                else:
                    S.new_run(
                        run_id,
                        modules_enabled=S.ModulesEnabled(**selected),
                    )
                    st.session_state.current_run_id = run_id
                    st.session_state.current_step = S.STEP_SETUP
                    st.rerun()

    with col_list:
        st.subheader("Existing runs")
        v1_runs = S.list_runs()
        if not v1_runs:
            st.caption("_No v1 runs yet._")
        else:
            for rid in v1_runs:
                if st.button(f"📂  {rid}", key=f"open_{rid}", use_container_width=True):
                    st.session_state.current_run_id = rid
                    st.session_state.current_step = S.STEP_SETUP
                    st.rerun()

        legacy = S.list_legacy_runs()
        if legacy:
            with st.expander(f"Legacy v0 runs ({len(legacy)}) — read only", expanded=False):
                st.caption(
                    "These runs were created before the v1 state format. Their "
                    "per-step JSONs are preserved on disk for reference but are "
                    "not openable in this UI."
                )
                for rid in legacy:
                    st.markdown(f"- `{rid}`")
