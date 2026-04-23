"""Pydantic schemas shared across PRISM v1 agents.

These are the "payload" schemas owned by each agent. Run-level envelope schemas
(State, Setup, Method, Market, Variant, ProductContext, PassCriteria, etc.)
live in `prism.state`.

Step 6 generalizes panel/assessment schemas to support n variants (ranking and
numerical confidence arrive in Steps 7 and 8 respectively). Secondary and
Report schemas here are v0 carry-overs that Steps 9 and 11 will replace.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------


class RespondentArchetype(BaseModel):
    archetype_id: str
    name: str
    age_band: str
    gender: str
    region: str
    occupation: str
    tech_comfort: str
    cultural_notes: str = Field(
        description=(
            "Culture- and market-specific context that shapes how this respondent "
            "would react to promotional design (aesthetics, reading conventions, "
            "formality expectations, seasonal/holiday salience)."
        )
    )


class Persona(BaseModel):
    """Target persona plus a roster of archetype respondents for one market."""

    market_summary: str = Field(
        description="2-4 sentence summary of the target market and buyer context."
    )
    target_segment: str
    key_cultural_dimensions: list[str] = Field(
        description=(
            "e.g. 'high-context communication', 'vertical script conventions', "
            "'seasonal motifs (sakura, momiji)', 'formality registers'."
        )
    )
    design_expectations: list[str] = Field(
        description="Visual/typographic norms the target audience expects in promotional assets."
    )
    archetypes: list[RespondentArchetype]


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------


class InstrumentItem(BaseModel):
    item_id: str
    question: str
    response_type: Literal["preference", "ranking", "likert_5", "open_text"]
    rationale: str = Field(
        description="Why this question maps to the research objective."
    )


class Instrument(BaseModel):
    """Research instrument for one market. Covers the methods the PM chose."""

    methods_covered: list[str] = Field(
        description="Method keys (e.g. 'ab_testing', 'survey') this instrument addresses."
    )
    stimulus_description: str = Field(
        description="What the respondent is shown and in what order."
    )
    items: list[InstrumentItem]
    pass_criteria_echo: str = Field(
        description="Restatement of pass/fail thresholds the aggregator will apply."
    )


# ---------------------------------------------------------------------------
# Panel responses
# ---------------------------------------------------------------------------


class PanelItemResponse(BaseModel):
    item_id: str
    answer: str
    reasoning: str = Field(
        default="",
        description="Optional one-sentence justification for the answer.",
    )


class VariantEvaluation(BaseModel):
    """One respondent's structured evaluation of one variant.

    Every PanelResponse contains one VariantEvaluation per variant in the run,
    so cross-market aggregation works on the same schema everywhere.
    """

    variant_id: str = Field(
        description="Must match a variant_id from state.setup.variants."
    )
    rank: int = Field(
        ge=1,
        description=(
            "1 = most appropriate for the respondent's market. "
            "Ranks must be unique within a single PanelResponse "
            "(no ties at the response level)."
        ),
    )
    appropriateness_score: int = Field(
        ge=0,
        le=100,
        description=(
            "0 = completely unsuitable for the respondent's market, "
            "100 = perfect fit. This is the standardized cross-market score."
        ),
    )
    variant_red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete issues specific to THIS variant that a respondent like "
            "you would flag (wrong register, inappropriate imagery, "
            "mistranslation, etc.). Empty if there are none."
        ),
    )
    reasoning: str = Field(
        description="One sentence explaining the rank and score for this variant."
    )


class PanelResponse(BaseModel):
    """A single synthetic respondent's universal response.

    Standardized regardless of market — every response carries:
    - A full ranking of all variants (`variant_evaluations`).
    - 0-100 appropriateness scores for each variant.
    - Per-variant red flags (not mixed into a global list).
    - English free-text throughout.
    """

    archetype_id: str
    variant_evaluations: list[VariantEvaluation] = Field(
        description=(
            "One VariantEvaluation per variant in the run. Ranks must be "
            "1..N with no duplicates; the respondent must commit to an order."
        )
    )
    items: list[PanelItemResponse] = Field(
        default_factory=list,
        description=(
            "Answers to the instrument's question items. Separate from the "
            "variant_evaluations ranking — `items` covers open_text, likert, "
            "and other instrument-driven fields."
        ),
    )
    overall_reasoning: str = Field(
        description="2-4 sentence synthesis of the respondent's overall take."
    )


# ---------------------------------------------------------------------------
# Primary assessment (per market)
# ---------------------------------------------------------------------------


class Assessment(BaseModel):
    """Primary assessment of one market's panel (ranking-based)."""

    verdict: Literal["pass", "fail", "needs_revision"]
    confidence_0_100: int = Field(
        ge=0,
        le=100,
        description=(
            "Numerical confidence (0-100) in this verdict. "
            "0-39 = weak signal, 40-59 = ambiguous, 60-79 = solid, 80-100 = clear. "
            "Drivers: gap between top variant and runner-up in both metrics, "
            "agreement between top-rank and mean-score winner, red-flag count, "
            "consistency across respondents."
        ),
    )
    variant_top_rank_shares: dict[str, float] = Field(
        description=(
            "Share of the panel that ranked each variant 1st (0.0-1.0). "
            "Shares sum to ~1.0 across variants."
        )
    )
    variant_mean_scores: dict[str, float] = Field(
        description=(
            "Mean appropriateness_score (0-100) across the panel for each variant."
        )
    )
    winning_variant_id: Optional[str] = Field(
        default=None,
        description=(
            "The variant with the highest top-rank share and highest mean score, "
            "or null if there's no clear winner."
        ),
    )
    cultural_red_flags: list[str] = Field(
        description=(
            "De-duplicated list of per-variant red flags raised across the panel. "
            "Each entry is prefixed with the variant_id it refers to, e.g. "
            "'[B] no Japanese text in headline'."
        )
    )
    rationale: str
    recommended_next_step: str


