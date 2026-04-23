"""The conversational orchestrator.

The orchestrator is the layer that talks to the PM between pipeline steps.
It does three things:

1. **Confirm** — When the PM submits a form for step X, the orchestrator uses
   an LLM to produce a structured summary of what was captured. The PM reads
   this, may request edits, then clicks "Proceed" to lock the step.
2. **Suggest** — The summary may include questions or edit suggestions based
   on cross-checks against the full run state.
3. **Remember** — Every orchestrator message is persisted into `state.history`
   with `actor="orchestrator"`, so the conversation survives browser reloads
   and is part of the audit trail.

The orchestrator itself never writes payload fields — only the step modules do.
It writes to `state.history` and nothing else.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from prism import state as S
from prism.llm import call_structured


# Default model for orchestrator reasoning — Opus 4.7 without thinking to stay snappy.
# Override via kwargs at the call site if a step wants deeper analysis.
ORCHESTRATOR_MODEL = "claude-haiku-4-5"

ACTION_ORCHESTRATOR_MESSAGE = "orchestrator_message"


class OrchestratorSummary(BaseModel):
    """Orchestrator's post-submit confirmation."""

    summary_markdown: str = Field(description="3-6 bullets restating what was captured.")
    questions_before_proceeding: list[str] = Field(
        default_factory=list,
        description="Blocking questions. Empty = OK to proceed.",
    )
    suggested_edits: list[str] = Field(
        default_factory=list,
        description="Optional concrete tweaks.",
    )
    ready_to_proceed: bool = Field(description="True if no blocking questions.")


_SYSTEM = (
    "You confirm each PRISM pipeline step. Restate what the PM submitted in 3-6 "
    "bullets. Flag inconsistencies in `questions_before_proceeding` and set "
    "`ready_to_proceed=false` if blocking. Be terse. Don't invent data."
)


def summarize_step(
    state: S.State,
    step: str,
    payload: dict[str, Any],
    *,
    model: Optional[str] = None,
) -> OrchestratorSummary:
    """Confirm PM's submission for `step`."""
    # Only pass a lean context — step status + setup summary, not the full state blob.
    lean_state = {
        "step_status": {k: v.value for k, v in state.step_status.items()},
        "setup_summary": _setup_brief(state),
    }
    user_prompt = (
        f"Step: `{step}`\n\n"
        f"Submission:\n```json\n{_safe_json(payload)}\n```\n\n"
        f"Run context:\n```json\n{_safe_json(lean_state)}\n```"
    )
    return call_structured(
        model=model or ORCHESTRATOR_MODEL,
        system=_SYSTEM,
        user_content=user_prompt,
        response_model=OrchestratorSummary,
        max_tokens=2000,
    )


def _setup_brief(state: S.State) -> Optional[dict]:
    """Compact setup view for cross-checks. None if setup not done."""
    if state.setup is None:
        return None
    s = state.setup
    return {
        "hypothesis": s.hypothesis,
        "source": s.source_market.locale,
        "targets": [m.locale for m in s.target_markets],
        "variant_ids": [v.id for v in s.variants],
    }


def record_message(
    state: S.State,
    step: str,
    summary: OrchestratorSummary,
) -> None:
    """Persist an orchestrator summary into state.history."""
    S.append_history(
        state,
        actor="orchestrator",
        action=ACTION_ORCHESTRATOR_MESSAGE,
        details={
            "step": step,
            "summary_markdown": summary.summary_markdown,
            "questions_before_proceeding": summary.questions_before_proceeding,
            "suggested_edits": summary.suggested_edits,
            "ready_to_proceed": summary.ready_to_proceed,
        },
    )


def latest_message_for(state: S.State, step: str) -> Optional[dict[str, Any]]:
    """Return the most recent orchestrator message for this step, or None."""
    for entry in reversed(state.history):
        if (
            entry.actor == "orchestrator"
            and entry.action == ACTION_ORCHESTRATOR_MESSAGE
            and entry.details.get("step") == step
        ):
            return entry.details
    return None


def all_messages_for(state: S.State, step: str) -> list[dict[str, Any]]:
    """All orchestrator messages for this step, chronological."""
    return [
        entry.details
        for entry in state.history
        if entry.actor == "orchestrator"
        and entry.action == ACTION_ORCHESTRATOR_MESSAGE
        and entry.details.get("step") == step
    ]


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _safe_json(obj: Any) -> str:
    """JSON-serialize with sane defaults; truncate large blobs defensively."""
    import json

    try:
        s = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(obj)
    # Guard against giant blobs — truncate at 8k chars (lean mode).
    if len(s) > 8_000:
        s = s[:8_000] + "\n... (truncated)"
    return s
