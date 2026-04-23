"""Step — Research Method Selection.

UI flow:

1. **Axes** — four checkboxes (qual / quant / behavioral / attitudinal). PM
   may select any combination.
2. **Methods** — the 11 methods from the spec, ranked by how many selected
   axes each covers. PM picks one or more.
3. **Research questions** — PM clicks "Generate questions". An Opus 4.7 agent
   produces 4-6 questions tied to the hypothesis + axes + methods. PM edits,
   adds, or removes questions inline.
4. **Review & proceed** — orchestrator confirmation, same pattern as Setup.

Like Setup, the draft lives in `st.session_state` until the PM clicks Proceed.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from pydantic import ValidationError

from prism import method as method_agent
from prism import orchestrator
from prism import state as S
from prism.ui import chat, progress


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None:
        st.warning("Complete the **Setup** step first — method selection depends on the hypothesis and markets.")
        return

    review_key = f"method_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    _ensure_draft_initialized(state)

    _render_form(state)

    if in_review:
        st.divider()
        _render_review(state)
    else:
        prior_msg = orchestrator.latest_message_for(state, S.STEP_METHOD)
        if prior_msg is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior_msg)


# ---------------------------------------------------------------------------
# Draft
# ---------------------------------------------------------------------------


def _dk(name: str, state: S.State) -> str:
    return f"method_{name}_{state.run_id}"


def _ensure_draft_initialized(state: S.State) -> None:
    if st.session_state.get(_dk("initialized", state)):
        return

    m = state.method
    if m is not None:
        axes_sel = [k for k in method_agent.AXIS_KEYS if getattr(m.axes, k)]
        st.session_state[_dk("axes", state)] = set(axes_sel)
        st.session_state[_dk("methods", state)] = set(m.selected_methods)
        st.session_state[_dk("questions", state)] = list(m.research_questions)
    else:
        st.session_state[_dk("axes", state)] = set()
        st.session_state[_dk("methods", state)] = set()
        st.session_state[_dk("questions", state)] = []

    st.session_state[_dk("rationale", state)] = ""
    st.session_state[_dk("initialized", state)] = True


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------


def _render_form(state: S.State) -> None:
    st.markdown(
        "Choose the methodological axes and concrete methods for this run. "
        "Axes shape what kinds of questions the panel can answer; methods "
        "shape the instrument the next step generates."
    )

    # --- Axes ---
    st.subheader("Axes")
    st.caption("Select any combination. You can pick from both dimensions simultaneously.")
    c1, c2 = st.columns(2)
    current_axes: set[str] = st.session_state[_dk("axes", state)]

    with c1:
        st.markdown("**What you measure**")
        for key in ("qualitative", "quantitative"):
            checked = st.checkbox(
                method_agent.AXIS_LABELS[key],
                value=(key in current_axes),
                key=f"axis_{state.run_id}_{key}",
            )
            _toggle_in_set(current_axes, key, checked)

    with c2:
        st.markdown("**What you observe**")
        for key in ("behavioral", "attitudinal"):
            checked = st.checkbox(
                method_agent.AXIS_LABELS[key],
                value=(key in current_axes),
                key=f"axis_{state.run_id}_{key}",
            )
            _toggle_in_set(current_axes, key, checked)

    # --- Methods ---
    st.subheader("Methods")
    st.caption(
        "Methods are ranked by how many selected axes each covers. Top-ranked "
        "methods are highlighted — but you can pick any."
    )

    selected_methods: set[str] = st.session_state[_dk("methods", state)]
    ranked = method_agent.methods_matching_axes(list(current_axes))
    max_overlap = max((score for _, score in ranked), default=0)

    cols = st.columns(3)
    for idx, (mkey, overlap) in enumerate(ranked):
        with cols[idx % 3]:
            is_top = max_overlap > 0 and overlap == max_overlap
            label_prefix = "⭐ " if is_top else ""
            axis_tags = " · ".join(
                method_agent.AXIS_LABELS[a] for a in sorted(method_agent.METHOD_AXES[mkey])
            )
            checked = st.checkbox(
                f"{label_prefix}{method_agent.METHOD_LABELS[mkey]}",
                value=(mkey in selected_methods),
                key=f"method_{state.run_id}_{mkey}",
                help=axis_tags,
            )
            _toggle_in_set(selected_methods, mkey, checked)
            st.caption(axis_tags)

    # --- Research questions ---
    st.subheader("Research questions")
    st.caption(
        "Concrete questions the downstream instrument and panel will answer. "
        "Generate a starting set from your hypothesis + chosen methods, then edit freely."
    )

    questions: list[str] = st.session_state[_dk("questions", state)]
    rationale: str = st.session_state.get(_dk("rationale", state), "")

    gen_col, add_col = st.columns([1, 1])
    with gen_col:
        if st.button(
            "🧠 Generate questions from hypothesis",
            key=f"method_generate_{state.run_id}",
            use_container_width=True,
        ):
            _generate_questions(state)
    with add_col:
        if st.button(
            "+ Add blank question",
            key=f"method_add_q_{state.run_id}",
            use_container_width=True,
        ):
            questions.append("")
            st.rerun()

    if rationale:
        with st.expander("Why these questions", expanded=False):
            st.markdown(rationale)

    to_remove: list[int] = []
    for i, q in enumerate(questions):
        qc1, qc2 = st.columns([6, 0.4])
        with qc1:
            questions[i] = st.text_area(
                f"Q{i+1}",
                value=q,
                key=f"q_{state.run_id}_{i}",
                label_visibility="collapsed",
                height=68,
            )
        with qc2:
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("✕", key=f"q_rm_{state.run_id}_{i}", help="Remove question"):
                to_remove.append(i)

    for idx in reversed(to_remove):
        questions.pop(idx)
    if to_remove:
        st.rerun()

    # --- Submit ---
    st.divider()
    if st.button(
        "Review before proceeding",
        key=f"method_submit_{state.run_id}",
        type="primary",
    ):
        _handle_submit(state)


def _toggle_in_set(s: set[str], key: str, checked: bool) -> None:
    if checked:
        s.add(key)
    else:
        s.discard(key)


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------


def _generate_questions(state: S.State) -> None:
    setup = state.setup
    if setup is None:
        st.error("Setup is not complete.")
        return

    axes = sorted(st.session_state[_dk("axes", state)])
    methods = sorted(st.session_state[_dk("methods", state)])

    if not axes:
        st.error("Select at least one axis before generating questions.")
        return
    if not methods:
        st.error("Select at least one method before generating questions.")
        return

    with st.spinner("Generating research questions from your hypothesis..."):
        try:
            result = method_agent.generate_research_questions(
                hypothesis=setup.hypothesis,
                source_locale=setup.source_market.locale,
                source_country=setup.source_market.country,
                target_markets=[
                    {"locale": m.locale, "country": m.country}
                    for m in setup.target_markets
                ],
                selected_axes=axes,
                selected_methods=methods,
                product_context=setup.product_context.model_dump(),
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"Question generation failed: {e}")
            return

    st.session_state[_dk("questions", state)] = list(result.questions)
    st.session_state[_dk("rationale", state)] = result.rationale
    S.append_history(
        state,
        actor="method_agent",
        action="research_questions_generated",
        details={
            "count": len(result.questions),
            "axes": axes,
            "methods": methods,
        },
    )
    S.save(state)
    st.rerun()


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def _collect_payload(state: S.State) -> dict[str, Any]:
    axes_sel = st.session_state[_dk("axes", state)]
    return {
        "axes": {k: (k in axes_sel) for k in method_agent.AXIS_KEYS},
        "selected_methods": sorted(st.session_state[_dk("methods", state)]),
        "research_questions": [
            q.strip() for q in st.session_state[_dk("questions", state)] if q.strip()
        ],
    }


def _local_validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not any(payload["axes"].values()):
        errors.append("Select at least one axis.")
    if not payload["selected_methods"]:
        errors.append("Select at least one method.")
    if len(payload["research_questions"]) < 1:
        errors.append("At least one research question is required.")
    for q in payload["research_questions"]:
        if len(q) < 10:
            errors.append(f"Research question is too short: '{q}'")
    return errors


def _handle_submit(state: S.State) -> None:
    payload = _collect_payload(state)

    try:
        S.Method.model_validate(payload)
    except ValidationError as e:
        st.error("Method payload failed schema validation:")
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            st.markdown(f"- `{loc}`: {err['msg']}")
        return

    errs = _local_validate(payload)
    if errs:
        st.error("Please resolve these before proceeding:")
        for msg in errs:
            st.markdown(f"- {msg}")
        return

    with st.spinner("Orchestrator reviewing your method selection..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_METHOD, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_METHOD, summary)
    S.save(state)

    st.session_state[f"method_draft_payload_{state.run_id}"] = payload
    st.session_state[f"method_review_{state.run_id}"] = True
    st.rerun()


# ---------------------------------------------------------------------------
# Review + Proceed
# ---------------------------------------------------------------------------


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_METHOD)
    if details:
        chat.render_orchestrator_message(details)
    else:
        st.info("No orchestrator message yet — resubmit above.")
        return

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Proceed to Persona",
            type="primary",
            use_container_width=True,
            key=f"method_proceed_{state.run_id}",
        ):
            _proceed(state)
    with c2:
        if st.button(
            "Edit",
            use_container_width=True,
            key=f"method_edit_{state.run_id}",
        ):
            st.session_state[f"method_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State) -> None:
    payload = st.session_state.get(f"method_draft_payload_{state.run_id}")
    if payload is None:
        st.error("No method draft in session — resubmit.")
        return

    was_complete = state.step_status.get(S.STEP_METHOD) == S.StepStatus.COMPLETE

    state.method = S.Method.model_validate(payload)
    S.mark_status(state, S.STEP_METHOD, S.StepStatus.COMPLETE)

    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_METHOD)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")

    S.append_history(
        state,
        actor="pm",
        action="method_confirmed",
        details={
            "axes_selected": [k for k, v in payload["axes"].items() if v],
            "methods_selected": payload["selected_methods"],
            "questions_count": len(payload["research_questions"]),
        },
    )
    S.save(state)

    st.session_state.pop(f"method_review_{state.run_id}", None)
    st.session_state.pop(f"method_draft_payload_{state.run_id}", None)
    st.session_state.current_step = S.STEP_PERSONA
    st.rerun()
