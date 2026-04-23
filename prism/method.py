"""Agent for generating research questions from a hypothesis + chosen axes/methods.

This is the pre-instrument reasoning: given the hypothesis, the markets under
study, and the methodological axes the PM picked (qual/quant, behavioral/
attitudinal) plus specific methods (survey, A/B, interviews, etc.), produce
4-6 concrete research questions that the downstream instrument and panel will
answer.

Opus 4.7 with adaptive thinking — this shapes every step after it, so we pay
for quality here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from prism.llm import call_structured


# ---------------------------------------------------------------------------
# Axes & methods taxonomy
# ---------------------------------------------------------------------------

AXIS_KEYS: list[str] = ["qualitative", "quantitative", "behavioral", "attitudinal"]

AXIS_LABELS: dict[str, str] = {
    "qualitative": "Qualitative",
    "quantitative": "Quantitative",
    "behavioral": "Behavioral",
    "attitudinal": "Attitudinal",
}

METHOD_KEYS: list[str] = [
    "observational",
    "usability_testing",
    "benchmarking",
    "eye_tracking",
    "ab_testing",
    "diary_study",
    "interviews",
    "concept_testing",
    "focus_groups",
    "card_sorting",
    "survey",
]

METHOD_LABELS: dict[str, str] = {
    "observational": "Observational",
    "usability_testing": "Usability Testing",
    "benchmarking": "Benchmarking",
    "eye_tracking": "Eye-tracking",
    "ab_testing": "A/B Testing",
    "diary_study": "Diary Study",
    "interviews": "Interviews",
    "concept_testing": "Concept Testing",
    "focus_groups": "Focus Groups",
    "card_sorting": "Card Sorting",
    "survey": "Survey",
}

# Canonical axis tags per method. Based on NN/g-style UX research taxonomy.
METHOD_AXES: dict[str, set[str]] = {
    "observational":     {"qualitative", "behavioral"},
    "usability_testing": {"qualitative", "quantitative", "behavioral", "attitudinal"},
    "benchmarking":      {"quantitative", "behavioral", "attitudinal"},
    "eye_tracking":      {"qualitative", "quantitative", "behavioral"},
    "ab_testing":        {"quantitative", "behavioral"},
    "diary_study":       {"qualitative", "behavioral", "attitudinal"},
    "interviews":        {"qualitative", "attitudinal"},
    "concept_testing":   {"qualitative", "quantitative", "attitudinal"},
    "focus_groups":      {"qualitative", "attitudinal"},
    "card_sorting":      {"qualitative", "quantitative", "attitudinal"},
    "survey":            {"qualitative", "quantitative", "attitudinal"},
}


def methods_matching_axes(selected_axes: list[str]) -> list[tuple[str, int]]:
    """Return methods ranked by how many of the selected axes they cover.

    Returns list of (method_key, overlap_count), sorted overlap desc then name.
    """
    selected = set(selected_axes)
    scored = [
        (m, len(METHOD_AXES[m] & selected))
        for m in METHOD_KEYS
    ]
    scored.sort(key=lambda t: (-t[1], METHOD_LABELS[t[0]]))
    return scored


# ---------------------------------------------------------------------------
# Agent: research question generation
# ---------------------------------------------------------------------------


class ResearchQuestions(BaseModel):
    questions: list[str] = Field(
        description=(
            "4-6 concrete, answerable research questions that the downstream "
            "instrument and synthetic panel will address. Each should be "
            "specific enough that a respondent's answer to the panel would "
            "resolve it, not vague aspirations."
        )
    )
    rationale: str = Field(
        description=(
            "One short paragraph explaining how these questions map to the "
            "chosen axes and methods, and to the hypothesis under test."
        )
    )


_SYSTEM = (
    "Write 4-6 specific research questions tied to the hypothesis. Each must be "
    "answerable by the chosen methods (behavioral methods → probe what people do; "
    "attitudinal → probe belief/preference). Plain English, no jargon."
)


def generate_research_questions(
    *,
    hypothesis: str,
    source_locale: str,
    source_country: str,
    target_markets: list[dict],
    selected_axes: list[str],
    selected_methods: list[str],
    product_context: dict,
    model: str = "claude-haiku-4-5",
) -> ResearchQuestions:
    tgt_list = ", ".join(f"{m['country']} ({m['locale']})" for m in target_markets)
    axes_list = ", ".join(AXIS_LABELS[a] for a in selected_axes) or "(none)"
    methods_list = ", ".join(METHOD_LABELS[m] for m in selected_methods) or "(none)"

    user = (
        f"Hypothesis: {hypothesis}\n"
        f"Source: {source_country} ({source_locale})\n"
        f"Targets: {tgt_list}\n"
        f"Asset: {product_context.get('application')} · "
        f"{product_context.get('asset_type')} · feature: {product_context.get('feature')}\n"
        f"Axes: {axes_list}\n"
        f"Methods: {methods_list}\n\n"
        f"Produce 4-6 research questions + one short rationale."
    )

    return call_structured(
        model=model,
        system=_SYSTEM,
        user_content=user,
        response_model=ResearchQuestions,
        max_tokens=3000,
    )
