"""Agent 4 — Aggregator / Primary Assessment (v1, state-backed).

Two entry points:

- `assess_market(state, market)` — rolls one market's panel responses into a
  per-market `Assessment` (variant preference shares, winning variant, red
  flags, rationale, recommendation). Deterministic shares are computed in code;
  Claude writes the verdict + rationale.

- `assess_cross_market(state)` — consumes the per-market assessments and
  produces a `CrossMarketAssessment` (consistent winners, divergent findings,
  overall recommendation).

Results are stored at:
- `state.assessment["by_market"][locale]` — per-market
- `state.assessment["cross_market"]` — cross-market
"""

from __future__ import annotations

from collections import Counter
from typing import Callable, Optional

from prism import state as S
from prism.llm import call_structured
from prism.panel import get_responses
from prism.persona import get_persona
from prism.schemas import Assessment, CrossMarketAssessment, PanelResponse


_PER_MARKET_SYSTEM = (
    "Synthesize one market's panel into a verdict. Plain-spoken. If red flags "
    "would block ship, say so. If the signal is marginal, recommend revision over pass. "
    "English only."
)

_CROSS_MARKET_SYSTEM = (
    "Given per-market verdicts, explain where markets converge and diverge. Name "
    "markets by locale. Don't invent findings not in the per-market assessments."
)


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_assessment(state: S.State, locale: str) -> Optional[Assessment]:
    if not state.assessment:
        return None
    data = (state.assessment or {}).get("by_market", {}).get(locale)
    return Assessment.model_validate(data) if data else None


def get_all_assessments(state: S.State) -> dict[str, Assessment]:
    if not state.assessment:
        return {}
    return {
        loc: Assessment.model_validate(v)
        for loc, v in state.assessment.get("by_market", {}).items()
    }


def get_cross_market(state: S.State) -> Optional[CrossMarketAssessment]:
    if not state.assessment:
        return None
    data = (state.assessment or {}).get("cross_market")
    return CrossMarketAssessment.model_validate(data) if data else None


def _set_assessment(state: S.State, locale: str, a: Assessment) -> None:
    if state.assessment is None:
        state.assessment = {"by_market": {}}
    state.assessment.setdefault("by_market", {})[locale] = a.model_dump(mode="json")


def _set_cross_market(state: S.State, cross: CrossMarketAssessment) -> None:
    if state.assessment is None:
        state.assessment = {"by_market": {}}
    state.assessment["cross_market"] = cross.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Deterministic tallies
# ---------------------------------------------------------------------------


def _tally_top_ranks(
    responses: list[PanelResponse],
    variant_ids: list[str],
) -> dict[str, float]:
    """Share of the panel that ranked each variant 1st."""
    total = len(responses) or 1
    counter: Counter = Counter()
    for r in responses:
        for ev in r.variant_evaluations:
            if ev.rank == 1:
                counter[ev.variant_id] += 1
                break
    return {vid: counter.get(vid, 0) / total for vid in variant_ids}


def _tally_mean_scores(
    responses: list[PanelResponse],
    variant_ids: list[str],
) -> dict[str, float]:
    """Mean appropriateness_score (0-100) per variant across the panel."""
    totals: dict[str, list[int]] = {vid: [] for vid in variant_ids}
    for r in responses:
        for ev in r.variant_evaluations:
            if ev.variant_id in totals:
                totals[ev.variant_id].append(ev.appropriateness_score)
    return {
        vid: (round(sum(vs) / len(vs), 1) if vs else 0.0)
        for vid, vs in totals.items()
    }


def _pick_winner(
    top_rank_shares: dict[str, float],
    mean_scores: dict[str, float],
) -> Optional[str]:
    """Winner = variant that maximizes both top-rank share AND mean score.
    If those disagree, return None (no clear winner)."""
    if not top_rank_shares:
        return None
    ranked = sorted(top_rank_shares.items(), key=lambda kv: kv[1], reverse=True)
    scored = sorted(mean_scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] <= 0:
        return None
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    if ranked[0][0] != scored[0][0]:
        return None  # disagreement across the two metrics
    return ranked[0][0]


