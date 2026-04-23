"""Agent 3 — Synthetic Panel (v1, state-backed, per-market).

Each respondent archetype is instantiated as a separate Sonnet 4.6 call. Each
call receives the instrument + every variant image as content blocks and
returns one PanelResponse. We parallelize across archetypes with a
ThreadPoolExecutor and cache the shared persona/instrument/research-context
system blocks so repeated calls hit the prompt cache.

For n variants, the prompt enumerates all variants and instructs the model to
pick `preferred_variant_id` from the actual IDs (or 'none' / 'tie').

Results are stored at `state.panel_responses["by_market"][locale]` as a list.
"""

from __future__ import annotations

import base64
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from prism import state as S
from prism.instrument import get_instrument
from prism.llm import call_structured
from prism.persona import get_persona
from prism.schemas import Instrument, PanelResponse, Persona, RespondentArchetype


RESPONDENT_SYSTEM = (
    "Role-play a panel respondent for a culturalization A/B test. Stay in character.\n"
    "Rules:\n"
    "- Rank every variant 1..N with unique ranks (commit to an order).\n"
    "- appropriateness_score is 0-100 (100=ship today, 50=issues, 0=unusable). "
    "Use the full range; don't cluster.\n"
    "- variant_red_flags: concrete, per-variant only. Empty if none. Skip issues "
    "that apply to every variant.\n"
    "- All free text in ENGLISH regardless of locale. Quote non-English phrasing."
)


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_responses(state: S.State, locale: str) -> list[PanelResponse]:
    if not state.panel_responses:
        return []
    raw = (state.panel_responses or {}).get("by_market", {}).get(locale, [])
    return [PanelResponse.model_validate(r) for r in raw]


def get_all_responses(state: S.State) -> dict[str, list[PanelResponse]]:
    if not state.panel_responses:
        return {}
    return {
        loc: [PanelResponse.model_validate(r) for r in raw]
        for loc, raw in state.panel_responses.get("by_market", {}).items()
    }


def _set_responses(state: S.State, locale: str, responses: list[PanelResponse]) -> None:
    if state.panel_responses is None:
        state.panel_responses = {"by_market": {}}
    state.panel_responses.setdefault("by_market", {})[locale] = [
        r.model_dump(mode="json") for r in responses
    ]


# ---------------------------------------------------------------------------
# Internals: image blocks, cached context, per-respondent call
# ---------------------------------------------------------------------------


def _image_block(path: Path, label: str) -> list[dict]:
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        mime = "image/png"
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return [
        {"type": "text", "text": f"Variant {label}:"},
        {
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": data},
        },
    ]


def _shared_context_blocks(
    state: S.State,
    market: S.Market,
    persona: Persona,
    instrument: Instrument,
) -> list[dict]:
    """System blocks shared across every respondent call for this market.
    Terminated with a cache_control marker so Claude caches the prefix."""
    setup = state.setup
    assert setup is not None

    persona_summary = (
        f"Segment: {persona.target_segment}\n"
        f"Cultural dimensions: {'; '.join(persona.key_cultural_dimensions)}\n"
        f"Design expectations: {'; '.join(persona.design_expectations)}"
    )
    items_text = "\n".join(
        f"  {i.item_id} [{i.response_type}]: {i.question}" for i in instrument.items
    )
    variant_ids = ", ".join(f"'{v.id}'" for v in setup.variants)
    n = len(setup.variants)
    instrument_text = (
        f"Stimulus: {instrument.stimulus_description}\n"
        f"Items:\n{items_text}\n"
        f"Variant ids: {variant_ids} (produce exactly {n} evaluations, ranks 1..{n})."
    )
    research_text = (
        f"{setup.product_context.application} {setup.product_context.asset_type} "
        f"for {market.country} ({market.locale}). "
        f"Hypothesis: {setup.hypothesis}"
    )
    return [
        {"type": "text", "text": research_text},
        {"type": "text", "text": persona_summary},
        {
            "type": "text",
            "text": instrument_text,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _archetype_user_content(
    archetype: RespondentArchetype,
    state: S.State,
) -> list[dict]:
    setup = state.setup
    assert setup is not None
    n_variants = len(setup.variants)

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Archetype {archetype.archetype_id} ({archetype.name}): "
                f"{archetype.age_band} {archetype.gender}, {archetype.region}, "
                f"{archetype.occupation}, tech_comfort={archetype.tech_comfort}. "
                f"Notes: {archetype.cultural_notes}\n"
                f"{n_variants} variants follow; review before answering."
            ),
        }
    ]
    for v in setup.variants:
        content.extend(_image_block(S.resolve_asset_path(v.path), v.id))
    content.append(
        {
            "type": "text",
            "text": (
                f"Respond as this archetype. Set archetype_id. Produce {n_variants} "
                f"variant_evaluations (ranks 1..{n_variants}, unique; scores 0-100). "
                f"Answer all instrument items under `items`. Write 2-4 sentence "
                f"overall_reasoning. English only."
            ),
        }
    )
    return content


