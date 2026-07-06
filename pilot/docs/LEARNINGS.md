# Learnings: testing the pilot workflow against Harbor + Brev

*Danica — follow-up to Carter's "want to try it out for brev too and document
learnings?" and the thread on whether Harbor scaffolding alone is enough.*

**What was tested:** Harbor 0.17.1's out-of-box authoring flow (`harbor init`,
`harbor check`, `harbor run`, dataset manifests), and the pilot workflow
end-to-end — six plain-language readiness goals for NVIDIA Brev, written from
public info only, compiled to a Harbor dataset and validated against Harbor's
own task schema. The compiled dataset is committed at
[`examples/brev/harbor/`](../examples/brev/). Caveat: the sandbox used had no
Docker and its proxy blocked harborframework.com and docs.nvidia.com, so
tasks were schema-validated and their verifiers executed with pytest locally,
but not yet run under `harbor run` with a real agent. That run is the obvious
next step on a normal dev box.

## 1. Harbor already ships more starter DX than the thread assumed

The Slack discussion treated "scaffolding the Harbor format" as the thing to
build. Harbor 0.17 already has it, and more:

- `harbor init --task` / `--dataset` — full scaffold (task.toml schema 1.3,
  instruction.md, Dockerfile, pytest verifier harness, solution stub,
  auto-maintained dataset.toml).
- `harbor check` — an *agent-driven rubric QA* of a task directory
  (configurable rubric, runs in Docker/Daytona/etc.). This is the "check
  their validity" piece Carter flagged as missing from the skill doc.
- `harbor exec` — experimental "compile paths into tasks and run a job".
- Path-based dataset manifests — `[[tasks]] path = "..."` with digests
  auto-computed, so datasets can live in a product repo like unit tests
  (the PRD's model) with no registry involved.

**Implication for the PRD:** pilot should not rebuild scaffolding or QA. Its
compile target should be byte-compatible with `harbor init` output (the
prototype's is), and `pilot check` should delegate to `harbor check` rather
than grow its own rubric runner.

## 2. But the scaffold is content-empty — Nikhil's gap is real

`harbor init` produces an *empty* instruction.md and a verifier that is
literally `def test_outputs(): pass` — a task that always passes. Nothing in
the format forces you to decide what "agent-ready" means. That's exactly how
the one-shot skill produced the openShell evals Carter called "kind of
useless": structurally valid tasks that check whether an agent can write
config files, not whether it can operate the product.

The fix that worked in practice wasn't more generation — it was **refusal**.
The prototype's lint blocks compilation of goals with no observable evidence
and recover-goals with nothing broken, and warns on step-by-step outcomes,
manual-only evidence, missing readiness dimensions (discover / understand /
execute / recover), and datasets with no public-info-only goal. Re-creating
the openShell failure mode as a goals file trips 2 errors and 5 warnings.
That's the mechanical version of "help people think through the questions."

## 3. Writing the goals file is itself the readiness audit

The most surprising result: **before any eval ran**, authoring six Brev goals
from public info surfaced real findings:

- Brev's public GitHub README documents install and `brev login`, but not
  non-interactive/CI auth and not what an unauthenticated command returns —
  the two things a headless agent needs most. (The full docs live at
  docs.nvidia.com/brev, which notably has a "Using the CLI with AI Agents"
  page — good sign, but the split means an agent landing on GitHub gets an
  incomplete picture.)
- The `--gpu machine-type:gpu-type:count` flag format is discoverable but
  shown mostly by example, which is the pattern agents mis-generalize from.

So the "understand-noninteractive-auth" goal is written to pass even if the
answer is "not documented" — a readiness eval whose *expected output is a
docs gap report*. This pattern (goal as audit probe) probably deserves its
own user story in the PRD.

## 4. Compilation exposed an eval-design failure mode worth designing for

First compile leaked verifier answers into instructions: the recover task
told the agent the fix was `brev login`, and the understand task named the
`--gpu` flag it was supposed to *find*. Grading became copying. The
prototype now (a) never renders `file_contains` search strings or `manual`
grading criteria into instruction.md, and (b) lints for verifier strings
appearing in agent-visible text (W206). Any tool in this space — CLI, skill,
or human review checklist — needs this rule; it's invisible until you look
at generated instruction + verifier side by side.

Second, deterministic-vs-rubric: a tiny evidence DSL (`cmd_ok`,
`file_exists`, `file_contains`, `manual`) covered all six Brev goals.
`manual` compiles to a **failing** pytest stamped `TODO(team)`, so an
unreviewed verifier cannot silently pass and `pilot check` can report
verifier debt (18 TODOs across the Brev set). This keeps eval ownership with
the team — "empower, don't write it for them" — while still giving them a
runnable dataset on day one.

## 5. So: is a CLI the optimal shape?

Mostly yes, with a caveat that supports Carter's instinct too:

- **The CLI is the contract.** Lint, compile, and check must produce the
  same result in CI as on a laptop, gate merges with exit codes, and be
  reviewable as diffs. A "copy prompt" button or skill can't be a CI gate.
- **A skill is the right front door.** The conversational part — eliciting
  goals from docs/blueprints/GitHub issues/support threads, suggesting
  starter tasks (the seeding idea from the thread) — is agent work, and a
  skill that *drives the pilot CLI* gets both: Claude/Codex handles the
  thinking-partner UX, the CLI enforces the invariants. They're layers, not
  alternatives.
- The deterministic core needed no LLM at all. Everything LLM-shaped
  (goal elicitation, turning `manual` evidence into rubric checks, fix-PR
  generation) composes on top or delegates to `harbor check`.

## 6. Concrete suggestions for the PRD

1. Compile target = `harbor init` byte-compatibility; QA = delegate to
   `harbor check`; run = plain `harbor run -p "dir/*"`. Zero custom infra.
2. Add "goal lint" as a first-class requirement (the no-evidence /
   answer-leak / dimension-coverage rules above), not just generation.
3. Stamp `[metadata] readiness_dimension` + `public_info_only` on every
   task — that's what makes the central-team, cross-product comparison
   use case a groupby instead of a project.
4. Make `manual` evidence fail-closed. It's the single biggest difference
   between this and the one-shot skill output.
5. Add the "expected finding is a docs gap" goal pattern as a user story.
6. Ship a companion skill that drives the CLI for goal elicitation and
   starter-task suggestion from existing sources.

## Repro

```bash
cd pilot && uv venv -p 3.13 && uv pip install -e ".[harbor]" -p .venv/bin/python
.venv/bin/pilot lint examples/brev/goals.yaml
.venv/bin/pilot compile examples/brev/goals.yaml -o examples/brev/harbor
.venv/bin/pilot check examples/brev/harbor        # validates with Harbor's models
harbor run -p "examples/brev/harbor/*" -a claude-code -m <model>   # needs Docker
```
