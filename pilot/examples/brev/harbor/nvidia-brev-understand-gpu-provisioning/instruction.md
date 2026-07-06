From public documentation alone, an agent can determine the exact CLI command that provisions an instance with a specific GPU type, including the flag format for choosing the GPU, and write that command with a short justification to /app/notes/provision-command.md.

Brev's GPU selection uses a structured flag value; this measures whether the parameter format is documented explicitly enough for an agent to construct (not copy) a correct command.

You are working in a fresh Linux container with a shell.
Use only publicly available information — public docs, public repositories, public package registries. Do not assume access to internal wikis, support channels, or credentials beyond any provided in the environment.

When you are done, the following should be true:
- `/app/notes/provision-command.md` exists and records your findings

Keep notes of what you tried in the files named above; the point is to show your working, not just the end state.
