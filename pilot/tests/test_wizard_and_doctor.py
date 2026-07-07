from pathlib import Path

from typer.testing import CliRunner

from pilot.cli import app
from pilot.doctor import run_checks, summarize

runner = CliRunner()

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "examples/brev/inputs/docs-excerpt.md"
SENT = REPO / "examples/brev/inputs/sentiment.txt"


def test_doctor_reports_python_check():
    checks = run_checks()
    names = {c.name for c in checks}
    assert "python >= 3.12" in names
    # python check is required and should pass under our own interpreter
    py = next(c for c in checks if c.name == "python >= 3.12")
    assert py.ok and py.level == "required"


def test_doctor_command_exits_zero_on_ready_env():
    result = runner.invoke(app, ["doctor"])
    # python passes; harbor may or may not be present, but python alone
    # shouldn't block. Required failures would exit 1.
    blocking, _ = summarize(run_checks())
    assert result.exit_code == (1 if blocking else 0)


def test_wizard_end_to_end_non_interactive(tmp_path: Path):
    out = tmp_path / "goals.yaml"
    result = runner.invoke(app, [
        "wizard", "--name", "nvidia-brev", "--org", "nvidia",
        "--docs", str(DOCS), "--sentiment", str(SENT),
        "-o", str(out), "--yes",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    text = out.read_text()
    assert "discover-install" in text
    assert "recover-" in text
    # the top documented action drove the understand task
    assert "understand-" in text


def test_wizard_refuses_to_clobber_without_force(tmp_path: Path):
    out = tmp_path / "goals.yaml"
    out.write_text("existing")
    result = runner.invoke(app, [
        "wizard", "--name", "x", "--docs", str(DOCS), "-o", str(out), "--yes",
    ])
    assert result.exit_code == 1
    assert out.read_text() == "existing"
