"""Shared render helpers for the three secondary sub-agent step views."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from prism import orchestrator
from prism import state as S
from prism.ui import chat, progress
from prism.ui.labels import confidence_badge


def gate_or_render(
    state: S.State,
    step: str,
    *,
    step_title: str,
    run_button_label: str,
    run_fn: Callable[[S.State, Callable[[str, int], None]], Any],
    render_findings_fn: Callable[[Any], None],
    build_orchestrator_payload_fn: Callable[[Any], dict],
    next_button_label: str,
    next_step: str,
    get_existing_fn: Callable[[S.State], Any],
) -> None:
    """Shared flow for a secondary sub-agent step."""
    progress.header(state, step)

    # Module disabled short-circuit
    status = state.step_status.get(step, S.StepStatus.PENDING)
    if status == S.StepStatus.DISABLED:
        st.info(f"This module is disabled. Enable it in the sidebar to run {step_title}.")
        return

    # Gate on setup (and optionally assessment) — a minimum of setup is enough
    if state.setup is None:
        st.warning("Complete **Setup** first.")
        return

    existing = get_existing_fn(state)

    # --- Run button / rerun ---
    label = f"🧠 Re-run {step_title}" if existing is not None else run_button_label
    if st.button(label, type="primary", use_container_width=True, key=f"sec_run_{step}_{state.run_id}"):
        _run_with_live_log(state, step, run_fn)

    # --- Render current findings ---
    if existing is not None:
        st.divider()
        render_findings_fn(existing)

    # --- Search log (last N) ---
    with st.expander("Search log", expanded=False):
        _render_search_log(state, step)

    # --- Review + proceed ---
    review_key = f"sec_review_{step}_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    if existing is not None and not in_review:
        st.divider()
        if st.button(
            "Review before proceeding",
            use_container_width=True,
            key=f"sec_submit_{step}_{state.run_id}",
        ):
            _handle_submit(
                state, step, existing, build_orchestrator_payload_fn, review_key
            )

    if in_review:
        st.divider()
        st.subheader("Orchestrator review")
        details = orchestrator.latest_message_for(state, step)
        if details:
            chat.render_orchestrator_message(details)

        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                next_button_label,
                type="primary",
                use_container_width=True,
                key=f"sec_proceed_{step}_{state.run_id}",
            ):
                _proceed(state, step, next_step, review_key)
        with c2:
            if st.button(
                "Back",
                use_container_width=True,
                key=f"sec_edit_{step}_{state.run_id}",
            ):
                st.session_state[review_key] = False
                st.rerun()

    # Show last orchestrator bubble below when not in active review
    if not in_review:
        prior = orchestrator.latest_message_for(state, step)
        if prior is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior)


def _run_with_live_log(
    state: S.State,
    step: str,
    run_fn: Callable[[S.State, Callable[[str, int], None]], Any],
) -> None:
    """Run the sub-agent with a live-updating search log."""
    status_box = st.status(f"Running secondary agent…", expanded=True)
    log_container = status_box.container()
    counter = {"n": 0}

    def on_search(query: str, result_count: int) -> None:
        counter["n"] += 1
        with log_container:
            st.markdown(
                f"🔎 **Search #{counter['n']}**: `{query}` → {result_count} results"
            )

    try:
        run_fn(state, on_search)
    except Exception as e:  # noqa: BLE001
        status_box.update(label=f"Agent failed: {e}", state="error")
        return

    status_box.update(
        label=f"Agent done — {counter['n']} web searches performed.",
        state="complete",
    )
    st.rerun()


def _render_search_log(state: S.State, step: str) -> None:
    actor_map = {
        S.STEP_CULTURAL_RISK: "cultural_risk_agent",
        S.STEP_COMPETITIVE: "competitive_agent",
        S.STEP_MARKET_CONTEXT: "market_context_agent",
    }
    actor = actor_map.get(step)
    if actor is None:
        return

    entries = [
        h
        for h in state.history
        if h.actor == actor and h.action == "web_search"
    ]
    if not entries:
        st.caption("_No searches yet._")
        return

    rows = [
        {
            "#": i + 1,
            "Query": h.details.get("query", ""),
            "Results": h.details.get("result_count", 0),
        }
        for i, h in enumerate(entries[-30:])
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _handle_submit(
    state: S.State,
    step: str,
    existing: Any,
    build_orchestrator_payload_fn: Callable[[Any], dict],
    review_key: str,
) -> None:
    payload = build_orchestrator_payload_fn(existing)
    with st.spinner("Orchestrator reviewing..."):
        try:
            summary = orchestrator.summarize_step(state, step, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return
    orchestrator.record_message(state, step, summary)
    S.save(state)
    st.session_state[review_key] = True
    st.rerun()


def _proceed(state: S.State, step: str, next_step: str, review_key: str) -> None:
    was_complete = state.step_status.get(step) == S.StepStatus.COMPLETE
    S.mark_status(state, step, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, step)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action=f"{step}_confirmed")
    S.save(state)
    st.session_state.pop(review_key, None)
    st.session_state.current_step = next_step
    st.rerun()


# ---------------------------------------------------------------------------
# Shared citation renderer
# ---------------------------------------------------------------------------


def render_citations(citations: list) -> None:
    if not citations:
        st.caption("_No citations._")
        return
    rows = []
    for c in citations:
        rows.append(
            {
                "Type": c.source_type,
                "Confidence": confidence_badge(c.confidence_0_100),
                "Claim": c.claim,
                "URL": c.source_url or "",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)
