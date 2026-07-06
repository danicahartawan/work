An agent preparing to use Brev in CI can determine from public docs how to authenticate without a browser or human present, or produce a precise statement that no such path is documented, with the pages it checked listed in /app/notes/auth-findings.md.

Agents run headless. If the only documented auth path requires an interactive browser, that is itself a readiness finding — this goal is expected to surface it either way.

You are working in a fresh Linux container with a shell.
Use only publicly available information — public docs, public repositories, public package registries. Do not assume access to internal wikis, support channels, or credentials beyond any provided in the environment.

When you are done, the following should be true:
- `/app/notes/auth-findings.md` exists and records your findings

Keep notes of what you tried in the files named above; the point is to show your working, not just the end state.
