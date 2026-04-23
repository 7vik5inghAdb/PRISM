"""Chat-style orchestrator bubbles for step confirmations."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from prism import orchestrator


def render_orchestrator_message(details: dict[str, Any]) -> None:
    """Render a single orchestrator message dict (from state.history)."""
    with st.chat_message("assistant", avatar="🧭"):
        st.markdown(details.get("summary_markdown", "_no summary_"))

        questions = details.get("questions_before_proceeding") or []
        if questions:
            st.markdown("**Questions before proceeding:**")
            for q in questions:
                st.markdown(f"- {q}")

        suggestions = details.get("suggested_edits") or []
        if suggestions:
            st.markdown("**Suggested edits:**")
            for s in suggestions:
                st.markdown(f"- {s}")

        ready = details.get("ready_to_proceed")
        if ready is False:
            st.warning("Orchestrator is not ready to proceed.")
        elif ready is True and not questions:
            st.success("Ready to proceed.")


def render_history_for(state, step: str) -> None:
    """Render all orchestrator messages for a step as a chat trail."""
    messages = orchestrator.all_messages_for(state, step)
    if not messages:
        return
    for details in messages:
        render_orchestrator_message(details)


def render_latest_for(state, step: str) -> Optional[dict[str, Any]]:
    """Render only the most recent orchestrator message. Returns the details (or None)."""
    details = orchestrator.latest_message_for(state, step)
    if details is None:
        return None
    render_orchestrator_message(details)
    return details