def _dedup_variant_red_flags(
    responses: list[PanelResponse],
) -> list[str]:
    """Collect per-variant red flags, prefix with '[variant_id]', de-dup."""
    seen: set[str] = set()
    out: list[str] = []
    for r in responses:
        for ev in r.variant_evaluations:
            for f in ev.variant_red_flags:
                tagged = f"[{ev.variant_id}] {f.strip()}"
                key = tagged.lower()
                if key and key not in seen:
                    seen.add(key)
                    out.append(tagged)
    return out


# ---------------------------------------------------------------------------
# Per-market assessment
# ---------------------------------------------------------------------------


def _build_per_market_prompt(
    state: S.State,
    market: S.Market,
    responses: list[PanelResponse],
    top_rank_shares: dict[str, float],
    mean_scores: dict[str, float],
    winning_variant_id: Optional[str],
    red_flags: list[str],
) -> str:
    setup = state.setup
    assert setup is not None
    persona = get_persona(state, market.locale)

    # Each respondent row — ranking + top-variant score
    rows = []
    for r in responses:
        ranks = sorted(r.variant_evaluations, key=lambda e: e.rank)
        rank_line = ", ".join(
            f"{e.rank}={e.variant_id}(score {e.appropriateness_score})"
            for e in ranks
        )
        variant_flags = "; ".join(
            f"[{e.variant_id}] {f}"
            for e in r.variant_evaluations
            for f in e.variant_red_flags
        ) or "(none)"
        rows.append(
            f"- {r.archetype_id} | {rank_line}\n"
            f"  flags: {variant_flags}\n"
            f"  reasoning: {r.overall_reasoning}"
        )
    panel_text = "\n".join(rows)

    rank_lines = "\n".join(
        f"  - `{vid}`: {share:.0%} ranked it 1st"
        for vid, share in sorted(top_rank_shares.items(), key=lambda kv: -kv[1])
    )
    score_lines = "\n".join(
        f"  - `{vid}`: mean score {score:.1f}/100"
        for vid, score in sorted(mean_scores.items(), key=lambda kv: -kv[1])
    )

    flags_block = (
        "  - " + "\n  - ".join(red_flags) if red_flags else "  (none)"
    )

    variant_ids_labels = "\n".join(
        f"  - `{v.id}`: {v.label}" + (" (CONTROL)" if v.is_control else "")
        for v in setup.variants
    )

    control_id = next((v.id for v in setup.variants if v.is_control), None)
    non_control_ids = [v.id for v in setup.variants if not v.is_control]

    return (
        f"Market: {market.country} ({market.locale})\n"
        f"Variants:\n{variant_ids_labels}\n"
        f"Pass criteria: top non-control ≥{setup.pass_criteria.min_top_variant_share:.0%}, "
        f"≤{setup.pass_criteria.max_cultural_red_flags} red flag(s).\n\n"
        f"Top-rank shares:\n{rank_lines}\n"
        f"Mean scores (0-100):\n{score_lines}\n"
        f"Winning variant (null if metrics disagree): `{winning_variant_id}`\n"
        f"Control: `{control_id}` | Non-control: {non_control_ids}\n"
        f"Red flags ({len(red_flags)}):\n{flags_block}\n\n"
        f"Target segment: {persona.target_segment if persona else '(none)'}\n\n"
        f"Panel ({len(responses)} respondents):\n{panel_text}\n\n"
        f"Produce Assessment:\n"
        f"- verdict: pass/fail/needs_revision\n"
        f"- confidence_0_100 (full range; 0-39 weak, 40-59 ambiguous, 60-79 solid, "
        f"80-100 clear). Drivers: metric gap, top-rank vs mean-score agreement, "
        f"red-flag count, respondent consistency.\n"
        f"- variant_top_rank_shares/variant_mean_scores/winning_variant_id/"
        f"cultural_red_flags: verbatim from above.\n"
        f"- rationale: 3-5 sentences. Call out metric disagreement if any.\n"
        f"- recommended_next_step: one concrete action."
    )


