"""Step — Persona Construction.

Runs the Persona Architect for each target market sequentially. Renders per-
market cards with archetype previews. PM confirms with the orchestrator and
proceeds to Instrument.
"""

from __future__ import annotations

import streamlit as st

from prism import orchestrator
from prism import persona as persona_agent
from prism import state as S
from prism.ui import chat, progress


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None or state.method is None:
        st.warning("Complete **Setup** and **Method** first.")
        return

    # Status table
    st.subheader("Per-market status")
    _render_status_table(state)

    existing = persona_agent.get_all_personas(state)
    all_done = all(m.locale in existing for m in state.setup.target_markets)

    # Generation controls
    c1, c2 = st.columns([1, 1])
    with c1:
        btn_label = "🧠 Regenerate all personas" if all_done else "🧠 Generate personas (all markets)"
        if st.button(btn_label, type="primary", use_container_width=True, key=f"persona_run_{state.run_id}"):
            _run_generation(state)

    # Previews
    if existing:
        st.divider()
        st.subheader("Generated personas")
        for m in state.setup.target_markets:
            p = existing.get(m.locale)
            if p is None:
                continue
            with st.expander(f"{m.country} ({m.locale}) — {len(p.archetypes)} archetypes", expanded=False):
                st.markdown(f"**Target segment:** {p.target_segment}")
                st.markdown(f"**Market summary:** {p.market_summary}")
                st.markdown("**Cultural dimensions:** " + ", ".join(p.key_cultural_dimensions))
                st.markdown("**Design expectations:** " + ", ".join(p.design_expectations))

                rows = [
                    {
                        "ID": a.archetype_id,
                        "Name": a.name,
                        "Age": a.age_band,
                        "Gender": a.gender,
                        "Region": a.region,
                        "Occupation": a.occupation,
                        "Tech": a.tech_comfort,
                    }
                    for a in p.archetypes
                ]
                st.dataframe(rows, hide_index=True, use_container_width=True)

    # Review + proceed
    review_key = f"persona_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    if all_done and not in_review:
        st.divider()
        if st.button(
            "Review before proceeding",
            use_container_width=True,
            key=f"persona_submit_{state.run_id}",
        ):
            _handle_submit(state)

    if in_review:
        st.divider()
        _render_review(state)

    if not in_review:
        prior = orchestrator.latest_message_for(state, S.STEP_PERSONA)
        if prior is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior)


# ---------------------------------------------------------------------------


def _render_status_table(state: S.State) -> None:
    assert state.setup is not None
    existing = persona_agent.get_all_personas(state)
    rows = []
    for m in state.setup.target_markets:
        p = existing.get(m.locale)
        if p is None:
            status = "⚪️ Not yet built"
            count = 0
        else:
            status = "🟢 Built"
            count = len(p.archetypes)
        rows.append({"Locale": m.locale, "Country": m.country, "Archetypes": count, "Status": status})
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _run_generation(state: S.State) -> None:
    markets = state.setup.target_markets if state.setup else []
    total = len(markets)
    progress_bar = st.progress(0.0, text="Starting...")
    done = {"count": 0}

    def on_start(m: S.Market) -> None:
        progress_bar.progress(
            done["count"] / total if total else 0,
            text=f"Building persona for {m.country} ({m.locale})...",
        )

    def on_done(m: S.Market, _p) -> None:
        done["count"] += 1
        progress_bar.progress(
            done["count"] / total if total else 1,
            text=f"Done {done['count']}/{total}",
        )

    try:
        persona_agent.build_personas_for_all_markets(
            state, on_market_start=on_start, on_market_done=on_done
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"Persona generation failed: {e}")
        return

    progress_bar.empty()
    st.success(f"Generated {done['count']} persona(s).")
    st.rerun()


def _handle_submit(state: S.State) -> None:
    personas = persona_agent.get_all_personas(state)
    payload = {
        "by_market": {
            loc: {
                "target_segment": p.target_segment,
                "archetype_count": len(p.archetypes),
                "cultural_dimensions": p.key_cultural_dimensions,
            }
            for loc, p in personas.items()
        }
    }

    with st.spinner("Orchestrator reviewing personas..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_PERSONA, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_PERSONA, summary)
    S.save(state)

    st.session_state[f"persona_review_{state.run_id}"] = True
    st.rerun()


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_PERSONA)
    if details:
        chat.render_orchestrator_message(details)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Proceed to Instrument",
            type="primary",
            use_container_width=True,
            key=f"persona_proceed_{state.run_id}",
        ):
            _proceed(state)
    with c2:
        if st.button(
            "Back to personas",
            use_container_width=True,
            key=f"persona_edit_{state.run_id}",
        ):
            st.session_state[f"persona_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State) -> None:
    was_complete = state.step_status.get(S.STEP_PERSONA) == S.StepStatus.COMPLETE
    S.mark_status(state, S.STEP_PERSONA, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_PERSONA)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action="persona_confirmed")
    S.save(state)

    st.session_state.pop(f"persona_review_{state.run_id}", None)
    st.session_state.current_step = S.STEP_INSTRUMENT
    st.rerun()
