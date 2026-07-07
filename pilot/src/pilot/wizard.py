"""`pilot wizard` — a team's first ten minutes with pilot.

Walks a first-time user from a clean install to a lint-clean goals.yaml with
three suggested tasks drawn from their own docs and user sentiment. Runs
interactively, or fully non-interactively (flags + --yes) so it also works in
CI and is testable.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from pilot.analyze import (
    GoalDraft,
    analyze_docs,
    analyze_sentiment,
    drafts_to_goals_yaml,
    load_sentiment,
    suggest_tasks,
)
from pilot.doctor import run_checks, summarize
from pilot.model import lint, load_spec

console = Console()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _read_source(source: str) -> tuple[str, str]:
    """Return (text, label) for a local path or a URL. Network is best-effort:
    if it's blocked (a common onboarding reality), say so and continue."""
    p = Path(source)
    if p.exists():
        return p.read_text(errors="replace"), str(p)
    if source.startswith(("http://", "https://")):
        try:
            import urllib.request

            with urllib.request.urlopen(source, timeout=20) as r:  # noqa: S310
                return r.read().decode("utf-8", "replace"), source
        except Exception as e:
            console.print(
                f"[yellow]Couldn't fetch {source} ({e.__class__.__name__}). "
                "Save the page to a local file and pass that instead.[/yellow]"
            )
            return "", source
    console.print(f"[yellow]No file at {source}; skipping.[/yellow]")
    return "", source


def _print_doctor() -> int:
    console.print("[bold]Step 1 — environment check[/bold]")
    checks = run_checks()
    for c in checks:
        mark = "[green]✓[/green]" if c.ok else ("[red]✗[/red]" if c.level == "required" else "[yellow]•[/yellow]")
        console.print(f"  {mark} {c.name}: {c.detail}")
        if not c.ok and c.fix:
            console.print(f"      [dim]{c.fix}[/dim]")
    blocking, _ = summarize(checks)
    console.print()
    return blocking


def _preview(draft: GoalDraft) -> Panel:
    lines = [
        f"[bold]{draft.id}[/bold]  [dim]({draft.dimension})[/dim]",
        f"{draft.outcome.strip()}",
        f"[dim]why: {draft.rationale}[/dim]",
    ]
    return Panel("\n".join(lines), border_style="cyan")


def wizard(
    name: str = typer.Option("", "--name", help="Product name (prompted if omitted)"),
    docs: list[str] = typer.Option(None, "--docs", help="Doc file path or URL (repeatable)"),
    sentiment: str = typer.Option("", "--sentiment", help="Sentiment file: issue titles / posts, one per line or JSON"),
    org: str = typer.Option("local", "--org"),
    output: Path = typer.Option(Path("goals.yaml"), "--output", "-o"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept all suggestions, no prompts (CI)"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing goals file"),
) -> None:
    """Interactive first-run: check env, read docs + sentiment, suggest 3 tasks."""
    console.print(Panel.fit(
        "[bold]pilot wizard[/bold] — from clean install to three readiness tasks",
        border_style="magenta",
    ))

    blocking = _print_doctor()
    if blocking:
        console.print(f"[red]{blocking} required check(s) failed. Fix these first.[/red]")
        if not yes and not typer.confirm("Continue anyway?", default=False):
            raise typer.Exit(1)

    # Step 2 — product identity
    if not name:
        name = typer.prompt("Step 2 — product name (e.g. nvidia-brev)")
    console.print(f"[bold]Product:[/bold] {name}\n")

    # Step 3 — docs
    console.print("[bold]Step 3 — read the docs[/bold]")
    doc_sources = list(docs or [])
    if not doc_sources and not yes:
        first = typer.prompt("  Docs file path or URL (blank to skip)", default="")
        if first:
            doc_sources.append(first)
    doc_text, labels = "", []
    for s in doc_sources:
        t, label = _read_source(s)
        doc_text += "\n" + t
        if t:
            labels.append(label)
    doc_signals = analyze_docs(doc_text, _slug(name))
    doc_signals.sources = labels
    if doc_signals.install_command:
        console.print(f"  detected install: [green]{doc_signals.install_command}[/green]")
    if doc_signals.actions:
        console.print(f"  common actions: {', '.join(doc_signals.actions)}")
    if not doc_text:
        console.print("  [yellow]no docs read — suggestions will be generic[/yellow]")
    console.print()

    # Step 4 — sentiment
    console.print("[bold]Step 4 — read user sentiment[/bold]")
    if not sentiment and not yes:
        sentiment = typer.prompt(
            "  Sentiment file (GitHub issue titles, forum/reddit posts; blank to skip)",
            default="",
        )
    pains = []
    if sentiment:
        sp = Path(sentiment)
        if sp.exists():
            items = load_sentiment(sp)
            pains = analyze_sentiment(items)
            console.print(f"  read {len(items)} items; top themes: "
                          + (", ".join(f"{p.theme}({p.count})" for p in pains[:3]) or "none"))
        else:
            console.print(f"  [yellow]no file at {sentiment}; skipping[/yellow]")
    else:
        console.print("  [dim]skipped — recover task will be seeded generically[/dim]")
    console.print()

    # Step 5 — suggest & confirm
    console.print("[bold]Step 5 — three suggested tasks[/bold]")
    drafts = suggest_tasks(name, doc_signals, pains)
    kept: list[GoalDraft] = []
    for d in drafts:
        console.print(_preview(d))
        if yes or typer.confirm(f"  keep '{d.id}'?", default=True):
            kept.append(d)
    if not kept:
        console.print("[red]No tasks kept — nothing to write.[/red]")
        raise typer.Exit(1)

    # Step 6 — write + lint
    if output.exists() and not force:
        console.print(f"[red]{output} exists. Re-run with --force to overwrite.[/red]")
        raise typer.Exit(1)
    output.write_text(drafts_to_goals_yaml(name, org, doc_signals, kept))
    console.print(f"\n[green]Wrote {output}[/green] with {len(kept)} task(s).")

    spec = load_spec(output)
    findings = lint(spec)
    errors = sum(f.level == "error" for f in findings)
    for f in findings:
        color = "red" if f.level == "error" else "yellow"
        console.print(f"  [{color}]{f.level}[/{color}] {f.code} {f.where}: {f.message}")
    console.print(
        f"\nNext: edit the [bold]manual:[/bold] checks in {output}, then "
        f"`pilot lint {output}` and `pilot compile {output}`."
        if not errors else
        f"\n[yellow]Resolve the {errors} error(s) above, then `pilot lint {output}`.[/yellow]"
    )
