# agent_population_flag_memory.md
UTC timestamp: 2026-03-30T00:00:00Z
Topic: --population / -j parallel agents per generation

---

## What was built

Added `--population N` (long form) and `-jN` / `-j N` (make-style short form) to `planselfplay.sh`, defaulting to 1. Each generation now spawns N background bash jobs and waits for all to complete before sleeping and advancing to the next generation.

Commits in this session (newest first):

| Hash | Change |
|------|--------|
| `67bbd60` | add --population/-j, rename die→quit, fix set -e sleep edge case |
| `e08034d` | docs: rewrite Tips section |
| `94ab0f9` | improve --goal temp file: unique name per run |
| `9cfcf67` | fix --goal: replace GOAL: line instead of prepending |
| `813f2a7` | add --goal flag (initial, prepend approach) |

---

## Design decisions

**Parallel model:** background jobs with `&` + PID array + `wait $pid` per member. Pure bash, no external dependencies, consistent with the script's "small control surface" philosophy.

**Rethink applied:** First considered a named helper function for the inner loop. Settled on inline `for member` loop — simpler, nothing to name or hunt down.

**Log line:** Always prints `[member/population]` including `[1/1]` for the default case. Rejected conditional label because one code path is cleaner than branching just to hide `[1/1]`.

**`-jN` parsing:** Two cases in the `case` block — `-j)` for `-j 4` (space-separated) and `-j*)` for `-jN` (attached). Order matters: exact match first.

---

## Bugs found and fixed during implementation

**`(( )) && sleep` under `set -e`:** The original pattern `(( generation < generations )) && sleep "$sleep_seconds"` exits with code 1 on the last generation (arithmetic false → `&&` short-circuits → expression exit 1). With `set -e` this could abort the script. Fixed to `if (( generation < generations )); then sleep ...; fi`.

**macOS `mktemp` suffix:** `mktemp "name.XXXXXX.txt"` on macOS does not replace the X's when a suffix follows them. Fixed by dropping the `.txt` extension: `mktemp "name.tmp.XXXXXX"`.

---

## Known limitation (planned work)

`-j N > 1` with agents that write to the repo will race on the same working tree — corrupted edits and broken commits are likely. The fix is **git worktree isolation**: create one branch+worktree per population member, run the agent there, then merge or cherry-pick the best result back to the main branch. This is tracked as follow-on work.

Current `-j` is safe for:
- Read-only analysis agents
- Agents writing only to non-overlapping paths
- Discard-stdout benchmarking runs

---

## Reusable lessons

- `if (( expr )); then ...; fi` is unambiguous under `set -e`; avoid `(( expr )) && cmd` for anything that may be false.
- macOS `mktemp`: X's must be at the end of the template; no suffix support.
- `awk -v var=value` is the safe way to inject shell variables into awk patterns — avoids all shell-interpolation issues with quotes, backslashes, and `&`.
- `die` → `quit`: friendlier error function name, no behaviour change needed.
- Parallel bash jobs: collect PIDs into an array, then `for pid in "${pids[@]}"; do wait "$pid"; done` — each `wait` propagates the job's exit code, so `set -e` will abort if any member fails.
