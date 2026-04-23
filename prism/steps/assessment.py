"""Step — Primary Assessment.

Two sub-agents, one view:

1. Per-market `Assessment` for each target market.
2. `CrossMarketAssessment` that compares them.

After this step, the orchestrator asks the PM whether to proceed to Secondary,
skip to Report, or revisit a step.
"""

from __future__ import annotations

import streamlit as st

from prism import aggregator as aggregator_agent
from prism import orchestrator
from prism import state as S
from prism.ui import chat, progress
from prism.ui.labels import confidence_badge, confidence_label


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    if state.setup is None:
        st.warning("Complete earlier steps first.")
        return

    from prism.panel import get_all_responses

    responses = get_all_responses(state)
    missing = [
        m.locale for m in state.setup.target_markets if not responses.get(m.locale)
    ]
    if missing:
        st.warning(f"Panel responses missing for {', '.join(missing)}. Run the **Panel** step.")
        return

    st.subheader("Per-market status")
    _render_status_table(state)

    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)
    all_market_done = all(m.locale in per_market for m in state.setup.target_markets)

    c1, c2 = st.columns(2)
    with c1:
        label = "🧠 Re-run per-market assessments" if all_market_done else "🧠 Assess each market"
        if st.button(label, type="primary", use_container_width=True, key=f"assess_run_{state.run_id}"):
            _run_per_market(state)
    with c2:
        can_cross = all_market_done
        label2 = "🧠 Re-run cross-market" if cross else "🔀 Cross-market synthesis"
        if st.button(
            label2,
            use_container_width=True,
            disabled=not can_cross,
            key=f"assess_cross_{state.run_id}",
        ):
            _run_cross(state)

    # Per-market results
    if per_market:
        st.divider()
        st.subheader("Per-market assessments")
        for m in state.setup.target_markets:
            a = per_market.get(m.locale)
            if a is None:
                continue
            verdict_badge = {"pass": "🟢", "fail": "🔴", "needs_revision": "🟡"}[a.verdict]
            with st.expander(
                f"{verdict_badge} {m.country} ({m.locale}) — "
                f"{a.verdict.upper()} · confidence {confidence_badge(a.confidence_0_100)}",
                expanded=False,
            ):
                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    st.markdown(f"**Winning variant:** `{a.winning_variant_id}`")
                with c_m2:
                    st.metric(
                        "Confidence",
                        f"{a.confidence_0_100}/100",
                        help=f"{confidence_label(a.confidence_0_100)} signal",
                    )
                rows = []
                for vid in sorted(a.variant_top_rank_shares.keys()):
                    rows.append(
                        {
                            "Variant": vid,
                            "Top-rank share": f"{a.variant_top_rank_shares.get(vid, 0):.0%}",
                            "Mean score": f"{a.variant_mean_scores.get(vid, 0):.1f}",
                        }
                    )
                st.dataframe(rows, hide_index=True, use_container_width=True)
                st.markdown(f"**Rationale:** {a.rationale}")
                st.markdown(f"**Recommended next step:** {a.recommended_next_step}")
                if a.cultural_red_flags:
                    st.markdown("**Per-variant red flags:**")
                    for f in a.cultural_red_flags:
                        st.markdown(f"- {f}")

    # Cross-market
    if cross:
        st.divider()
        st.subheader(
            f"Cross-market synthesis · confidence {confidence_badge(cross.confidence_0_100)}"
        )
        c_c1, c_c2 = st.columns([2, 1])
        with c_c1:
            st.markdown(
                f"**Consistent winners:** {', '.join(cross.consistent_winners) or '(none)'}"
            )
        with c_c2:
            st.metric(
                "Confidence",
                f"{cross.confidence_0_100}/100",
                help=f"{confidence_label(cross.confidence_0_100)} signal",
            )
        st.markdown(f"**Cross-market rationale:** {cross.cross_market_rationale}")
        st.markdown(f"**Recommended next step:** {cross.recommended_next_step}")
        if cross.divergent_findings:
            st.markdown("**Divergent findings:**")
            for f in cross.divergent_findings:
                st.markdown(f"- {f}")

    # Review + proceed
    review_key = f"assess_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    ready = all_market_done and (cross is not None or len(state.setup.target_markets) == 1)
    if ready and not in_review:
        st.divider()
        if st.button(
            "Review before proceeding",
            use_container_width=True,
            key=f"assess_submit_{state.run_id}",
        ):
            _handle_submit(state)

    if in_review:
        st.divider()
        _render_review(state)

    if not in_review:
        prior = orchestrator.latest_message_for(state, S.STEP_ASSESSMENT)
        if prior is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior)


