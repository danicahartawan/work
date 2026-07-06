FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/notes

# TODO(team): inject the broken state this recover goal starts from:
#   No Brev credentials exist in the environment. The first stateful command the agent runs (e.g. listing instances) will fail with whatever error the CLI emits for an unauthenticated user.
# e.g. plant an expired credential file, remove a dependency, or
# point config at a dead endpoint. The agent must NOT be told.
