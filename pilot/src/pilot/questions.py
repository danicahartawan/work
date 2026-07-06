"""Question bank: the prompts that help a team think past the 1==1 eval.

Each readiness dimension carries the questions a goal author should be able
to answer before the goal is worth compiling. `pilot questions` prints them,
`pilot init` seeds them as comments in the starter goals file.
"""

DIMENSIONS = ("discover", "understand", "execute", "recover")

QUESTION_BANK: dict[str, list[str]] = {
    "discover": [
        "Starting from zero context, what search terms would an agent plausibly use to find your product?",
        "Which page do you *want* an agent to land on first, and does it exist?",
        "Can install/setup instructions be found without leaving public pages (no login, no paywall, no internal wiki)?",
        "If your docs vanished, could the agent still find the product via its package registry / GitHub / marketplace listing?",
    ],
    "understand": [
        "Given the docs an agent will actually find, can it determine the *one* correct command/API call for a concrete outcome?",
        "Are required parameters and their formats stated explicitly, or only shown by example?",
        "Is there exactly one recommended way to do the thing, or do docs offer three conflicting ones?",
        "Can the agent tell what authentication is required *before* attempting the call, and how to do it non-interactively?",
    ],
    "execute": [
        "Can the whole flow run in a fresh, non-interactive shell (no browser pop-ups, no TTY prompts, no human in the loop)?",
        "Is there machine-readable output (JSON flag, exit codes) the agent can act on, or must it parse prose?",
        "What state does success leave behind that a script could verify?",
        "How long does the happy path take, and does anything block on human approval?",
    ],
    "recover": [
        "What is the most common failure a new user hits, and what does its error message actually say?",
        "Does the error message name the fix (or a doc URL), or just describe the symptom?",
        "If credentials are missing/expired, can the agent discover the remediation from the error alone?",
        "After a failed attempt, is retrying safe (idempotent), and would an agent know that?",
    ],
}
