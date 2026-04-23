"""Charting agent — generates static PNGs from state.

Deterministic (not LLM-driven): it reads state, decides which charts are
applicable given what data is present, and produces matplotlib PNGs under
`runs/<run_id>/charts/`. The list of produced charts lands at
`state.charts: list[Chart]` with `path` relative to the run dir.

Charts produced (each is skipped if its source data isn't in state):
1. Variant top-rank share — per market (grouped bar)
2. Variant mean appropriateness score — per market (grouped bar)
3. Cross-market mean-score heatmap (only if >1 target market)
4. Confidence summary — per market + cross-market (horizontal bar)
5. Per-variant red-flag counts (aggregated across markets)
6. Cultural risk severity per finding (if cultural_risk sub-agent ran)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # non-interactive backend — safe in Streamlit server context

import matplotlib.pyplot as plt
import numpy as np

from prism import aggregator as aggregator_agent
from prism import secondary as secondary_agent
from prism import state as S
from prism.schemas import Assessment


# Consistent styling
plt.style.use("seaborn-v0_8-whitegrid")

FIG_DPI = 110
CONF_BANDS = [(0, 40, "#d9534f"), (40, 60, "#f0ad4e"), (60, 80, "#f7d85a"), (80, 100, "#5cb85c")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _charts_dir(state: S.State) -> Path:
    d = S.run_dir(state.run_id) / "charts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(fig, charts_dir: Path, filename: str) -> str:
    """Save and return path relative to the run directory."""
    full = charts_dir / filename
    fig.savefig(full, bbox_inches="tight", dpi=FIG_DPI)
    plt.close(fig)
    return str(Path("charts") / filename)


def _confidence_color(score: int) -> str:
    for lo, hi, color in CONF_BANDS:
        if lo <= score < hi:
            return color
    return CONF_BANDS[-1][2]  # 100 -> last band


def _variant_labels(state: S.State) -> dict[str, str]:
    """variant_id -> short label for x-axis ticks."""
    if state.setup is None:
        return {}
    return {v.id: f"{v.id}\n{v.label[:18]}" for v in state.setup.variants}


def _market_label(m: S.Market) -> str:
    return f"{m.country}\n({m.locale})"


# ---------------------------------------------------------------------------
# Per-chart builders
# ---------------------------------------------------------------------------


def chart_top_rank_per_market(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    assessments = aggregator_agent.get_all_assessments(state)
    if not assessments or state.setup is None:
        return None

    variant_ids = [v.id for v in state.setup.variants]
    markets = [m for m in state.setup.target_markets if m.locale in assessments]
    if not markets or not variant_ids:
        return None

    n_variants = len(variant_ids)
    n_markets = len(markets)
    width = 0.8 / n_markets

    fig, ax = plt.subplots(figsize=(max(7, n_variants * 1.3), 4.8))
    x = np.arange(n_variants)

    for i, m in enumerate(markets):
        a = assessments[m.locale]
        shares = [a.variant_top_rank_shares.get(vid, 0.0) * 100 for vid in variant_ids]
        offset = (i - (n_markets - 1) / 2) * width
        bars = ax.bar(x + offset, shares, width, label=_market_label(m))
        for b, share in zip(bars, shares):
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 1,
                f"{share:.0f}%",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    labels = _variant_labels(state)
    ax.set_xticks(x, [labels[v] for v in variant_ids])
    ax.set_ylabel("Panel share ranking 1st (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Top-rank share per variant, by market")
    ax.legend(loc="upper right", framealpha=0.9)

    path = _save(fig, charts_dir, "top_rank_per_market.png")
    return S.Chart(
        path=path,
        title="Top-rank share per variant, by market",
        description="Share of each market's panel that ranked each variant 1st.",
        source_step=S.STEP_CHARTING,
    )


def chart_mean_scores_per_market(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    assessments = aggregator_agent.get_all_assessments(state)
    if not assessments or state.setup is None:
        return None

    variant_ids = [v.id for v in state.setup.variants]
    markets = [m for m in state.setup.target_markets if m.locale in assessments]
    if not markets or not variant_ids:
        return None

    n_variants = len(variant_ids)
    n_markets = len(markets)
    width = 0.8 / n_markets

    fig, ax = plt.subplots(figsize=(max(7, n_variants * 1.3), 4.8))
    x = np.arange(n_variants)

    for i, m in enumerate(markets):
        a = assessments[m.locale]
        scores = [a.variant_mean_scores.get(vid, 0.0) for vid in variant_ids]
        offset = (i - (n_markets - 1) / 2) * width
        bars = ax.bar(x + offset, scores, width, label=_market_label(m))
        for b, s in zip(bars, scores):
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 1,
                f"{s:.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    labels = _variant_labels(state)
    ax.set_xticks(x, [labels[v] for v in variant_ids])
    ax.set_ylabel("Mean appropriateness score (0-100)")
    ax.set_ylim(0, 110)
    ax.set_title("Mean appropriateness score per variant, by market")
    ax.legend(loc="upper right", framealpha=0.9)

    path = _save(fig, charts_dir, "mean_scores_per_market.png")
    return S.Chart(
        path=path,
        title="Mean appropriateness score per variant, by market",
        description="Average respondent appropriateness score (0-100) for each variant, by market.",
        source_step=S.STEP_CHARTING,
    )


def chart_cross_market_heatmap(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    assessments = aggregator_agent.get_all_assessments(state)
    if not assessments or state.setup is None or len(state.setup.target_markets) < 2:
        return None

    variant_ids = [v.id for v in state.setup.variants]
    markets = [m for m in state.setup.target_markets if m.locale in assessments]
    if len(markets) < 2:
        return None

    data = np.array(
        [[assessments[m.locale].variant_mean_scores.get(vid, 0.0) for vid in variant_ids] for m in markets]
    )

    fig, ax = plt.subplots(figsize=(max(6, len(variant_ids) * 1.3), max(3.5, len(markets) * 0.7 + 1.5)))
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(np.arange(len(variant_ids)), variant_ids)
    ax.set_yticks(np.arange(len(markets)), [_market_label(m).replace("\n", " ") for m in markets])

    for i in range(len(markets)):
        for j in range(len(variant_ids)):
            val = data[i, j]
            color = "white" if val < 30 or val > 75 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", color=color, fontsize=10, fontweight="bold")

    ax.set_title("Mean appropriateness score — variants × markets")
    fig.colorbar(im, ax=ax, label="Mean score (0-100)")

    path = _save(fig, charts_dir, "cross_market_heatmap.png")
    return S.Chart(
        path=path,
        title="Mean score heatmap — variants × markets",
        description="Cross-market comparability view of mean appropriateness scores.",
        source_step=S.STEP_CHARTING,
    )


def chart_confidence_summary(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    per_market = aggregator_agent.get_all_assessments(state)
    cross = aggregator_agent.get_cross_market(state)
    if not per_market and cross is None:
        return None

    rows: list[tuple[str, int]] = []
    for locale, a in per_market.items():
        rows.append((locale, a.confidence_0_100))
    if cross is not None:
        rows.append(("Cross-market", cross.confidence_0_100))

    if not rows:
        return None

    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    colors = [_confidence_color(v) for v in values]

    fig, ax = plt.subplots(figsize=(7, max(2, 0.6 * len(rows) + 1)))
    bars = ax.barh(labels, values, color=colors, edgecolor="#333", linewidth=0.6)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Confidence (0-100)")
    ax.set_title("Assessment confidence by market")

    for bar, value in zip(bars, values):
        ax.text(
            value + 1, bar.get_y() + bar.get_height() / 2,
            f"{value}",
            va="center", fontsize=10, fontweight="bold",
        )

    # Band legend
    for lo, hi, color in CONF_BANDS:
        ax.axvspan(lo, hi, ymin=0, ymax=0.04, color=color, alpha=0.35)

    path = _save(fig, charts_dir, "confidence_summary.png")
    return S.Chart(
        path=path,
        title="Assessment confidence by market",
        description="Primary + cross-market confidence scores on the 0-100 scale.",
        source_step=S.STEP_CHARTING,
    )


def chart_red_flags_per_variant(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    assessments = aggregator_agent.get_all_assessments(state)
    if not assessments or state.setup is None:
        return None

    variant_ids = [v.id for v in state.setup.variants]
    counts: dict[str, int] = {vid: 0 for vid in variant_ids}
    for a in assessments.values():
        for flag in a.cultural_red_flags:
            # flags are "[variant_id] text"
            if flag.startswith("[") and "]" in flag:
                vid = flag[1 : flag.index("]")]
                if vid in counts:
                    counts[vid] += 1

    if sum(counts.values()) == 0:
        return None

    labels = [_variant_labels(state)[v] for v in variant_ids]
    values = [counts[v] for v in variant_ids]

    fig, ax = plt.subplots(figsize=(max(6, len(variant_ids) * 1.2), 4.2))
    bars = ax.bar(labels, values, color="#d9534f", edgecolor="#7a1f1f", linewidth=0.6)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.15, str(v),
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Distinct red flags (across markets)")
    ax.set_title("Cultural red-flag count per variant")
    ax.set_ylim(0, max(values) * 1.2 + 1)

    path = _save(fig, charts_dir, "red_flags_per_variant.png")
    return S.Chart(
        path=path,
        title="Cultural red-flag count per variant",
        description="Aggregated across all markets with assessments.",
        source_step=S.STEP_CHARTING,
    )


def chart_cultural_risk_severity(state: S.State, charts_dir: Path) -> Optional[S.Chart]:
    syn = secondary_agent.get_cultural_risk(state)
    if syn is None or not syn.findings:
        return None

    findings = sorted(syn.findings, key=lambda f: f.severity_0_100)
    labels = [(f.title[:40] + "…") if len(f.title) > 40 else f.title for f in findings]
    values = [f.severity_0_100 for f in findings]
    colors = [_confidence_color(v) for v in values]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.5 * len(findings) + 1.5)))
    bars = ax.barh(labels, values, color=colors, edgecolor="#333", linewidth=0.6)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Severity (0-100)")
    ax.set_title(f"Cultural risk findings (overall: {syn.overall_risk_0_100}/100)")
    for bar, v in zip(bars, values):
        ax.text(v + 1, bar.get_y() + bar.get_height() / 2, f"{v}",
                va="center", fontsize=9, fontweight="bold")

    path = _save(fig, charts_dir, "cultural_risk_severity.png")
    return S.Chart(
        path=path,
        title="Cultural risk finding severity",
        description="Sorted ascending by severity. Overall risk is the aggregate score.",
        source_step=S.STEP_CHARTING,
    )


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def build_charts(state: S.State) -> list[S.Chart]:
    """Generate all applicable charts. Writes files + returns metadata list."""
    charts_dir = _charts_dir(state)

    builders = [
        chart_top_rank_per_market,
        chart_mean_scores_per_market,
        chart_cross_market_heatmap,
        chart_confidence_summary,
        chart_red_flags_per_variant,
        chart_cultural_risk_severity,
    ]

    produced: list[S.Chart] = []
    for fn in builders:
        try:
            chart = fn(state, charts_dir)
        except Exception as e:  # noqa: BLE001
            S.append_history(
                state, actor="charting_agent", action="chart_failed",
                details={"builder": fn.__name__, "error": str(e)},
            )
            continue
        if chart is not None:
            produced.append(chart)
            S.append_history(
                state, actor="charting_agent", action="chart_built",
                details={"title": chart.title, "path": chart.path},
            )

    # Replace state.charts with this run's charts (prior charts are overwritten)
    state.charts = produced
    S.save(state)
    return produced
