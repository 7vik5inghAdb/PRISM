"""Per-step view modules.

Each step is a module that exports `render(state: State, step: str) -> None`.
The module is responsible for:

- Displaying the step's form or action UI.
- Calling the relevant agent (Persona Architect, Panel, etc.).
- Writing results to state via `prism.state.save(state)`.
- Asking the orchestrator to confirm, then marking the step complete.
"""

from __future__ import annotations

from prism import state as S


def render_step(state: S.State, step: str) -> None:
    """Dispatch to the correct per-step renderer.

    Steps that haven't been implemented yet fall through to the placeholder.
    Later checkpoints replace the placeholder imports.
    """
    if step == S.STEP_SETUP:
        from prism.steps import setup as mod
    elif step == S.STEP_METHOD:
        from prism.steps import method as mod
    elif step == S.STEP_PERSONA:
        from prism.steps import persona as mod
    elif step == S.STEP_INSTRUMENT:
        from prism.steps import instrument as mod
    elif step == S.STEP_PANEL:
        from prism.steps import panel as mod
    elif step == S.STEP_ASSESSMENT:
        from prism.steps import assessment as mod
    elif step == S.STEP_CULTURAL_RISK:
        from prism.steps import cultural_risk as mod
    elif step == S.STEP_COMPETITIVE:
        from prism.steps import competitive as mod
    elif step == S.STEP_MARKET_CONTEXT:
        from prism.steps import market_context as mod
    elif step == S.STEP_CHARTING:
        from prism.steps import charting as mod
    elif step == S.STEP_REPORT:
        from prism.steps import report as mod
    else:
        from prism.steps import placeholder as mod

    mod.render(state, step)
