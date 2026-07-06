Starting from nothing but public internet access, an agent can find, install, and prove that the Brev CLI runs on a clean Linux box.

The agent gets no hints about where Brev lives or how it is installed. This measures whether public docs and registries are findable enough.

You are working in a fresh Linux container with a shell.
Use only publicly available information — public docs, public repositories, public package registries. Do not assume access to internal wikis, support channels, or credentials beyond any provided in the environment.

When you are done, the following should be true:
- `brev --version` exits successfully
- `/app/notes/install-source.md` exists

Keep notes of what you tried in the files named above; the point is to show your working, not just the end state.
