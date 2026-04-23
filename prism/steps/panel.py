"""Step — Synthetic Panel.

Runs the synthetic panel for every target market. Uses the ThreadPoolExecutor
parallelism from prism.panel and renders a live counter of respondents
completed per market.
"""

from __future__ import annotations

import streamlit as st

from prism import orchestrator
from prism import panel as panel_agent
from prism import state as S
from prism.ui import chat, progress


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None or state.method is None:
        st.warning("Complete **Setup** and **Method** first.")
        return

    from prism.instrument import get_all_instruments
    from prism.persona import get_all_personas

    personas = get_all_personas(state)
    instruments = get_all_instruments(state)
    missing_p = [m.locale for m in state.setup.target_markets if m.locale not in personas]
    missing_i = [m.locale for m in state.setup.target_markets if m.locale not in instruments]
    if missing_p or missing_i:
        msg = []
        if missing_p:
            msg.append(f"persona missing for {', '.join(missing_p)}")
        if missing_i:
            msg.append(f"instrument missing for {', '.join(missing_i)}")
        st.warning("Run prior steps first: " + "; ".join(msg))
        return

    st.subheader("Per-market status")
    _render_status_table(state)

    responses = panel_agent.get_all_responses(state)
    all_done = all(m.locale in responses and responses[m.locale] for m in state.setup.target_markets)

    c1, c2 = st.columns(2)
    with c1:
        label = "🧠 Re-run all panels" if all_done else "🧠 Run panels (all markets)"
        if st.button(label, type="primary", use_container_width=True, key=f"panel_run_{state.run_id}"):
            _run_panels(state)
    with c2:
        workers = st.number_input(
            "Parallel workers per market",
            min_value=1,
            max_value=16,
            value=6,
            step=1,
            key=f"panel_workers_{state.run_id}",
        )

    if responses:
        st.divider()
        st.subheader("Panel responses")
        for m in state.setup.target_markets:
            rs = responses.get(m.locale, [])
            if not rs:
                continue
            with st.expander(
                f"{m.country} ({m.locale}) — {len(rs)} respondents", expanded=False
            ):
                _render_panel_summary(rs)

    review_key = f"panel_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    if all_done and not in_review:
        st.divider()
        if st.button(
            "Review before proceeding",
            use_container_width=True,
            key=f"panel_submit_{state.run_id}",
        ):
            _handle_submit(state)

    if in_review:
        st.divider()
        _render_review(state)

    if not in_review:
        prior = orchestrator.latest_message_for(state, S.STEP_PANEL)
        if prior is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior)


def _render_status_table(state: S.State) -> None:
    assert state.setup is not None
    rs = panel_agent.get_all_responses(state)
    rows = []
    for m in state.setup.target_markets:
        count = len(rs.get(m.locale, []))
        target = state.setup.panel_size_per_market
        status = "🟢 Complete" if count >= target else ("🟡 Partial" if count else "⚪️ Not yet run")
        rows.append(
            {"Locale": m.locale, "Country": m.country, "Responses": f"{count}/{target}", "Status": status}
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _run_panels(state: S.State) -> None:
    if state.setup is None:
        return
    workers = int(st.session_state.get(f"panel_workers_{state.run_id}", 6) or 6)
    total_respondents = state.setup.panel_size_per_market * len(state.setup.target_markets)
    progress_bar = st.progress(0.0, text="Starting...")
    counter = {"respondents": 0, "current_market": ""}

    def on_market_start(m: S.Market) -> None:
        counter["current_market"] = m.locale
        progress_bar.progress(
            counter["respondents"] / total_respondents if total_respondents else 0,
            text=f"Running panel for {m.country} ({m.locale})...",
        )

    def on_respondent(m: S.Market, _aid: str) -> None:
        counter["respondents"] += 1
        progress_bar.progress(
            counter["respondents"] / total_respondents if total_respondents else 1,
            text=f"{counter['respondents']}/{total_respondents} respondents done "
                 f"(current: {counter['current_market']})",
        )

    try:
        panel_agent.run_panels_for_all_markets(
            state,
            max_workers=workers,
            on_market_start=on_market_start,
            on_respondent_done=on_respondent,
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"Panel run failed: {e}")
        return

    progress_bar.empty()
    st.success(f"Completed {counter['respondents']} respondent(s) across all markets.")
    st.rerun()


def _render_panel_summary(responses) -> None:
    from collections import Counter

    if not responses:
        st.caption("No responses.")
        return

    # Top-rank counts
    top_cnt: Counter = Counter()
    # Per-variant score lists
    score_lists: dict[str, list[int]] = {}
    flag_total = 0
    for r in responses:
        for ev in r.variant_evaluations:
            score_lists.setdefault(ev.variant_id, []).append(ev.appropriateness_score)
            flag_total += len(ev.variant_red_flags)
            if ev.rank == 1:
                top_cnt[ev.variant_id] += 1

    total = len(responses)
    rows = []
    for vid in sorted(score_lists.keys()):
        scores = score_lists[vid]
        mean_score = sum(scores) / len(scores) if scores else 0
        first_count = top_cnt.get(vid, 0)
        rows.append(
            {
                "Variant": vid,
                "Ranked 1st": f"{first_count}/{total}",
                "Top-rank share": f"{first_count/total:.0%}" if total else "-",
                "Mean score": f"{mean_score:.1f}",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(f"Total per-variant red flags raised across panel: {flag_total}")


def _handle_submit(state: S.State) -> None:
    responses = panel_agent.get_all_responses(state)
    payload = {
        "by_market": {
            loc: {
                "respondents": len(rs),
                **_distribution(rs),
                "total_red_flags": sum(
                    len(ev.variant_red_flags)
                    for r in rs
                    for ev in r.variant_evaluations
                ),
            }
            for loc, rs in responses.items()
        }
    }

    with st.spinner("Orchestrator reviewing panel..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_PANEL, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_PANEL, summary)
    S.save(state)
    st.session_state[f"panel_review_{state.run_id}"] = True
    st.rerun()


def _distribution(responses) -> dict[str, dict]:
    """Summarize a market's responses for the orchestrator confirmation."""
    from collections import Counter

    total = len(responses) or 1
    top_cnt: Counter = Counter()
    score_lists: dict[str, list[int]] = {}
    for r in responses:
        for ev in r.variant_evaluations:
            score_lists.setdefault(ev.variant_id, []).append(ev.appropriateness_score)
            if ev.rank == 1:
                top_cnt[ev.variant_id] += 1

    return {
        "top_rank_shares": {vid: round(top_cnt.get(vid, 0) / total, 3) for vid in score_lists},
        "mean_scores": {
            vid: round(sum(vs) / len(vs), 1) if vs else 0.0
            for vid, vs in score_lists.items()
        },
    }


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_PANEL)
    if details:
        chat.render_orchestrator_message(details)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Proceed to Assessment",
            type="primary",
            use_container_width=True,
            key=f"panel_proceed_{state.run_id}",
        ):
            _proceed(state)
    with c2:
        if st.button(
            "Back",
            use_container_width=True,
            key=f"panel_edit_{state.run_id}",
        ):
            st.session_state[f"panel_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State) -> None:
    was_complete = state.step_status.get(S.STEP_PANEL) == S.StepStatus.COMPLETE
    S.mark_status(state, S.STEP_PANEL, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_PANEL)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action="panel_confirmed")
    S.save(state)

    st.session_state.pop(f"panel_review_{state.run_id}", None)
    st.session_state.current_step = S.STEP_ASSESSMENT
    st.rerun()