# ---------------------------------------------------------------------------
# Cross-market assessment (new for v1)
# ---------------------------------------------------------------------------


class CrossMarketAssessment(BaseModel):
    """Comparison across per-market assessments.

    Produced after every target market's per-market Assessment is complete.
    Lives at `state.assessment["cross_market"]`.
    """

    per_market_verdicts: dict[str, Literal["pass", "fail", "needs_revision"]] = Field(
        description="Map of locale -> verdict."
    )
    confidence_0_100: int = Field(
        ge=0,
        le=100,
        description=(
            "Numerical confidence (0-100) in this cross-market synthesis. "
            "Higher when markets converge strongly; lower when they diverge "
            "or when individual per-market confidences are low."
        ),
    )
    consistent_winners: list[str] = Field(
        description=(
            "Variant IDs that won (were the top-share variant) in every target market. "
            "Empty if every market had a different winner or no market had a clear winner."
        )
    )
    divergent_findings: list[str] = Field(
        description=(
            "Specific places where markets disagreed, with locales named. "
            "Each entry is a short sentence."
        )
    )
    cross_market_rationale: str = Field(
        description=(
            "2-4 sentence explanation of the convergence/divergence pattern across markets "
            "and what it implies for the ship decision."
        )
    )
    recommended_next_step: str = Field(
        description=(
            "Single concrete recommendation across markets — ship-all, ship-subset, "
            "revise-and-retest, or kill."
        )
    )


# ---------------------------------------------------------------------------
# Secondary + Report carry-overs (replaced in Steps 9 / 11)
# ---------------------------------------------------------------------------


class SecondaryCitation(BaseModel):
    claim: str = Field(
        description="A specific factual claim. Must be directly supportable by the source_url."
    )
    source_type: Literal[
        "web_source",
        "industry_knowledge",
        "competitor_behavior",
        "cultural_convention",
        "design_norm",
        "market_trend",
    ]
    source_url: Optional[str] = Field(
        default=None,
        description=(
            "URL backing this claim. Required when source_type='web_source'. "
            "May be null only for non-web sources (model training knowledge)."
        ),
    )
    confidence_0_100: int = Field(
        ge=0,
        le=100,
        description=(
            "Numerical confidence (0-100) in this claim. Web-sourced with recent "
            "authoritative URLs → 80+. Background knowledge with caveats → 40-60. "
            "Training-cutoff-dated or contested claims → below 40."
        ),
    )
    caveat: str = ""


# ---------- Cultural Risk sub-agent ----------


