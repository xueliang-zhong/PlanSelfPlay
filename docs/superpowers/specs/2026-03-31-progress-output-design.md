# Design: Progress Output & Per-Generation Logging

**Date:** 2026-03-31
**Status:** Approved

---

## Problem

PSP's current progress output is verbose and carries redundant fields on every
generation line:

```
PSP CONFIG | agent=codex | plan=(builtin) | goal=reduce lines of code | generations=9 | sleep=2 | budget=0s | stdout=discard | bin=codex | args=--full-auto exec -
PSP 1/9 | agent=codex | plan=(builtin) | bin=codex | args=--full-auto exec -
PSP 2/9 | agent=codex | plan=(builtin) | bin=codex | args=--full-auto exec -
```

Agent stdout is discarded by default (`--stdout discard`) with no way to
retrieve it after the fact. There is no per-generation log file option.

---

## Goals

1. A clean one-line header that confirms plan, goal, agent, and generation count.
2. A terse per-generation status line (start + outcome).
3. Opt-in per-generation log files via `--stdout log`.
4. Zero breaking changes to `--stdout discard` and `--stdout inherit`.

---

## Output Format

### Header line (always)

```
PSP Step | plan: <display> | goal: <goal> | agent: <agent> | generations: <N>
```

`<display>` is `(builtin)` when no explicit plan file is given, otherwise the
plan filename.

### Per-generation lines

Without `--stdout log`:

```
PSP 1/9 | running...
PSP 1/9 | committed abc1234
PSP 2/9 | running...
PSP 2/9 | no commit
```

With `--stdout log`:

```
PSP 1/9 | running... → psp_codex_20260331T090000Z_gen1.log
PSP 1/9 | committed abc1234
PSP 2/9 | running... → psp_codex_20260331T090000Z_gen2.log
PSP 2/9 | no commit
```

---

## `--stdout log` Mode

`stdout_mode` gains a third valid value: `log`.

**Log file naming:** `psp_<agent>_<run_ts>_gen<N>.log`

- `<agent>`: the agent name (e.g. `codex`, `claude`, `opencode`)
- `<run_ts>`: UTC timestamp computed **once** at loop start (`YYYYMMDDTHHMMSSz`),
  shared across all generations in the same run so logs sort together
- `<N>`: zero-padded generation number (e.g. `gen01`, `gen02`)
- Written to `$PWD`

**Priority:** `--stdout log` in `config.toml`, env var, or CLI flag; lowest to
highest as with all other options.

---

## Implementation Changes

| Location | Change |
|---|---|
| `planselfplay.sh` — validation | Accept `log` as third valid value for `stdout_mode` |
| `planselfplay.sh` — loop setup | When `stdout_mode=log`: compute `run_ts` once before the loop |
| `planselfplay.sh` — loop body | Per generation: set `stdout_target` to log file path; print `running... → <file>` |
| `planselfplay.sh` — loop body | Print outcome line after agent exits: `committed <sha>` or `no commit` |
| `planselfplay.sh` — CONFIG line | Replace with `PSP Step | plan: ... | goal: ... | agent: ... | generations: N` |
| `planselfplay.sh` — `write_default_config` | Add `# stdout = "log"` as commented example |
| `doc/guide.md` | Update progress output examples; document `log` mode |

---

## Non-Goals

- `tee` mode (log AND inherit simultaneously) — YAGNI; not requested
- Auto-creating a `psp_logs/` subdirectory — log files go in `$PWD` alongside
  other PSP artifacts (results.tsv, skill_*.md, etc.)
- Rotating or cleaning up old logs — user responsibility

---

## Backward Compatibility

`--stdout discard` and `--stdout inherit` are unchanged in behaviour and
remain valid values. The CONFIG line format changes (less verbose) but is
informational only — nothing parses it.
