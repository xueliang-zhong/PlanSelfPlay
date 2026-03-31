# Skill: Document Writing

Use this skill when the goal involves writing or updating documentation
(README, guides, API docs, inline comments, changelogs).

## Core principles

- **Lead with the job** — state what the thing does before explaining how.
- **Shortest accurate description wins** — if a sentence can be cut without losing meaning, cut it.
- **Concrete over abstract** — every abstract claim needs a concrete example, or cut it.
- **User's next action** — every section should leave the reader knowing what to do next.

## Structure for reference docs

1. One-line summary (what it is)
2. Quick start (minimal working example, copy-paste ready)
3. Options / API (exhaustive, scannable table or list)
4. Concepts (only if the mental model is non-obvious)
5. Examples (real-world, runnable)

## Common mistakes to avoid

- Over-explaining things self-evident from code or command names.
- Mixing user-facing docs with internal implementation details.
- Future tense ("will return") — use present tense ("returns").
- Passive voice when active is clearer: "the flag disables X", not "X is disabled by the flag".
- Stale examples — if you update behaviour, update the example in the same commit.
