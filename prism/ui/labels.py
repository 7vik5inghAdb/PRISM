"""Shared display labels for steps and statuses."""

from prism import state as S


STEP_LABELS: dict[str, str] = {
    S.STEP_SETUP: "Setup",
    S.STEP_METHOD: "Method",
    S.STEP_PERSONA: "Persona",
    S.STEP_INSTRUMENT: "Instrument",
    S.STEP_PANEL: "Panel",
    S.STEP_ASSESSMENT: "Assessment",
    S.STEP_CULTURAL_RISK: "↳ Cultural Risk",
    S.STEP_COMPETITIVE: "↳ Competitive",
    S.STEP_MARKET_CONTEXT: "↳ Market Context",
    S.STEP_CHARTING: "Charts",
    S.STEP_REPORT: "Report",
}


STATUS_BADGE: dict[S.StepStatus, str] = {
    S.StepStatus.PENDING: "⚪️",
    S.StepStatus.RUNNING: "🟡",
    S.StepStatus.COMPLETE: "🟢",
    S.StepStatus.STALE: "🟠",
    S.StepStatus.FAILED: "🔴",
    S.StepStatus.DISABLED: "⚫️",
}


STATUS_LABEL: dict[S.StepStatus, str] = {
    S.StepStatus.PENDING: "Pending",
    S.StepStatus.RUNNING: "Running",
    S.StepStatus.COMPLETE: "Complete",
    S.StepStatus.STALE: "Stale",
    S.StepStatus.FAILED: "Failed",
    S.StepStatus.DISABLED: "Disabled",
}


def confidence_badge(score: int) -> str:
    """Render a 0-100 confidence score as a colored badge string."""
    if score >= 80:
        return f"🟢 {score}/100"
    if score >= 60:
        return f"🟡 {score}/100"
    if score >= 40:
        return f"🟠 {score}/100"
    return f"🔴 {score}/100"


def confidence_label(score: int) -> str:
    if score >= 80:
        return "Clear"
    if score >= 60:
        return "Solid"
    if score >= 40:
        return "Ambiguous"
    return "Weak"
