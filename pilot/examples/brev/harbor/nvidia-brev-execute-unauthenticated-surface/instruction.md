An agent can install the Brev CLI and exercise everything that works without an account — help output, version, command discovery — and produce a machine-readable inventory at /app/notes/cli-surface.json of which commands responded and which demanded authentication.

Measures the scriptability of the CLI's unauthenticated surface: exit codes, non-interactive behavior, whether it hangs waiting for a TTY.

You are working in a fresh Linux container with a shell.
Use only publicly available information — public docs, public repositories, public package registries. Do not assume access to internal wikis, support channels, or credentials beyond any provided in the environment.

When you are done, the following should be true:
- `brev --help` exits successfully
- `/app/notes/cli-surface.json` exists
- `python3 -c "import json; json.load(open('/app/notes/cli-surface.json'))"` exits successfully

Keep notes of what you tried in the files named above; the point is to show your working, not just the end state.
