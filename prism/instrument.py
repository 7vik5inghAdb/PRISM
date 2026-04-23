"""Agent 2 — Instrument Designer (v1, state-backed, per-market).

Given the persona and the PM-chosen methods, generates a concrete research
instrument for one target market: stimulus description, ordered question items
(preference / ranking / likert / open_text), and an echo of the pass criteria.

Results are stored at `state.instrument["by_market"][locale]`.

Opus 4.7 — question wording matters, so we pay for it.
"""

from __future__ import annotations

from typing import Callable, Optional

from prism import state as S
from prism.llm import call_structured
from prism.persona import get_persona
from prism.schemas import Instrument, Persona


_SYSTEM = (
    "Design a short culturalization-test instrument (5-8 items, <5 min). Elicit "
    "preference + reasoning, probe cultural red flags, avoid leading/double-barreled "
    "questions. Match the PM's methods: A/B → include a preference or ranking item; "
    "Survey → likert + open_text; Interviews/Focus Groups → lean on open_text."
)


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_instrument(state: S.State, locale: str) -> Optional[Instrument]:
    if not state.instrument:
        return None
    data = (state.instrument or {}).get("by_market", {}).get(locale)
    return Instrument.model_validate(data) if data else None


def get_all_instruments(state: S.State) -> dict[str, Instrument]:
    if not state.instrument:
        return {}
    return {
        loc: Instrument.model_validate(v)
        for loc, v in state.instrument.get("by_market", {}).items()
    }


def _set_instrument(state: S.State, locale: str, inst: Instrument) -> None:
    if state.instrument is None:
        state.instrument = {"by_market": {}}
    state.instrument.setdefault("by_market", {})[locale] = inst.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _build_user_prompt(
    state: S.State, market: S.Market, persona: Persona
) -> str:
    setup = state.setup
    assert setup is not None
    method = state.method

    n = len(setup.variants)
    methods_list = ", ".join(method.selected_methods) if method else "(none)"
    dimensions = "; ".join(persona.key_cultural_dimensions)

    rq_line = ""
    if method and method.research_questions:
        rq_line = (
            "Research questions: "
            + " | ".join(method.research_questions)
            + "\n"
        )

    return (
        f"Market: {setup.source_market.locale} → {market.locale} ({market.country})\n"
        f"Target segment: {persona.target_segment}\n"
        f"Cultural dimensions: {dimensions}\n"
        f"Hypothesis: {setup.hypothesis}\n"
        f"Methods: {methods_list}\n"
        f"{rq_line}"
        f"Variants to test: n={n}\n\n"
        f"Produce 5-8 items: one ranking or preference item across the {n} variants "
        f"(with 'none'/'tie' escape hatches if preference); 2-3 likert_5 items on "
        f"cultural fit; 2-3 open_text items on red flags and reasoning. Each item "
        f"gets a short rationale. Fill stimulus_description and pass_criteria_echo "
        f"(≥{setup.pass_criteria.min_top_variant_share:.0%} share for top variant; "
        f"≤{setup.pass_criteria.max_cultural_red_flags} red flags). "
        f"methods_covered = method keys actually addressed."
    )


def design_instrument_for_market(
    state: S.State, market: S.Market, persona: Persona
) -> Instrument:
    return call_structured(
        model="claude-haiku-4-5",
        system=_SYSTEM,
        user_content=_build_user_prompt(state, market, persona),
        response_model=Instrument,
        max_tokens=4000,
    )


def design_instruments_for_all_markets(
    state: S.State,
    on_market_start: Optional[Callable[[S.Market], None]] = None,
    on_market_done: Optional[Callable[[S.Market, Instrument], None]] = None,
) -> dict[str, Instrument]:
    if state.setup is None:
        raise RuntimeError("state.setup is required before designing instruments.")

    personas = {m.locale: get_persona(state, m.locale) for m in state.setup.target_markets}
    missing = [loc for loc, p in personas.items() if p is None]
    if missing:
        raise RuntimeError(f"Persona missing for markets: {missing}. Run the Persona step first.")

    result: dict[str, Instrument] = {}
    for market in state.setup.target_markets:
        if on_market_start:
            on_market_start(market)

        persona = personas[market.locale]
        assert persona is not None  # checked above
        inst = design_instrument_for_market(state, market, persona)

        _set_instrument(state, market.locale, inst)
        S.append_history(
            state,
            actor="instrument_agent",
            action="instrument_designed",
            details={
                "locale": market.locale,
                "items_count": len(inst.items),
                "methods_covered": inst.methods_covered,
            },
        )
        S.save(state)

        result[market.locale] = inst
        if on_market_done:
            on_market_done(market, inst)

    return result
