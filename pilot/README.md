# pilot — agent-readiness evals for your product

**pilot answers one question: can an AI agent discover, understand, execute
against, and recover from errors when using our product?**

You write readiness *goals* in plain product language — outcomes, not
click-by-click steps. pilot compiles them into runnable
[Harbor](https://www.harborframework.com) eval tasks that live in your repo
like unit tests and run in CI.

pilot does **not** write your evals for you. It makes you answer the right
questions, refuses to compile goals that can't fail meaningfully, and turns
every judgment you haven't made yet into a failing test you can't ignore.

## Quickstart

```bash
uv pip install -e "pilot[harbor]"      # harbor extra needs Python 3.12+

pilot init my-product                  # starter goals.yaml + guidance
pilot questions discover               # what a discover goal should answer
pilot lint goals.yaml                  # catch the traps before compiling
pilot compile goals.yaml -o harbor     # goals -> Harbor task dirs
pilot check harbor                     # validate with Harbor's own schema
harbor run -p "harbor/*" -a claude-code -m <model>
```

A complete worked example against NVIDIA Brev is in
[`examples/brev/`](examples/brev/) — `goals.yaml` plus the compiled dataset.

## The goal file

```yaml
product:
  name: nvidia-brev
  org: nvidia
  docs: [https://docs.nvidia.com/brev/]

goals:
  - id: recover-unauthenticated-error
    dimension: recover            # discover | understand | execute | recover
    failure_injection: >          # required for recover goals
      No credentials exist; the first stateful command fails.
    outcome: >                    # plain language, states the END STATE
      When a Brev command fails for lack of authentication, an agent can
      diagnose the failure from the error output alone and write a recovery
      plan that names the documented remediation.
    evidence:                     # observable success criteria
      - file_exists: /app/notes/recovery.md
      - file_contains: {path: /app/notes/recovery.md, text: "brev login"}
      - manual: recovery plan quotes the actual error message observed
```

### Evidence kinds

| kind            | compiles to                                   |
| --------------- | --------------------------------------------- |
| `cmd_ok`        | pytest asserting the command exits 0          |
| `file_exists`   | pytest asserting the artifact exists          |
| `file_contains` | pytest asserting the artifact mentions text   |
| `manual`        | a **failing** pytest marked `TODO(team)`      |

`manual` evidence fails on purpose. A verifier nobody reviewed must not be
able to pass — replace the TODO with a real assertion (or a rubric check)
before trusting results. `pilot check` reports how many TODOs remain.

### What lint refuses

- goals with no evidence (nothing observable = not an eval)
- `recover` goals with no `failure_injection` (nothing breaks = nothing to recover from)
- and it warns on: step-by-step outcomes, manual-only evidence, datasets
  that skip a readiness dimension, and specs with no `public_info_only`
  goal (needed to compare products on public-info readiness).

These rules are the mechanical version of the review a good eval author
gives a first draft — they exist so the compiled dataset is never the
`assert 1 == 1` eval that one-shot scaffolding tends to produce.

## What compilation produces

One Harbor task directory per goal, matching `harbor init --task` scaffolding
(schema 1.3), plus a path-based `dataset.toml`:

```
harbor/
├── dataset.toml
└── nvidia-brev-recover-unauthenticated-error/
    ├── task.toml            # [metadata] readiness_dimension, public_info_only
    ├── instruction.md       # the outcome, verbatim — never steps
    ├── environment/Dockerfile
    ├── tests/test.sh        # Harbor reward.txt convention
    ├── tests/test_outputs.py
    └── solution/solve.sh    # TODO(team): write it — fastest docs audit there is
```

The `[metadata]` block stamps each task with its readiness dimension so a
central team can aggregate scores per dimension across products.

## Division of labor with Harbor

Harbor already ships `harbor init` (scaffold), `harbor check` (agent-driven
rubric QA), and `harbor run`. pilot deliberately does not rebuild any of
that. pilot owns the layer before Harbor: deciding *what to measure*
(dimensions + question bank), keeping goals honest (lint), and compiling
them into Harbor's format. After `pilot compile`, everything downstream is
plain Harbor.
