"""Step — Instrument Design.

Runs the Instrument Designer for each target market. Pulls method selection
from state (which methods the PM picked) so each instrument covers the right
item types.
"""

from __future__ import annotations

import streamlit as st

from prism import instrument as instrument_agent
from prism import orchestrator
from prism import state as S
from prism.ui import chat, progress


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None or state.method is None:
        st.warning("Complete **Setup** and **Method** first.")
        return

    from prism.persona import get_all_personas

    personas = get_all_personas(state)
    missing = [m.locale for m in state.setup.target_markets if m.locale not in personas]
    if missing:
        st.warning(
            f"Persona is missing for {', '.join(missing)}. Run the **Persona** step first."
        )
        return

    st.subheader("Per-market status")
    _render_status_table(state)

    existing = instrument_agent.get_all_instruments(state)
    all_done = all(m.locale in existing for m in state.setup.target_markets)

    btn_label = "🧠 Regenerate all instruments" if all_done else "🧠 Design instruments (all markets)"
    if st.button(btn_label, type="primary", use_container_width=True, key=f"inst_run_{state.run_id}"):
        _run_generation(state)

    if existing:
        st.divider()
        st.subheader("Generated instruments")
        for m in state.setup.target_markets:
            inst = existing.get(m.locale)
            if inst is None:
                continue
            with st.expander(f"{m.country} ({m.locale}) — {len(inst.items)} items", expanded=False):
                st.markdown(f"**Methods covered:** {', '.join(inst.methods_covered)}")
                st.markdown(f"**Stimulus:** {inst.stimulus_description}")
                rows = [
                    {"ID": i.item_id, "Type": i.response_type, "Question": i.question}
                    for i in inst.items
                ]
                st.dataframe(rows, hide_index=True, use_container_width=True)
                st.caption(f"Pass criteria: {inst.pass_criteria_echo}")

    # Review + proceed
    review_key = f"inst_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    if all_done and not in_review:
        st.divider()
        if st.button(
            "Review before proceeding",
            use_container_width=True,
            key=f"inst_submit_{state.run_id}",
        ):
            _handle_submit(state)

    if in_review:
        st.divider()
        _render_review(state)

    if not in_review:
        prior = orchestrator.latest_message_for(state, S.STEP_INSTRUMENT)
        if prior is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior)


def _render_status_table(state: S.State) -> None:
    assert state.setup is not None
    existing = instrument_agent.get_all_instruments(state)
    rows = []
    for m in state.setup.target_markets:
        inst = existing.get(m.locale)
        if inst is None:
            status = "⚪️ Not yet built"
            count = 0
        else:
            status = "🟢 Built"
            count = len(inst.items)
        rows.append({"Locale": m.locale, "Country": m.country, "Items": count, "Status": status})
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _run_generation(state: S.State) -> None:
    markets = state.setup.target_markets if state.setup else []
    total = len(markets)
    progress_bar = st.progress(0.0, text="Starting...")
    done = {"count": 0}

    def on_start(m: S.Market) -> None:
        progress_bar.progress(
            done["count"] / total if total else 0,
            text=f"Designing instrument for {m.country}...",
        )

    def on_done(m: S.Market, _inst) -> None:
        done["count"] += 1
        progress_bar.progress(done["count"] / total if total else 1, text=f"Done {done['count']}/{total}")

    try:
        instrument_agent.design_instruments_for_all_markets(
            state, on_market_start=on_start, on_market_done=on_done
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"Instrument design failed: {e}")
        return

    progress_bar.empty()
    st.success(f"Designed {done['count']} instrument(s).")
    st.rerun()


def _handle_submit(state: S.State) -> None:
    insts = instrument_agent.get_all_instruments(state)
    payload = {
        "by_market": {
            loc: {
                "items_count": len(i.items),
                "methods_covered": i.methods_covered,
                "item_types": list({it.response_type for it in i.items}),
            }
            for loc, i in insts.items()
        }
    }

    with st.spinner("Orchestrator reviewing instruments..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_INSTRUMENT, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_INSTRUMENT, summary)
    S.save(state)
    st.session_state[f"inst_review_{state.run_id}"] = True
    st.rerun()


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_INSTRUMENT)
    if details:
        chat.render_orchestrator_message(details)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Proceed to Panel",
            type="primary",
            use_container_width=True,
            key=f"inst_proceed_{state.run_id}",
        ):
            _proceed(state)
    with c2:
        if st.button(
            "Back",
            use_container_width=True,
            key=f"inst_edit_{state.run_id}",
        ):
            st.session_state[f"inst_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State) -> None:
    was_complete = state.step_status.get(S.STEP_INSTRUMENT) == S.StepStatus.COMPLETE
    S.mark_status(state, S.STEP_INSTRUMENT, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_INSTRUMENT)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action="instrument_confirmed")
    S.save(state)

    st.session_state.pop(f"inst_review_{state.run_id}", None)
    st.session_state.current_step = S.STEP_PANEL
    st.rerun()
