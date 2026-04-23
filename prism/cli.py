"""PRISM-v0 CLI — step-by-step orchestration with HITL checkpoints.

Each subcommand runs exactly one pipeline step and writes its JSON artifact under
`runs/<run_id>/`. The PM reviews / edits that JSON before the next step runs.
`run-all` chains steps with a confirmation gate between each one.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel as RichPanel
from rich.table import Table

from prism.aggregator import assess as assess_run
from prism.artifacts import load_artifact, load_config, run_dir, save_artifact
from prism.instrument import design_instrument
from prism.panel import run_panel
from prism.persona import build_persona
from prism.report import build_report, save_report_markdown
from prism.schemas import (
    Assessment,
    Instrument,
    PanelResponse,
    Persona,
    RunConfig,
    SecondarySynthesis,
    TriangulatedReport,
)
from prism.secondary import synthesize_secondary


app = typer.Typer(
    add_completion=False,
    help="PRISM-v0 — synthetic research agency prototype (Adobe Express culturalization).",
)
console = Console()


def _load(config: Path) -> RunConfig:
    cfg = load_config(config)
    console.print(
        RichPanel.fit(
            f"[bold]run_id:[/bold] {cfg.run_id}\n"
            f"[bold]market:[/bold] {cfg.market.source_locale} → "
            f"{cfg.market.target_locale} ({cfg.market.country})\n"
            f"[bold]panel size:[/bold] {cfg.panel.size}",
            title="PRISM-v0 run",
        )
    )
    return cfg


# ---------- step 1: persona ----------

@app.command()
def persona(config: Path = typer.Option(..., exists=True, readable=True)):
    """Step 1 — build target persona + archetype roster."""
    cfg = _load(config)
    console.print("[bold cyan]→ Building persona...[/bold cyan]")
    p = build_persona(cfg)
    path = save_artifact(cfg.run_id, "persona", p)
    _show_persona(p)
    console.print(f"\n[green]Saved:[/green] {path}")


# ---------- step 2: instrument ----------

@app.command()
def instrument(config: Path = typer.Option(..., exists=True, readable=True)):
    """Step 2 — design A/B preference instrument."""
    cfg = _load(config)
    p = load_artifact(cfg.run_id, "persona", Persona)
    console.print("[bold cyan]→ Designing instrument...[/bold cyan]")
    inst = design_instrument(cfg, p)
    path = save_artifact(cfg.run_id, "instrument", inst)
    _show_instrument(inst)
    console.print(f"\n[green]Saved:[/green] {path}")


# ---------- step 3: panel ----------

@app.command()
def panel(
    config: Path = typer.Option(..., exists=True, readable=True),
    max_workers: int = typer.Option(6, help="Parallel respondent calls."),
):
    """Step 3 — run synthetic panel (multimodal, parallel)."""
    cfg = _load(config)
    p = load_artifact(cfg.run_id, "persona", Persona)
    inst = load_artifact(cfg.run_id, "instrument", Instrument)
    console.print(
        f"[bold cyan]→ Running panel ({len(p.archetypes)} respondents, "
        f"{max_workers} workers)...[/bold cyan]"
    )
    responses = run_panel(cfg, p, inst, max_workers=max_workers)
    path = save_artifact(
        cfg.run_id,
        "panel_responses",
        [r.model_dump(mode="json") for r in responses],
    )
    _show_panel_summary(responses)
    console.print(f"\n[green]Saved:[/green] {path}")


# ---------- step 4: assessment ----------

@app.command()
def assess(config: Path = typer.Option(..., exists=True, readable=True)):
    """Step 4 — roll up panel into pass/fail assessment."""
    cfg = _load(config)
    p = load_artifact(cfg.run_id, "persona", Persona)
    raw = load_artifact(cfg.run_id, "panel_responses")
    responses = [PanelResponse.model_validate(r) for r in raw]
    console.print("[bold cyan]→ Aggregating...[/bold cyan]")
    a = assess_run(cfg, p, responses)
    path = save_artifact(cfg.run_id, "assessment", a)
    _show_assessment(a)
    console.print(f"\n[green]Saved:[/green] {path}")


# ---------- step 5: secondary ----------

@app.command()
def secondary(config: Path = typer.Option(..., exists=True, readable=True)):
    """Step 5 — secondary synthesis (market / competitor / cultural context)."""
    cfg = _load(config)
    p = load_artifact(cfg.run_id, "persona", Persona)
    a = load_artifact(cfg.run_id, "assessment", Assessment)
    console.print("[bold cyan]→ Synthesizing secondary context...[/bold cyan]")
    s = synthesize_secondary(cfg, p, a)
    path = save_artifact(cfg.run_id, "secondary", s)
    _show_secondary(s)
    console.print(f"\n[green]Saved:[/green] {path}")


# ---------- step 6: report ----------

@app.command()
def report(config: Path = typer.Option(..., exists=True, readable=True)):
    """Step 6 — triangulated report (JSON + Markdown)."""
    cfg = _load(config)
    p = load_artifact(cfg.run_id, "persona", Persona)
    raw = load_artifact(cfg.run_id, "panel_responses")
    responses = [PanelResponse.model_validate(r) for r in raw]
    a = load_artifact(cfg.run_id, "assessment", Assessment)
    s = load_artifact(cfg.run_id, "secondary", SecondarySynthesis)
    console.print("[bold cyan]→ Compiling triangulated report...[/bold cyan]")
    rep = build_report(cfg, p, responses, a, s)
    json_path = save_artifact(cfg.run_id, "report", rep)
    md_path = save_report_markdown(cfg, p, responses, a, s, rep)
    _show_report(rep)
    console.print(f"\n[green]JSON:[/green]     {json_path}")
    console.print(f"[green]Markdown:[/green] {md_path}")


# ---------- run-all ----------

@app.command("run-all")
def run_all(
    config: Path = typer.Option(..., exists=True, readable=True),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip HITL confirmation gates."),
    max_workers: int = typer.Option(6),
):
    """Run all 6 steps end-to-end with confirmation gates between them."""
    cfg = _load(config)

    console.print("[bold cyan]→ Step 1/6 Persona...[/bold cyan]")
    p = build_persona(cfg)
    save_artifact(cfg.run_id, "persona", p)
    _show_persona(p)
    _gate(yes, "persona")

    console.print("[bold cyan]→ Step 2/6 Instrument...[/bold cyan]")
    inst = design_instrument(cfg, p)
    save_artifact(cfg.run_id, "instrument", inst)
    _show_instrument(inst)
    _gate(yes, "instrument")

    console.print(
        f"[bold cyan]→ Step 3/6 Panel ({len(p.archetypes)} respondents)...[/bold cyan]"
    )
    responses = run_panel(cfg, p, inst, max_workers=max_workers)
    save_artifact(
        cfg.run_id,
        "panel_responses",
        [r.model_dump(mode="json") for r in responses],
    )
    _show_panel_summary(responses)
    _gate(yes, "panel")

    console.print("[bold cyan]→ Step 4/6 Assessment...[/bold cyan]")
    a = assess_run(cfg, p, responses)
    save_artifact(cfg.run_id, "assessment", a)
    _show_assessment(a)
    _gate(yes, "assessment")

    console.print("[bold cyan]→ Step 5/6 Secondary synthesis...[/bold cyan]")
    s = synthesize_secondary(cfg, p, a)
    save_artifact(cfg.run_id, "secondary", s)
    _show_secondary(s)
    _gate(yes, "secondary")

    console.print("[bold cyan]→ Step 6/6 Triangulated report...[/bold cyan]")
    rep = build_report(cfg, p, responses, a, s)
    save_artifact(cfg.run_id, "report", rep)
    md_path = save_report_markdown(cfg, p, responses, a, s, rep)
    _show_report(rep)
    console.print(f"\n[green]Report (Markdown):[/green] {md_path}")
    console.print(f"[green]All artifacts in:[/green] {run_dir(cfg.run_id)}")


# ---------- show ----------

@app.command()
def show(
    config: Path = typer.Option(..., exists=True, readable=True),
    step: str = typer.Argument(
        ..., help="persona | instrument | panel | assessment | secondary | report"
    ),
):
    """Pretty-print a saved artifact without re-running it."""
    cfg = _load(config)
    if step == "persona":
        _show_persona(load_artifact(cfg.run_id, "persona", Persona))
    elif step == "instrument":
        _show_instrument(load_artifact(cfg.run_id, "instrument", Instrument))
    elif step == "panel":
        raw = load_artifact(cfg.run_id, "panel_responses")
        _show_panel_summary([PanelResponse.model_validate(r) for r in raw])
    elif step == "assessment":
        _show_assessment(load_artifact(cfg.run_id, "assessment", Assessment))
    elif step == "secondary":
        _show_secondary(load_artifact(cfg.run_id, "secondary", SecondarySynthesis))
    elif step == "report":
        _show_report(load_artifact(cfg.run_id, "report", TriangulatedReport))
    else:
        raise typer.BadParameter(
            "step must be persona|instrument|panel|assessment|secondary|report"
        )


# ---------- helpers ----------

def _gate(yes: bool, step: str) -> None:
    if yes:
        return
    ok = typer.confirm(f"Continue past the {step} checkpoint?", default=True)
    if not ok:
        console.print("[yellow]Stopped at checkpoint.[/yellow]")
        raise typer.Exit(0)


def _show_persona(p: Persona) -> None:
    console.print(RichPanel(p.market_summary, title="Market summary"))
    console.print(f"[bold]Target segment:[/bold] {p.target_segment}")
    console.print(f"[bold]Cultural dimensions:[/bold] {', '.join(p.key_cultural_dimensions)}")
    console.print(f"[bold]Design expectations:[/bold] {', '.join(p.design_expectations)}")
    t = Table(title=f"Archetype roster ({len(p.archetypes)})")
    for col in ("id", "name", "age", "gender", "region", "occupation", "tech"):
        t.add_column(col)
    for a in p.archetypes:
        t.add_row(
            a.archetype_id, a.name, a.age_band, a.gender,
            a.region, a.occupation, a.tech_comfort,
        )
    console.print(t)


def _show_instrument(inst: Instrument) -> None:
    console.print(RichPanel(inst.stimulus_description, title="Stimulus"))
    t = Table(title=f"Instrument items ({len(inst.items)})")
    t.add_column("id"); t.add_column("type"); t.add_column("question")
    for i in inst.items:
        t.add_row(i.item_id, i.response_type, i.question)
    console.print(t)
    console.print(f"[dim]Pass criteria echo: {inst.pass_criteria_echo}[/dim]")


def _show_panel_summary(responses: list[PanelResponse]) -> None:
    from collections import Counter
    counts = Counter(r.preference for r in responses)
    t = Table(title=f"Panel summary (n={len(responses)})")
    t.add_column("preference"); t.add_column("count"); t.add_column("share")
    for k in ("A", "B", "neither", "both_equal"):
        c = counts.get(k, 0)
        t.add_row(k, str(c), f"{(c / len(responses)):.0%}" if responses else "-")
    console.print(t)
    flags = sum(len(r.cultural_red_flags) for r in responses)
    console.print(f"[bold]Total cultural_red_flags raised:[/bold] {flags}")


def _show_assessment(a: Assessment) -> None:
    color = {"pass": "green", "fail": "red", "needs_revision": "yellow"}[a.verdict]
    console.print(
        RichPanel(
            f"[bold {color}]{a.verdict.upper()}[/bold {color}] — "
            f"preference_for_B = {a.preference_for_B:.0%}\n\n"
            f"{a.rationale}\n\n"
            f"[bold]Next step:[/bold] {a.recommended_next_step}",
            title="Primary Assessment",
        )
    )
    if a.cultural_red_flags:
        t = Table(title="Cultural red flags")
        t.add_column("flag")
        for f in a.cultural_red_flags:
            t.add_row(f)
        console.print(t)


def _show_secondary(s: SecondarySynthesis) -> None:
    console.print(RichPanel(s.market_context, title="Market context"))
    console.print(RichPanel(s.competitor_landscape, title="Competitor landscape"))
    console.print("[bold]Cultural trends:[/bold]")
    for t in s.cultural_trends:
        console.print(f"  • {t}")
    console.print("[bold]Design norms:[/bold]")
    for d in s.design_norms:
        console.print(f"  • {d}")
    console.print("[bold]Risks beyond the panel:[/bold]")
    for r in s.relevant_risks:
        console.print(f"  • {r}")
    tbl = Table(title=f"Citations ({len(s.citations)})")
    tbl.add_column("type"); tbl.add_column("conf"); tbl.add_column("claim")
    for c in s.citations:
        tbl.add_row(c.source_type, c.confidence, c.claim)
    console.print(tbl)
    console.print(f"[dim italic]Freshness caveat: {s.freshness_caveat}[/dim italic]")


def _show_report(r: TriangulatedReport) -> None:
    color = {"pass": "green", "fail": "red", "needs_revision": "yellow"}[
        r.headline_verdict
    ]
    conf_color = {"high": "green", "medium": "yellow", "low": "red"}[r.confidence]
    console.print(
        RichPanel(
            f"[bold {color}]{r.headline_verdict.upper()}[/bold {color}] · "
            f"confidence: [bold {conf_color}]{r.confidence}[/bold {conf_color}]\n\n"
            f"{r.executive_summary}",
            title="Triangulated Report",
        )
    )
    console.print("[bold]Recommended actions:[/bold]")
    for a in r.recommended_actions:
        console.print(f"  • {a}")
    if r.open_questions:
        console.print("[bold]Open questions:[/bold]")
        for q in r.open_questions:
            console.print(f"  • {q}")
    console.print(RichPanel(r.convergence_analysis, title="Convergence analysis"))


if __name__ == "__main__":
    app()
