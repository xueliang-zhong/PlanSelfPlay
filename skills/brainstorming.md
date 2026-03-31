# Skill: Brainstorming

Use this skill when the goal involves open-ended design, choosing between approaches,
or when the best path is unclear.

## Process

1. **Diverge first** — generate at least 3 distinct approaches without evaluating them yet.
2. **Annotate each** — for every approach note: expected outcome, main risk, reversibility.
3. **Converge** — pick the approach with the best risk/reward ratio given current constraints.
4. **Checkpoint** — in one sentence, state why you rejected the alternatives.

## Rules

- Never stop at the first idea that seems to work.
- Include at least one "unconventional" option (e.g., delete instead of fix, simplify instead of add).
- If stuck between two options, prototype the cheaper one first.
- Record firmly rejected paths in FAILED_PATHS.md so future runs don't revisit them.

## When branching is expensive

Commit the current state before trying a speculative approach so `git reset` can
recover cleanly if the branch fails.
