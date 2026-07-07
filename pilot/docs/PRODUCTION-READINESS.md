# Production-readiness — scoped to onboarding teams into Harbor

This checklist is deliberately narrow. It is **not** "make pilot a polished
product." It is only: *what has to be true for a team that has never used
Harbor to go from `pip install` to a reviewed, running readiness dataset
without a human from our side holding their hand.* Anything that doesn't
serve that first-hour onboarding job is out of scope here.

## Done in this change

- **`pilot wizard`** — the guided first run. Env check → product identity →
  read docs → read user sentiment → three suggested tasks spanning
  discover/understand/recover → lint. Works interactively or fully
  non-interactively (`--yes` + flags) so it runs in CI and in tests.
- **`pilot doctor`** — preflight. The #1 onboarding failure is a half-set-up
  environment (no Harbor, wrong Python), so we surface it up front with the
  exact fix command instead of letting `harbor run` fail cryptically later.
- **Suggestions are deterministic and offline.** No API key required to get
  value on day one; suggestions are reproducible, which is what makes an
  onboarding tool trustworthy. The analyzer seam (`analyze_docs`,
  `analyze_sentiment`) can be swapped for an LLM later without touching the
  wizard.
- **Fail-safe writes.** The wizard refuses to clobber an existing goals file
  without `--force`; generated `manual:` checks compile to *failing* tests so
  an unreviewed dataset can't silently pass.
- **Tests (11) covering the analyzer, the generated-goals-lint-clean
  invariant, the no-answer-leak invariant, and the wizard end-to-end.**

## The remaining edits to be truly production-ready for onboarding

Ranked by how directly they unblock a self-serve team.

1. **`pilot init --ci` — emit the CI wiring.** The onboarding promise is
   "evals live in your repo like unit tests and run in CI." Ship a generated
   GitHub Actions / GitLab CI job that runs `pilot lint` on every PR and
   `harbor run` on the compiled dataset on a schedule. Without this, teams
   author tasks and then never wire the gate, which is the whole point.
2. **Real docs ingestion.** Today the wizard reads a local file or a single
   URL. Onboarding teams have a docs *site*. Add: crawl a docs base URL
   (depth-limited), read a local docs directory, and pull a GitHub repo's
   `README`/`docs/`. Behind the existing `analyze_docs` signature.
3. **Real sentiment connectors.** Replace "point me at a text file" with
   first-class readers for GitHub Issues, Discourse/forums, and Zendesk/
   support exports — that's where the "sentiment" actually lives (Danica's
   seeding idea). Keep the file reader as the offline fallback.
4. **Promote `manual:` to Harbor rubric verifiers.** Right now manual
   evidence is an honest dead-end (a failing TODO). For onboarding, compile
   it into a Harbor LLM-judge/rubric check so a team ends the first session
   with a *runnable* grader, not homework. Delegate QA to `harbor check`.
5. **Version-pin the compile target to Harbor's schema.** We emit
   `schema_version = "1.3"`. Add a golden test that re-validates the sample
   dataset against the installed Harbor models, and a CI matrix across Harbor
   versions, so a Harbor bump can't silently break every team's compile.
6. **Packaging + distribution.** Publish to an internal index so onboarding is
   `uv tool install pilot`, not a git clone. Pin `harbor` compatibly. Add
   `pilot --version` to the doctor output for support triage.
7. **Telemetry-free by default, opt-in metrics.** For a central team to know
   onboarding is working they'll want funnel data (wizard started → dataset
   compiled → CI wired). Make it explicit opt-in; never phone home silently.
8. **Docs: a 10-minute onboarding quickstart** that is *only* the wizard path,
   plus a troubleshooting page for the environments teams actually hit
   (corporate proxy blocking the installer — the exact Brev finding — belongs
   here as a worked example).

## Explicitly out of scope for onboarding

Multi-tenant registries, a hosted UI, cross-product leaderboards, and
non-Harbor eval backends. They matter for the broader program, but none of
them is on the path of a single team's first successful dataset — folding
them in here would bloat the thing we're asking teams to adopt.