def _render_status_table(state: S.State) -> None:
    assert state.setup is not None
    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)
    rows = []
    for m in state.setup.target_markets:
        a = per_market.get(m.locale)
        if a is None:
            status = "⚪️ Not yet run"
            conf = "-"
        else:
            badge = {"pass": "🟢", "fail": "🔴", "needs_revision": "🟡"}[a.verdict]
            status = f"{badge} {a.verdict}"
            conf = f"{a.confidence_0_100}/100"
        rows.append(
            {"Locale": m.locale, "Country": m.country, "Verdict": status, "Confidence": conf}
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)
    if len(state.setup.target_markets) > 1:
        st.caption(
            f"Cross-market: {'🟢 synthesized' if cross else '⚪️ not yet run'}"
        )


def _run_per_market(state: S.State) -> None:
    assert state.setup is not None
    total = len(state.setup.target_markets)
    bar = st.progress(0.0, text="Starting...")
    done = {"count": 0}

    def on_start(m: S.Market) -> None:
        bar.progress(
            done["count"] / total if total else 0,
            text=f"Assessing {m.country}...",
        )

    def on_done(m: S.Market, _a) -> None:
        done["count"] += 1
        bar.progress(done["count"] / total if total else 1, text=f"Done {done['count']}/{total}")

    try:
        aggregator_agent.assess_all_markets(state, on_market_start=on_start, on_market_done=on_done)
    except Exception as e:  # noqa: BLE001
        st.error(f"Assessment failed: {e}")
        return

    bar.empty()
    st.success(f"Assessed {done['count']} market(s).")
    st.rerun()


def _run_cross(state: S.State) -> None:
    try:
        with st.spinner("Synthesizing cross-market assessment..."):
            aggregator_agent.assess_cross_market(state)
    except Exception as e:  # noqa: BLE001
        st.error(f"Cross-market synthesis failed: {e}")
        return

    st.success("Cross-market synthesis complete.")
    st.rerun()


def _handle_submit(state: S.State) -> None:
    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)

    payload = {
        "by_market": {
            loc: {
                "verdict": a.verdict,
                "confidence_0_100": a.confidence_0_100,
                "winning_variant_id": a.winning_variant_id,
                "top_rank_shares": a.variant_top_rank_shares,
                "mean_scores": a.variant_mean_scores,
            }
            for loc, a in per_market.items()
        },
        "cross_market": (
            {
                "confidence_0_100": cross.confidence_0_100,
                "consistent_winners": cross.consistent_winners,
                "divergent_findings_count": len(cross.divergent_findings),
            }
            if cross
            else None
        ),
    }

    with st.spinner("Orchestrator reviewing assessment..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_ASSESSMENT, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_ASSESSMENT, summary)
    S.save(state)
    st.session_state[f"assess_review_{state.run_id}"] = True
    st.rerun()


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_ASSESSMENT)
    if details:
        chat.render_orchestrator_message(details)

    st.markdown("**What's next?**")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(
            "Proceed to Secondary →",
            type="primary",
            use_container_width=True,
            key=f"assess_to_sec_{state.run_id}",
            help="Run cultural risk, competitive analysis, and market context sub-agents (those enabled).",
        ):
            _proceed(state, goto=S.STEP_CULTURAL_RISK)
    with c2:
        if st.button(
            "Skip to Report",
            use_container_width=True,
            key=f"assess_to_report_{state.run_id}",
            help="Compile the report with only primary assessment + any already-complete modules.",
        ):
            _proceed(state, goto=S.STEP_REPORT)
    with c3:
        if st.button(
            "Revisit a step",
            use_container_width=True,
            key=f"assess_edit_{state.run_id}",
        ):
            st.session_state[f"assess_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State, goto: str) -> None:
    was_complete = state.step_status.get(S.STEP_ASSESSMENT) == S.StepStatus.COMPLETE
    S.mark_status(state, S.STEP_ASSESSMENT, S.StepStatus.COMPLETE)
    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_ASSESSMENT)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")
    S.append_history(state, actor="pm", action="assessment_confirmed", details={"goto": goto})
    S.save(state)

    st.session_state.pop(f"assess_review_{state.run_id}", None)
    st.session_state.current_step = goto
    st.rerun()
