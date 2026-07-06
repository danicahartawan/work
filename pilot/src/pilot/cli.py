"""pilot CLI: init, questions, lint, compile, check."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pilot import __version__
from pilot.compiler import compile_spec, count_todos
from pilot.model import Finding, SpecError, lint, load_spec
from pilot.questions import DIMENSIONS, QUESTION_BANK

app = typer.Typer(
    help=(
        "Measure agent-readiness: write goals in plain product language, "
        "compile them into runnable Harbor eval tasks."
    ),
    no_args_is_help=True,
)
console = Console()

_STARTER = """\
# Agent-readiness goals for {name}.
#
# Write outcomes, not steps. Each goal answers one question about whether an
# AI agent can operate this product: can it DISCOVER it, UNDERSTAND it,
# EXECUTE against it, and RECOVER when things break?
#
# Evidence kinds:
#   - cmd_ok: "<command>"                         command must exit 0
#   - file_exists: /app/notes/<file>.md           artifact must exist
#   - file_contains: {{path: ..., text: ...}}       artifact must mention text
#   - manual: "<what a human must judge>"         compiles to a FAILING test
#                                                 until you replace it
#
# Run `pilot questions <dimension>` for the questions each goal should answer.

product:
  name: {name}
  summary: ""
  org: local
  docs: []

goals:
  - id: discover-install
    dimension: discover
    public_info_only: true
    outcome: >
      Starting from nothing but public internet access, an agent can find,
      install, and prove that {name} runs.
    evidence:
      - manual: "replace with the real success criteria for {name}"
"""


def _print_findings(findings: list[Finding]) -> int:
    errors = 0
    for f in findings:
        color = "red" if f.level == "error" else "yellow"
        console.print(f"[{color}]{f.level:7}[/{color}] {f.code} {f.where}: {f.message}")
        errors += f.level == "error"
    return errors


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"pilot {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=_version_callback, is_eager=True
    ),
) -> None:
    pass


@app.command()
def init(
    name: str = typer.Argument(help="Product name, e.g. nvidia-brev"),
    output: Path = typer.Option(Path("goals.yaml"), "--output", "-o"),
) -> None:
    """Write a starter goals file for a product."""
    if output.exists():
        console.print(f"[red]{output} already exists — not overwriting.[/red]")
        raise typer.Exit(1)
    output.write_text(_STARTER.format(name=name))
    console.print(f"Wrote {output}. Next: edit the goals, then `pilot lint {output}`.")


@app.command()
def questions(
    dimension: str = typer.Argument("", help=f"One of: {', '.join(DIMENSIONS)}"),
) -> None:
    """Print the questions a readiness goal should be able to answer."""
    dims = [dimension] if dimension else list(DIMENSIONS)
    for dim in dims:
        if dim not in QUESTION_BANK:
            console.print(f"[red]unknown dimension {dim!r}[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]{dim}[/bold]")
        for q in QUESTION_BANK[dim]:
            console.print(f"  • {q}")
        console.print()


@app.command("lint")
def lint_cmd(
    goals: Path = typer.Argument(..., metavar="GOALS", help="Path to goals.yaml"),
) -> None:
    """Lint a goals file for the traps that make evals useless."""
    _lint_or_exit(goals)


def _lint_or_exit(goals_path: Path):
    try:
        spec = load_spec(goals_path)
    except (SpecError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)
    findings = lint(spec)
    errors = _print_findings(findings)
    if errors:
        console.print(f"[red]{errors} error(s) — fix before compiling.[/red]")
        raise typer.Exit(1)
    if not findings:
        console.print("[green]goals look sound.[/green]")
    return spec


@app.command()
def compile(
    goals: Path = typer.Argument(..., metavar="GOALS", help="Path to goals.yaml"),
    out: Path = typer.Option(Path("harbor"), "--out", "-o", help="Output dataset dir"),
) -> None:
    """Compile goals into a Harbor dataset (lints first)."""
    spec = _lint_or_exit(goals)
    task_dirs = compile_spec(spec, out)

    table = Table(title=f"{spec.product.name} → {out}/")
    table.add_column("task")
    table.add_column("dimension")
    table.add_column("open TODOs", justify="right")
    for goal, task_dir in zip(spec.goals, task_dirs):
        table.add_row(task_dir.name, goal.dimension, str(count_todos(task_dir)))
    console.print(table)
    console.print(
        f"\nNext:\n"
        f"  pilot check {out}\n"
        f'  harbor run -p "{out}/*" -a claude-code -m <model>'
    )


@app.command()
def check(
    dataset: Path = typer.Argument(..., help="Compiled dataset directory"),
) -> None:
    """Validate compiled tasks (with Harbor's own models when installed)."""
    task_dirs = sorted(
        p for p in dataset.iterdir() if p.is_dir() and (p / "task.toml").exists()
    )
    if not task_dirs:
        console.print(f"[red]no task directories under {dataset}[/red]")
        raise typer.Exit(1)

    try:
        from harbor.models.task.task import Task  # type: ignore

        def validate(task_dir: Path) -> str:
            Task(task_dir)
            return "harbor schema ok"
    except ImportError:

        def validate(task_dir: Path) -> str:
            required = ["task.toml", "instruction.md", "environment/Dockerfile",
                        "tests/test.sh", "tests/test_outputs.py"]
            missing = [f for f in required if not (task_dir / f).exists()]
            if missing:
                raise ValueError(f"missing: {', '.join(missing)}")
            return "structure ok (install pilot[harbor] for full schema check)"

    failures = 0
    total_todos = 0
    for task_dir in task_dirs:
        todos = count_todos(task_dir)
        total_todos += todos
        try:
            status = validate(task_dir)
            note = f", {todos} TODO(team) left" if todos else ""
            console.print(f"[green]✓[/green] {task_dir.name}: {status}{note}")
        except Exception as e:  # harbor raises pydantic/os errors
            failures += 1
            console.print(f"[red]✗[/red] {task_dir.name}: {e}")

    if failures:
        raise typer.Exit(1)
    if total_todos:
        console.print(
            f"\n[yellow]{total_todos} TODO(team) marker(s) remain — manual "
            "evidence fails until replaced with real checks.[/yellow]"
        )


if __name__ == "__main__":
    app()
