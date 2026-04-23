"""Agent 1 — Persona Architect (v1, state-backed, per-market).

For each target market in `state.setup.target_markets`, produces a Persona
(market summary + cultural dimensions + design expectations + archetype
roster sized to `state.setup.panel_size_per_market`). Results are stored at
`state.persona["by_market"][locale]`.

Opus 4.7 with adaptive thinking — this sets the foundation for instrument +
panel downstream, so we pay for quality here.
"""

from __future__ import annotations

from typing import Callable, Optional

from prism import state as S
from prism.llm import call_structured
from prism.schemas import Persona


_SYSTEM = (
    "Build a target persona + respondent roster for one market. Ground every claim "
    "in that market's cultural, linguistic, and design conventions — not generic tropes."
)


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_persona(state: S.State, locale: str) -> Optional[Persona]:
    if not state.persona:
        return None
    data = (state.persona or {}).get("by_market", {}).get(locale)
    return Persona.model_validate(data) if data else None


def get_all_personas(state: S.State) -> dict[str, Persona]:
    if not state.persona:
        return {}
    return {
        loc: Persona.model_validate(v)
        for loc, v in state.persona.get("by_market", {}).items()
    }


def _set_persona(state: S.State, locale: str, persona: Persona) -> None:
    if state.persona is None:
        state.persona = {"by_market": {}}
    state.persona.setdefault("by_market", {})[locale] = persona.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _build_user_prompt(state: S.State, market: S.Market) -> str:
    assert state.setup is not None
    setup = state.setup
    pc = setup.product_context
    n = setup.panel_size_per_market

    return (
        f"Market: {market.country} ({market.locale})\n"
        f"Source: {setup.source_market.country} ({setup.source_market.locale})\n"
        f"Asset: {pc.application} · {pc.asset_type} · feature: {pc.feature}\n"
        f"Use case: {pc.use_case}\n"
        f"Hypothesis: {setup.hypothesis}\n\n"
        f"Produce: market_summary (2-4 sentences), target_segment (one sentence), "
        f"4-6 key_cultural_dimensions (script, formality, motifs, color, etc.), "
        f"4-6 design_expectations, and exactly {n} archetypes with ids R01..R{n:02d}. "
        f"Diversify archetypes across age_band, gender, region, occupation, tech_comfort. "
        f"Give each a 2-3 sentence cultural_notes field grounded in those axes."
    )


def build_persona_for_market(state: S.State, market: S.Market) -> Persona:
    return call_structured(
        model="claude-haiku-4-5",
        system=_SYSTEM,
        user_content=_build_user_prompt(state, market),
        response_model=Persona,
        max_tokens=8000,
    )


def build_personas_for_all_markets(
    state: S.State,
    on_market_start: Optional[Callable[[S.Market], None]] = None,
    on_market_done: Optional[Callable[[S.Market, Persona], None]] = None,
) -> dict[str, Persona]:
    """Build persona for every target market, sequentially.

    After each market completes, writes state to disk (so the UI can recover
    from a mid-run crash). `on_market_start` / `on_market_done` let the caller
    surface progress in the UI.
    """
    if state.setup is None:
        raise RuntimeError("state.setup is required before building personas.")

    result: dict[str, Persona] = {}
    for market in state.setup.target_markets:
        if on_market_start:
            on_market_start(market)

        persona = build_persona_for_market(state, market)
        _set_persona(state, market.locale, persona)
        S.append_history(
            state,
            actor="persona_agent",
            action="persona_built",
            details={
                "locale": market.locale,
                "country": market.country,
                "archetypes_count": len(persona.archetypes),
            },
        )
        S.save(state)

        result[market.locale] = persona
        if on_market_done:
            on_market_done(market, persona)

    return result