def assess_market(state: S.State, market: S.Market) -> Assessment:
    if state.setup is None:
        raise RuntimeError("state.setup is required before assessment.")

    responses = get_responses(state, market.locale)
    if not responses:
        raise RuntimeError(f"No panel responses for {market.locale}. Run the Panel step first.")

    variant_ids = [v.id for v in state.setup.variants]
    top_rank_shares = _tally_top_ranks(responses, variant_ids)
    mean_scores = _tally_mean_scores(responses, variant_ids)
    winner = _pick_winner(top_rank_shares, mean_scores)
    red_flags = _dedup_variant_red_flags(responses)

    prompt = _build_per_market_prompt(
        state, market, responses, top_rank_shares, mean_scores, winner, red_flags
    )

    return call_structured(
        model="claude-haiku-4-5",
        system=_PER_MARKET_SYSTEM,
        user_content=prompt,
        response_model=Assessment,
        max_tokens=4000,
    )


def assess_all_markets(
    state: S.State,
    on_market_start: Optional[Callable[[S.Market], None]] = None,
    on_market_done: Optional[Callable[[S.Market, Assessment], None]] = None,
) -> dict[str, Assessment]:
    if state.setup is None:
        raise RuntimeError("state.setup is required.")

    result: dict[str, Assessment] = {}
    for market in state.setup.target_markets:
        if on_market_start:
            on_market_start(market)

        a = assess_market(state, market)
        _set_assessment(state, market.locale, a)
        S.append_history(
            state,
            actor="aggregator_agent",
            action="assessment_built",
            details={
                "locale": market.locale,
                "verdict": a.verdict,
                "winning_variant_id": a.winning_variant_id,
            },
        )
        S.save(state)

        result[market.locale] = a
        if on_market_done:
            on_market_done(market, a)

    return result


# ---------------------------------------------------------------------------
# Cross-market assessment
# ---------------------------------------------------------------------------


def _build_cross_prompt(
    state: S.State, per_market: dict[str, Assessment]
) -> str:
    rows = []
    for locale, a in per_market.items():
        rank_str = ", ".join(
            f"{vid}={share:.0%}"
            for vid, share in sorted(a.variant_top_rank_shares.items(), key=lambda kv: -kv[1])
        )
        score_str = ", ".join(
            f"{vid}={score:.1f}"
            for vid, score in sorted(a.variant_mean_scores.items(), key=lambda kv: -kv[1])
        )
        flags_str = "; ".join(a.cultural_red_flags) if a.cultural_red_flags else "(none)"
        rows.append(
            f"## {locale}\n"
            f"- Verdict: {a.verdict}  (confidence {a.confidence_0_100}/100)\n"
            f"- Winning variant: {a.winning_variant_id}\n"
            f"- Top-rank shares: {rank_str}\n"
            f"- Mean scores (0-100): {score_str}\n"
            f"- Red flags: {flags_str}\n"
            f"- Rationale: {a.rationale}\n"
            f"- Per-market next step: {a.recommended_next_step}"
        )
    block = "\n\n".join(rows)

    return (
        f"Per-market assessments:\n\n{block}\n\n"
        f"Produce CrossMarketAssessment:\n"
        f"- per_market_verdicts: locale → verdict.\n"
        f"- confidence_0_100 (full range): high when markets converge, lower when "
        f"they diverge or per-market confidence is low.\n"
        f"- consistent_winners: winning variant IDs shared across every market "
        f"(empty if none).\n"
        f"- divergent_findings: short sentences naming market-specific disagreements.\n"
        f"- cross_market_rationale: 2-4 sentences.\n"
        f"- recommended_next_step: one concrete cross-market action."
    )


def assess_cross_market(state: S.State) -> CrossMarketAssessment:
    per_market = get_all_assessments(state)
    if not per_market:
        raise RuntimeError("No per-market assessments — run assess_all_markets first.")

    cross = call_structured(
        model="claude-haiku-4-5",
        system=_CROSS_MARKET_SYSTEM,
        user_content=_build_cross_prompt(state, per_market),
        response_model=CrossMarketAssessment,
        max_tokens=3000,
    )

    _set_cross_market(state, cross)
    S.append_history(
        state,
        actor="aggregator_agent",
        action="cross_market_built",
        details={
            "markets": list(per_market.keys()),
            "consistent_winners": cross.consistent_winners,
        },
    )
    S.save(state)
    return cross