class CulturalRiskFinding(BaseModel):
    title: str = Field(
        description="Short phrase naming the risk (e.g. 'Seasonal motif mismatch')."
    )
    description: str = Field(
        description="2-4 sentences explaining the risk and why it matters for this run."
    )
    severity_0_100: int = Field(
        ge=0,
        le=100,
        description="How material this risk is to the ship decision.",
    )
    affected_markets: list[str] = Field(
        description="Locales from state.setup.target_markets this risk applies to."
    )
    citations: list[SecondaryCitation]


class CulturalRiskSynthesis(BaseModel):
    findings: list[CulturalRiskFinding]
    overall_risk_0_100: int = Field(
        ge=0,
        le=100,
        description="Aggregate cultural risk across markets (0=no risk, 100=do-not-ship).",
    )
    summary: str = Field(
        description="3-5 sentence PM-facing summary of the risk picture."
    )


# ---------- Competitive Analysis sub-agent ----------


class Competitor(BaseModel):
    name: str
    positioning: str = Field(
        description="One-sentence positioning relative to the application under study."
    )
    relevant_offerings: list[str] = Field(
        description="Specific products/features that compete with the asset type under test."
    )
    threat_level_0_100: int = Field(
        ge=0,
        le=100,
        description="How much of a competitive threat this competitor is for the current run.",
    )
    citations: list[SecondaryCitation]


class CompetitiveAnalysisSynthesis(BaseModel):
    competitors: list[Competitor]
    landscape_summary: str = Field(
        description="3-5 sentence view of the competitive landscape across target markets."
    )
    threats: list[str] = Field(
        description="Concrete competitive threats this run should factor into its decision."
    )
    opportunities: list[str] = Field(
        description="Gaps or differentiators this run could exploit."
    )


# ---------- Market Context sub-agent ----------


class MarketContextSynthesis(BaseModel):
    sizing_qualitative: str = Field(
        description="Qualitative sizing of the addressable market across target countries."
    )
    growth_signals: list[str] = Field(
        description="Specific growth indicators (user growth, revenue, adoption) with citations."
    )
    audience_behaviors: list[str] = Field(
        description="How the target audience currently creates/consumes this asset type."
    )
    adjacent_trends: list[str] = Field(
        description="Related market movements (tooling, design taste, platform shifts)."
    )
    citations: list[SecondaryCitation]
    summary: str


class TriangulatedReport(BaseModel):
    """LLM-generated narrative sections of the final report.

    Only module-specific summaries for modules that actually ran are populated;
    disabled-module fields stay null and are skipped in the rendered output.
    Deterministic sections (tables, charts, appendix) are not in this model —
    they are assembled by the Markdown renderer directly from state.
    """

    executive_summary: str = Field(
        description="3-5 sentence TL;DR a PM can paste into a status update."
    )
    headline_verdict: Literal["pass", "fail", "needs_revision"]
    confidence_0_100: int = Field(
        ge=0,
        le=100,
        description=(
            "Numerical confidence (0-100) in the triangulated verdict. Higher "
            "when primary panel and enabled secondary modules converge strongly."
        ),
    )
    primary_findings_summary: str = Field(
        description="2-4 paragraph summary of the per-market and cross-market panel assessments."
    )
    cultural_risk_summary: Optional[str] = Field(
        default=None,
        description="Summary of Cultural Risk sub-agent findings. Null if that module was disabled/skipped.",
    )
    competitive_summary: Optional[str] = Field(
        default=None,
        description="Summary of Competitive Analysis sub-agent findings. Null if disabled/skipped.",
    )
    market_context_summary: Optional[str] = Field(
        default=None,
        description="Summary of Market Context sub-agent findings. Null if disabled/skipped.",
    )
    convergence_analysis: str = Field(
        description=(
            "Where primary panel and enabled secondary modules agree, where they "
            "diverge, and what that implies for the ship decision."
        )
    )
    cultural_red_flags: list[str] = Field(
        description="De-duplicated list of flags across primary + cultural risk (if enabled)."
    )
    recommended_actions: list[str] = Field(
        description="Concrete prioritized next steps for the PM. 3-7 items."
    )
    open_questions: list[str] = Field(
        description="Questions the run did not answer, worth flagging for follow-up."
    )
