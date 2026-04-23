"""Module opt-out UI — shared checklist widget.

The four optional modules are:
- `cultural_risk` — secondary sub-agent surveying market sensitivities/taboos
- `competitive_analysis` — secondary sub-agent profiling competitor positioning
- `market_context` — secondary sub-agent covering market size, growth, behavior
- `charting` — matplotlib chart agent (embedded in the final report)

Setup / Method / Persona / Instrument / Panel / Assessment / Report are always on.
"""

from __future__ import annotations

import streamlit as st

from prism import state as S


MODULE_DESCRIPTIONS: list[tuple[str, str, str]] = [
    (
        "cultural_risk",
        "Cultural risk",
        "Surfaces market-specific sensitivities, taboos, and misalignment risks.",
    ),
    (
        "competitive_analysis",
        "Competitive analysis",
        "Profiles competitors in the target market(s) using agentic web search.",
    ),
    (
        "market_context",
        "Market context",
        "Market size, growth signals, and audience behavior from web sources.",
    ),
    (
        "charting",
        "Charting",
        "Static matplotlib charts embedded in the final report.",
    ),
]


def checklist_inputs(defaults: S.ModulesEnabled, key_prefix: str) -> dict[str, bool]:
    """Render a module checklist. Returns the current checkbox values.

    The caller decides when to persist (e.g. on form submit, or immediately).
    """
    st.markdown("**Optional modules**")
    st.caption(
        "Required steps (Setup, Method, Persona, Instrument, Panel, "
        "Assessment, Report) are always enabled. These optional modules "
        "are skipped entirely and absent from the final report when off."
    )
    result: dict[str, bool] = {}
    for key, label, desc in MODULE_DESCRIPTIONS:
        current = getattr(defaults, key)
        result[key] = st.checkbox(
            label,
            value=current,
            key=f"{key_prefix}_{key}",
            help=desc,
        )
    return result


def apply_toggles(state: S.State, new_values: dict[str, bool]) -> list[str]:
    """Apply new module values to state. Returns the list of step keys whose
    status changed. Caller is responsible for `S.save(state)` + `st.rerun()`.
    """
    prior = state.modules_enabled.model_dump()
    if prior == new_values:
        return []

    for key, value in new_values.items():
        setattr(state.modules_enabled, key, value)

    changed_steps = S.sync_module_status(state)
    S.append_history(
        state,
        actor="pm",
        action="modules_toggled",
        details={
            "from": prior,
            "to": new_values,
            "changed_steps": changed_steps,
        },
    )
    return changed_steps
