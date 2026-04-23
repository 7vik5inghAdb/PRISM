"""PRISM v1 shared state manager.

Every run has a single `runs/<run_id>/state.json` that is the authoritative
source of truth for all agents and the Streamlit UI. Every mutation:

1. Writes back the full state (atomic replace).
2. Appends a record to `state.history` so we have a complete audit trail.
3. Reconciles dependent step statuses (stale propagation, module opt-out).

Agent-owned payload shapes (Persona, Instrument, PanelResponse, etc.) live in
`prism/schemas.py` and will be tightened in Step 6 of the rebuild. For now
those are stored as loose `dict[str, Any]` on the State model so upstream code
can keep working while we refactor.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Step identifiers and dependency graph
# ---------------------------------------------------------------------------

STEP_SETUP = "setup"
STEP_METHOD = "method"
STEP_PERSONA = "persona"
STEP_INSTRUMENT = "instrument"
STEP_PANEL = "panel"
STEP_ASSESSMENT = "assessment"
STEP_CULTURAL_RISK = "secondary.cultural_risk"
STEP_COMPETITIVE = "secondary.competitive_analysis"
STEP_MARKET_CONTEXT = "secondary.market_context"
STEP_CHARTING = "charting"
STEP_REPORT = "report"

ALL_STEPS: list[str] = [
    STEP_SETUP,
    STEP_METHOD,
    STEP_PERSONA,
    STEP_INSTRUMENT,
    STEP_PANEL,
    STEP_ASSESSMENT,
    STEP_CULTURAL_RISK,
    STEP_COMPETITIVE,
    STEP_MARKET_CONTEXT,
    STEP_CHARTING,
    STEP_REPORT,
]

# When the key step is (re-)run, these downstream steps become stale if they
# were previously complete. Ordering is not meaningful.
DOWNSTREAM_OF: dict[str, list[str]] = {
    STEP_SETUP: [
        STEP_METHOD,
        STEP_PERSONA,
        STEP_INSTRUMENT,
        STEP_PANEL,
        STEP_ASSESSMENT,
        STEP_CULTURAL_RISK,
        STEP_COMPETITIVE,
        STEP_MARKET_CONTEXT,
        STEP_CHARTING,
        STEP_REPORT,
    ],
    STEP_METHOD: [
        STEP_PERSONA,
        STEP_INSTRUMENT,
        STEP_PANEL,
        STEP_ASSESSMENT,
        STEP_REPORT,
    ],
    STEP_PERSONA: [STEP_INSTRUMENT, STEP_PANEL, STEP_ASSESSMENT, STEP_REPORT],
    STEP_INSTRUMENT: [STEP_PANEL, STEP_ASSESSMENT, STEP_REPORT],
    STEP_PANEL: [STEP_ASSESSMENT, STEP_CHARTING, STEP_REPORT],
    STEP_ASSESSMENT: [STEP_CHARTING, STEP_REPORT],
    STEP_CULTURAL_RISK: [STEP_REPORT],
    STEP_COMPETITIVE: [STEP_REPORT],
    STEP_MARKET_CONTEXT: [STEP_REPORT],
    STEP_CHARTING: [STEP_REPORT],
}

# Maps module toggle key -> step key for reconciliation.
_MODULE_TO_STEP: dict[str, str] = {
    "cultural_risk": STEP_CULTURAL_RISK,
    "competitive_analysis": STEP_COMPETITIVE,
    "market_context": STEP_MARKET_CONTEXT,
    "charting": STEP_CHARTING,
}


# ---------------------------------------------------------------------------
# Enums and nested models
# ---------------------------------------------------------------------------


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    STALE = "stale"
    FAILED = "failed"
    DISABLED = "disabled"


class Market(BaseModel):
    locale: str  # e.g. "ja-JP"
    country: str  # e.g. "Japan"


class Variant(BaseModel):
    id: str
    label: str
    path: str  # relative to repo root
    is_control: bool = False


class ProductContext(BaseModel):
    application: str
    product_unit: str
    feature: str
    asset_type: str
    use_case: str


class PassCriteria(BaseModel):
    min_top_variant_share: float = 0.65
    max_cultural_red_flags: int = 1


class Setup(BaseModel):
    hypothesis: str
    source_market: Market
    target_markets: list[Market]
    product_context: ProductContext
    variants: list[Variant]
    pass_criteria: PassCriteria = Field(default_factory=PassCriteria)
    panel_size_per_market: int = 12


class MethodAxes(BaseModel):
    qualitative: bool = False
    quantitative: bool = False
    behavioral: bool = False
    attitudinal: bool = False


class Method(BaseModel):
    axes: MethodAxes
    selected_methods: list[str]
    research_questions: list[str]


class ModulesEnabled(BaseModel):
    """Toggleable modules. Setup/Method/Persona/Instrument/Panel/Assessment/Report are always on."""
    cultural_risk: bool = True
    competitive_analysis: bool = True
    market_context: bool = True
    charting: bool = True


class HistoryEntry(BaseModel):
    ts: str  # ISO 8601 UTC
    actor: str  # "pm" | "orchestrator" | "system" | agent name
    action: str
    details: dict[str, Any] = Field(default_factory=dict)


class Chart(BaseModel):
    path: str  # relative to the run dir
    title: str
    description: str
    source_step: str


class ReportPaths(BaseModel):
    md_path: Optional[str] = None
    json_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Root state model
# ---------------------------------------------------------------------------


class State(BaseModel):
    run_id: str
    schema_version: int = SCHEMA_VERSION
    created_at: str
    updated_at: str

    modules_enabled: ModulesEnabled = Field(default_factory=ModulesEnabled)
    step_status: dict[str, StepStatus] = Field(default_factory=dict)

    # Structured envelopes
    setup: Optional[Setup] = None
    method: Optional[Method] = None

    # Per-market payloads. Shape of inner values is owned by the respective agent
    # and will be tightened in Step 6; kept loose here so state.py can land first.
    # persona: {"by_market": {"<locale>": Persona}}
    # instrument: {"by_market": {"<locale>": Instrument}}
    # panel_responses: {"by_market": {"<locale>": list[PanelResponse]}}
    # assessment: {"by_market": {"<locale>": Assessment}, "cross_market": {...}}
    persona: Optional[dict[str, Any]] = None
    instrument: Optional[dict[str, Any]] = None
    panel_responses: Optional[dict[str, Any]] = None
    assessment: Optional[dict[str, Any]] = None

    # secondary: {"cultural_risk": {...}, "competitive_analysis": {...}, "market_context": {...}}
    secondary: Optional[dict[str, Any]] = None

    charts: list[Chart] = Field(default_factory=list)
    report: Optional[ReportPaths] = None

    history: list[HistoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(run_id: str) -> Path:
    return run_dir(run_id) / "state.json"


def exists(run_id: str) -> bool:
    return state_path(run_id).exists()


def resolve_asset_path(relative: str) -> Path:
    """Resolve a variant-image path (relative to repo root) into an absolute Path.

    Raises FileNotFoundError if the asset does not exist.
    """
    p = REPO_ROOT / relative
    if not p.exists():
        raise FileNotFoundError(f"Asset not found: {p}")
    return p


def list_runs() -> list[str]:
    """List run_ids that have a state.json (v1 runs only; old v0 runs excluded)."""
    if not RUNS_DIR.exists():
        return []
    return sorted(
        p.name
        for p in RUNS_DIR.iterdir()
        if p.is_dir() and (p / "state.json").exists()
    )


def list_legacy_runs() -> list[str]:
    """List v0 runs (have per-step JSON but no state.json). Read-only reference."""
    if not RUNS_DIR.exists():
        return []
    return sorted(
        p.name
        for p in RUNS_DIR.iterdir()
        if p.is_dir()
        and not (p / "state.json").exists()
        and any(p.glob("*.json"))
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def new_run(run_id: str, modules_enabled: Optional[ModulesEnabled] = None) -> State:
    if exists(run_id):
        raise FileExistsError(
            f"Run '{run_id}' already has a state.json at {state_path(run_id)}."
        )
    now = _now_iso()
    state = State(
        run_id=run_id,
        created_at=now,
        updated_at=now,
        modules_enabled=modules_enabled or ModulesEnabled(),
        step_status={s: StepStatus.PENDING for s in ALL_STEPS},
    )
    sync_module_status(state)
    append_history(state, actor="system", action="run_created", details={"run_id": run_id})
    save(state)
    return state


def load(run_id: str) -> State:
    path = state_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"No state.json for run '{run_id}' at {path}.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return State.model_validate(data)


def save(state: State) -> Path:
    state.updated_at = _now_iso()
    path = state_path(state.run_id)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    tmp.replace(path)
    return path


# ---------------------------------------------------------------------------
# History, status, and staleness
# ---------------------------------------------------------------------------


def append_history(
    state: State,
    *,
    actor: str,
    action: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    state.history.append(
        HistoryEntry(
            ts=_now_iso(),
            actor=actor,
            action=action,
            details=details or {},
        )
    )


def mark_status(state: State, step: str, status: Union[StepStatus, str]) -> None:
    if step not in ALL_STEPS:
        raise ValueError(f"Unknown step '{step}'. Known: {ALL_STEPS}")
    if isinstance(status, str):
        status = StepStatus(status)
    state.step_status[step] = status
    append_history(
        state,
        actor="system",
        action="status_changed",
        details={"step": step, "status": status.value},
    )


def mark_downstream_stale(state: State, step: str) -> list[str]:
    """Mark every downstream step whose status was COMPLETE as STALE.

    Returns the list of steps newly marked stale (for UI messaging).
    """
    affected: list[str] = []
    for downstream in DOWNSTREAM_OF.get(step, []):
        if state.step_status.get(downstream) == StepStatus.COMPLETE:
            state.step_status[downstream] = StepStatus.STALE
            affected.append(downstream)
    if affected:
        append_history(
            state,
            actor="system",
            action="downstream_stale",
            details={"triggered_by": step, "affected": affected},
        )
    return affected


def _has_payload(state: "State", step: str) -> bool:
    """Has the step produced data on disk already? Used to preserve COMPLETE
    across disable/re-enable cycles."""
    if step == STEP_CULTURAL_RISK:
        return bool(state.secondary and state.secondary.get("cultural_risk"))
    if step == STEP_COMPETITIVE:
        return bool(state.secondary and state.secondary.get("competitive_analysis"))
    if step == STEP_MARKET_CONTEXT:
        return bool(state.secondary and state.secondary.get("market_context"))
    if step == STEP_CHARTING:
        return bool(state.charts)
    return False


def sync_module_status(state: State) -> list[str]:
    """Reconcile step_status with modules_enabled.

    Steps whose module is off become DISABLED (data preserved on disk).
    Steps whose module is (re-)enabled:
      - become COMPLETE if a payload already exists (work isn't lost),
      - otherwise become PENDING.

    Returns the list of steps whose status changed as a result.
    """
    changed: list[str] = []
    for mod_key, step_key in _MODULE_TO_STEP.items():
        enabled = getattr(state.modules_enabled, mod_key)
        current = state.step_status.get(step_key, StepStatus.PENDING)
        if not enabled:
            if current != StepStatus.DISABLED:
                state.step_status[step_key] = StepStatus.DISABLED
                changed.append(step_key)
        else:  # enabled
            if current == StepStatus.DISABLED:
                new_status = (
                    StepStatus.COMPLETE if _has_payload(state, step_key) else StepStatus.PENDING
                )
                state.step_status[step_key] = new_status
                changed.append(step_key)
    if changed:
        append_history(
            state,
            actor="system",
            action="module_status_synced",
            details={"changed": changed},
        )
    return changed


def can_run(state: State, step: str) -> tuple[bool, str]:
    """Can `step` be run right now? Returns (ok, reason_if_not)."""
    if step not in ALL_STEPS:
        return False, f"Unknown step '{step}'"
    if state.step_status.get(step) == StepStatus.DISABLED:
        return False, f"Step '{step}' is disabled (module opt-out)."
    # A step can run iff all its hard dependencies are COMPLETE or non-required.
    for dep, downstreams in DOWNSTREAM_OF.items():
        if step in downstreams:
            dep_status = state.step_status.get(dep)
            if dep_status in (StepStatus.DISABLED,):
                # Disabled deps don't block — e.g. charting disabled doesn't block report.
                continue
            if dep_status not in (StepStatus.COMPLETE,):
                # Allow running if dep is only optional (module-off handled above),
                # otherwise must be complete.
                return False, f"Step '{step}' needs '{dep}' to be complete (currently {dep_status})."
    return True, ""


def progress_summary(state: State) -> dict[str, Any]:
    """Compact view of pipeline progress for the UI header."""
    counts: dict[str, int] = {s.value: 0 for s in StepStatus}
    for step in ALL_STEPS:
        st = state.step_status.get(step, StepStatus.PENDING)
        counts[st.value] += 1
    return {
        "run_id": state.run_id,
        "counts": counts,
        "updated_at": state.updated_at,
    }