def _run_one(
    archetype: RespondentArchetype,
    state: S.State,
    shared_blocks: list[dict],
) -> PanelResponse:
    return call_structured(
        model="claude-haiku-4-5",
        system=RESPONDENT_SYSTEM,
        user_content=_archetype_user_content(archetype, state),
        response_model=PanelResponse,
        max_tokens=3000,
        extra_system_blocks=shared_blocks,
    )


# ---------------------------------------------------------------------------
# Per-market + all-markets entry points
# ---------------------------------------------------------------------------


def run_panel_for_market(
    state: S.State,
    market: S.Market,
    *,
    max_workers: int = 6,
    on_respondent_done: Optional[Callable[[str], None]] = None,
) -> list[PanelResponse]:
    persona = get_persona(state, market.locale)
    instrument = get_instrument(state, market.locale)
    if persona is None or instrument is None:
        raise RuntimeError(
            f"Persona and/or instrument missing for {market.locale}. "
            f"Run Persona and Instrument steps first."
        )

    shared = _shared_context_blocks(state, market, persona, instrument)
    responses: list[PanelResponse] = []
    errors: list[tuple[str, Exception]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_one, a, state, shared): a.archetype_id
            for a in persona.archetypes
        }
        for fut in as_completed(futures):
            aid = futures[fut]
            try:
                responses.append(fut.result())
                if on_respondent_done:
                    on_respondent_done(aid)
            except Exception as e:  # noqa: BLE001
                errors.append((aid, e))

    if errors:
        msgs = "\n".join(f"  {aid}: {e}" for aid, e in errors)
        raise RuntimeError(f"Panel for {market.locale} had {len(errors)} failed respondent(s):\n{msgs}")

    responses.sort(key=lambda r: r.archetype_id)
    return responses


def run_panels_for_all_markets(
    state: S.State,
    *,
    max_workers: int = 6,
    on_market_start: Optional[Callable[[S.Market], None]] = None,
    on_respondent_done: Optional[Callable[[S.Market, str], None]] = None,
    on_market_done: Optional[Callable[[S.Market, list[PanelResponse]], None]] = None,
) -> dict[str, list[PanelResponse]]:
    if state.setup is None:
        raise RuntimeError("state.setup is required before running panels.")

    result: dict[str, list[PanelResponse]] = {}
    for market in state.setup.target_markets:
        if on_market_start:
            on_market_start(market)

        responses = run_panel_for_market(
            state,
            market,
            max_workers=max_workers,
            on_respondent_done=(
                (lambda aid: on_respondent_done(market, aid))
                if on_respondent_done
                else None
            ),
        )

        _set_responses(state, market.locale, responses)
        S.append_history(
            state,
            actor="panel_agent",
            action="panel_run",
            details={
                "locale": market.locale,
                "respondents": len(responses),
            },
        )
        S.save(state)

        result[market.locale] = responses
        if on_market_done:
            on_market_done(market, responses)

    return result
