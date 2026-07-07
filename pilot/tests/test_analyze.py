from pathlib import Path

from pilot.analyze import (
    analyze_docs,
    analyze_sentiment,
    drafts_to_goals_yaml,
    load_sentiment,
    suggest_tasks,
)
from pilot.model import lint, load_spec

DOCS = """
# Foo CLI
Install:
```bash
curl -fsSL https://example.com/install.sh | bash
```
Usage:
```bash
foo login
foo deploy my-app
foo deploy other-app
foo status
```
"""

SENTIMENT = [
    "foo login hangs forever behind my proxy",
    "install script fails with 403, can't install foo",
    "getting forbidden on foo status, unclear what auth it needs",
    "love it once it works but setup was confusing",
]


def test_detects_install_and_infers_binary_from_examples():
    sig = analyze_docs(DOCS, product_slug="foo-cli")
    assert sig.install_kind == "curl-installer"
    # binary can't come from a curl installer; inferred from usage examples
    assert sig.binary == "foo"
    assert "deploy" in sig.actions  # most frequent subcommand
    assert sig.actions[0] == "deploy"


def test_pip_install_binary_from_package():
    sig = analyze_docs("run `pip install harbor` then go", product_slug="harbor")
    assert sig.install_kind == "pip"
    assert sig.binary == "harbor"


def test_sentiment_clusters_and_ranks():
    pains = analyze_sentiment(SENTIMENT)
    assert pains, "expected at least one pain point"
    themes = {p.theme for p in pains}
    assert "auth/access" in themes
    # negative phrasing is weighted, so auth/access should rank at or near top
    assert pains[0].count >= 2


def test_load_sentiment_formats(tmp_path: Path):
    txt = tmp_path / "s.txt"
    txt.write_text("# comment\nline one\nline two\n")
    assert load_sentiment(txt) == ["line one", "line two"]

    js = tmp_path / "s.json"
    js.write_text('[{"title": "a"}, "b"]')
    assert load_sentiment(js) == ["a", "b"]


def test_suggest_tasks_spans_dimensions_and_lints_clean(tmp_path: Path):
    sig = analyze_docs(DOCS, "foo-cli")
    pains = analyze_sentiment(SENTIMENT)
    drafts = suggest_tasks("foo", sig, pains)

    assert [d.dimension for d in drafts] == ["discover", "understand", "recover"]
    # recover goal must carry an injected failure or lint E104 fires
    assert drafts[2].failure_injection

    yaml_text = drafts_to_goals_yaml("foo", "acme", sig, drafts)
    goals_file = tmp_path / "goals.yaml"
    goals_file.write_text(yaml_text)

    spec = load_spec(goals_file)
    errors = [f for f in lint(spec) if f.level == "error"]
    assert not errors, f"generated goals should have no lint errors: {errors}"


def test_no_sentiment_still_produces_valid_recover(tmp_path: Path):
    sig = analyze_docs(DOCS, "foo-cli")
    drafts = suggest_tasks("foo", sig, pains=[])
    assert drafts[2].dimension == "recover"
    assert drafts[2].failure_injection  # generic but present, so lint passes

    goals_file = tmp_path / "g.yaml"
    goals_file.write_text(drafts_to_goals_yaml("foo", "acme", sig, drafts))
    spec = load_spec(goals_file)
    assert not [f for f in lint(spec) if f.level == "error"]


def test_no_answer_leak_in_generated_outcomes():
    """file_contains/manual criteria must not leak into agent-visible outcome."""
    sig = analyze_docs(DOCS, "foo-cli")
    drafts = suggest_tasks("foo", sig, analyze_sentiment(SENTIMENT))
    for d in drafts:
        for ev in d.evidence:
            if "file_contains" in ev:
                assert ev["file_contains"]["text"].lower() not in d.outcome.lower()
