# PlanSelfPlay — User Guide

## What it is

PlanSelfPlay keeps your agent policy in a plain-text PLAN file and replays it
with a short shell script. Improvements land as ordinary diffs, commits, and
notes instead of disappearing into framework internals. You can read the whole
setup in a few minutes, see what each generation changed, and copy the pattern
into another repo the same day.

---

## Install

```bash
git clone https://github.com/xueliang-zhong/PlanSelfPlay.git ~/PlanSelfPlay
~/PlanSelfPlay/psp --install
```

`--install` creates `~/.local/bin/psp`, adds a managed PATH block to
`~/.zshrc` and `~/.bashrc`, and bootstraps `~/.psp/config.toml`.

If `~/.local/bin` is not yet on your PATH, the installer prints a one-liner
to activate it in the current shell:

```
Install complete. Activate in your current shell:
  export PATH="/home/you/.local/bin:$PATH"
Or open a new terminal — your rc file is already updated.
```

---

## Files

| File | Role |
| --- | --- |
| `psp` | Driver: replays a PLAN through the chosen agent |
| `plan.template.txt` | Bundled starter plan with all directives |
| `~/.psp/config.toml` | User defaults (lowest priority) |
| `~/.psp/history` | Append-only run log |

---

## Quick examples

```bash
# Interactive — prompts "Goal: "
psp

# Pipe a goal (no plan file needed)
echo "reduce lines of code" | psp

# Re-run a past goal
psp --history | fzf | psp
psp --fzf

# Inspect generation logs
psp --logs

# Run your own plan
psp -p plan.txt

# 6 generations, Claude, with a time cap
psp -a claude -p plan.txt -g 6 -t 3600

# Preview the resolved command without running anything
echo "add type hints" | psp --dry-run
```

---

## All options

```
Usage: psp [options] [plan-path]
       echo "GOAL" | psp [options]
```

| Flag | Description |
| --- | --- |
| `-a, --agent codex\|claude\|opencode` | Agent to use (default: codex) |
| `-p, --plan PATH` | Plan file to replay |
| `-g, --generations N` | Generations to run (default: 10) |
| `-s, --sleep SECONDS` | Pause between generations (default: 2) |
| `-t, --time-budget SECONDS` | Wall-clock cap; 0 = no limit |
| `-o, --output discard\|inherit\|log` | Agent output handling (default: log) |
| `-x, --agent-args STRING` | Override full agent argument string |
| `--agent-bin PATH` | Override agent executable |
| `--yolo` | Skip permission prompts (use with care) |
| `--keep-logs always\|session\|never` | Log retention: always=keep forever (default), session=delete on exit, never=delete after each generation |
| `--install` | Install psp to `~/.local/bin`, wire PATH, and initialise `~/.psp/config.toml` |
| `--init-plan [PATH]` | Write a starter plan file and exit |
| `-G, --goal TEXT` | Set goal directly (stdin takes priority if piped) |
| `--config-show` | Print resolved config with source of each value and exit |
| `--generate-completion` | Print shell completion script (`source <(psp --generate-completion)`) |
| `--dry-run` | Print resolved command and exit |
| `--history` | Print past goals and exit |
| `--continue, -C` | Re-run the last goal from history (like `!!` in bash) |
| `--fzf` | Browse past goals with metadata preview |
| `--logs` | Print generation log paths (one per line) |
| `--no-color` | Disable ANSI color output |
| `--quiet, -q` | Suppress progress output, show only summary |
| `--stop-on-error` | Abort the loop on first agent failure |
| `--cwd PATH` | Run in a different working directory |
| `--verbose` | Show detailed timing and debug info |
| `--print-plan` | Print the effective plan and exit |
| `--model MODEL` | LLM model to use (e.g. gpt-4o, claude-sonnet-4-20250514) |
| `--config PATH` | Use an alternative config file instead of ~/.psp/config.toml |
| `--no-banner` | Suppress the header line |
| `--env KEY=VALUE` | Pass an environment variable to the agent (repeatable) |
| `--headless` | Suppress all interactive prompts (CI/automation) |
| `--max-turns N` | Max conversation turns per generation |
| `--diff` | Show git diff after each generation |
| `--clean` | Skip loading config file (from neovim `--clean`) |
| `--last, -L` | Show last run summary |
| `--format json` | Output in JSON format (for `--config-show`, `--history`, `--logs`, `--last`) |
| `--follow, -f` | Tail the most recent generation log |
| `--generation-timeout SECONDS` | Per-generation timeout; 0 = no limit |
| `--timeout SECONDS` | Alias for `--generation-timeout` |
| `--retry N` | Retry failed generations with backoff |
| `--stats` | Print aggregate run statistics |
| `--tac` | Reverse ordering for `--history` / `--logs` output |
| `--progress auto\|plain\|tty` | Output verbosity hint for compatible agents |
| `-V, --version` | Print version and exit |
| `-h, --help` | Show help |

### Agent presets

Each agent is pre-configured for non-interactive stdin use:

| Agent | Default command |
| --- | --- |
| `codex` | `codex --full-auto exec -` |
| `claude` | `claude -p -` |
| `opencode` | `opencode run -` |

Override with `--agent-bin` / `--agent-args`, or env vars `AGENT_BIN` / `AGENT_ARGS`.

---

## User config (`~/.psp/config.toml`)

Bootstrap once, then edit:

```bash
psp --install         # one-shot: install + PATH + config
```

All keys are optional. Priority: `config.toml` < `PSP_*` env vars < CLI flags.

```toml
# ~/.psp/config.toml
agent       = "claude"    # codex | claude | opencode
generations = 6
# sleep       = 2
# time_budget = 3600      # hard stop in seconds
# output      = "log"     # discard | inherit | log
# agent_bin   = ""
# agent_args  = ""
# yolo        = false
# keep_logs   = "always"   # always | session | never  (always = default)
# quiet       = false
# stop_on_error = false
# verbose     = false
# no_color    = false
# no_banner   = false
# model       = ""
# headless    = false
# max_turns   = ""
# diff_mode   = false
# timeout     = 0           # per-generation timeout (CLI: --generation-timeout)
# retry       = 0
# progress    = "auto"     # auto | plain | tty
```

`psp --config-show` prints both the resolved values and the source for each one,
so it is the fastest way to debug precedence issues.

Color output follows terminal capability by default: if stdout is not a TTY,
PSP falls back to plain text automatically. Use `--no-color` to force plain
output even in an interactive terminal.

## Run history

Every real run appends one line to `~/.psp/history`:

```
2026-03-31T09:00:00Z  claude  /your/repo  g=6  improve test coverage
```

Browse and re-run:

```bash
psp --history              # list past goals
psp --history | fzf | psp   # pick one and re-run
psp --fzf                   # richer picker with agent / generation / cwd preview
```

`psp --fzf` keeps the same pipe-first behavior underneath, but surfaces the
saved agent, generation count, working directory, and timestamp in the preview
pane so long histories stay navigable.

## Log browser

`psp --logs` prints one absolute log path per line, so it composes cleanly with
standard tools:

```bash
psp --logs
```

To clean up all generation logs from the current run:

```bash
psp --logs | xargs rm
```

---

## The PLAN file

A plan is a plain-text file the agent reads as its instructions. The built-in
template (used when you pipe a goal without `--plan`) contains:

```text
DOMAIN: the current working directory and its contents.
GOAL: <your goal>
LEARN FROM CURRENT MEMORY: read CURRENT_MEMORY.md first if it exists.
LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes.
APPLY SKILLS: read any skill_*.md files and apply relevant ones.
DEAD ENDS: read FAILED_PATHS.md; never re-try listed approaches.
STRATEGY: 90% refine the best path / 10% test one mutation.
RETHINK: after the first design, pause and reconsider.
AT TASK COMPLETION: write agent_<topic>_memory.md.
UPDATE CURRENT MEMORY: merge new lessons into CURRENT_MEMORY.md.
WRITE SKILLS: promote reusable techniques into skill_<topic>.md.
SKILL HYGIENE: patch existing skills; create new ones only for new techniques.
SELECTION: commit if better; git reset otherwise.
CONSTRAINTS: work only inside this repo; use timeout on every scan.
```

Start your own plan with:

```bash
psp --init-plan plan.txt   # writes a commented starter file
```

Then edit `DOMAIN`, `GOAL`, and `CONSTRAINTS` to fit your repo. Keep the memory
and strategy directives unless you intentionally want a different loop.

---

## Tiered memory

PSP artifacts form a natural hierarchy. Agents write lower tiers automatically;
you promote upward when a lesson earns wider reuse.

| Tier | File | When | Scope |
| --- | --- | --- | --- |
| 1 | `agent_<timestamp>_<topic>.md` | After each run | Run-specific episode |
| 2 | `CURRENT_MEMORY.md` | When a lesson helps the next few runs | Repo-wide, near-term |
| 3 | `skill_<topic>.md` | When a technique is reusable across many runs | Broad, durable |
| 4 | `FAILED_PATHS.md` | When a failure pattern is clear | Repo-wide avoidance |

**Rule:** never promote automatically — promotion always requires judgment.

---

## Tips

**Start small.** Run `--generations 2` first to check the agent reads the plan
and produces sensible output before committing to a long loop.

**Watch live output.** Add `--output inherit` to print agent output to the
terminal, useful when debugging a new plan.

**Inspect the effective plan.** When a goal is piped in, a `plan.tmp.*` file is
written for the duration of the run. Open it to confirm the `GOAL:` line before
the first generation finishes.

**Edit the plan mid-run.** Changes to `plan.txt` take effect at the next
generation boundary without restarting the loop.

**Time budget.** `--time-budget 3600` stops the loop cleanly before starting a
generation that would exceed the cap — useful for overnight runs or CI.

**`--yolo` (use with care).** Passes the agent's permission-bypass flag. The
agent will run destructive commands without asking. Commit your work and use a
throwaway branch first.

---

## How the runner loop works

```bash
for generation in 1..N:
    run: agent < plan > output_target
    if HEAD advanced: print "committed" in terminal output
    else:             print "no commit"
    sleep between generations
```

The plan is written to a temp file per run (built-in template) or read directly
(explicit `--plan`). The agent receives it on stdin.

### Progress output

PSP prints two lines per generation — one when starting, one with the outcome:

```
| PSP STEP | plan: (builtin) | goal: reduce lines of code | agent: codex | gen: 9 |
| 🔄 PSP 1/9 | running …
| ✅ PSP 1/9 | committed abc1234 | took: 12s
| 🔄 PSP 2/9 | running …
| ⚪ PSP 2/9 | no commit | took: 8s
```

### `--output` values

| Value | Behaviour |
| --- | --- |
| `log` (default) | Each generation's output is saved to a file in `$PWD` |
| `discard` | Agent output is discarded |
| `inherit` | Agent output is printed to the terminal |

With `--output log`, a log file is created for each generation:

```
| 🔄 PSP 1/9 | running … → psp_codex_20260331T090000Z_gen01.log
| ✅ PSP 1/9 | committed abc1234 | took: 12s
```

All logs from the same run share a timestamp prefix so they sort together.
Set `output = "log"` in `~/.psp/config.toml` to make this the default.

---

## Mapping PLAN directives to ML concepts

| PLAN directive | ML / optimization concept | Reference |
| --- | --- | --- |
| `DOMAIN` | State space / problem formulation | [State space](https://en.wikipedia.org/wiki/State_space_(computer_science)) |
| `GOAL` | Loss / fitness function | [Fitness function](https://en.wikipedia.org/wiki/Fitness_function) |
| `LEARN FROM CURRENT MEMORY` | Working memory | [Working memory](https://en.wikipedia.org/wiki/Working_memory) |
| `LEARN FROM PREVIOUS RUNS` | Episodic memory retrieval | [Reflexion](https://arxiv.org/abs/2303.11366), [ExpeL](https://arxiv.org/abs/2308.10144) |
| `APPLY SKILLS` | Procedural memory | [Voyager](https://arxiv.org/abs/2305.16291) |
| `DEAD ENDS` | Negative experience / tabu search | [Tabu search](https://en.wikipedia.org/wiki/Tabu_search) |
| `STRATEGY` | Exploration–exploitation | [Exploration–exploitation](https://en.wikipedia.org/wiki/Exploration%E2%80%93exploitation_dilemma) |
| `RETHINK` | Self-critique / iterative refinement | [Self-Refine](https://arxiv.org/abs/2303.17651), [Tree of Thoughts](https://arxiv.org/abs/2305.10601) |
| `AT TASK COMPLETION` | Episodic write-back | [ExpeL](https://arxiv.org/abs/2308.10144) |
| `WRITE SKILLS` | Skill distillation | [Voyager](https://arxiv.org/abs/2305.16291) |
| `SELECTION` | Selection pressure / hill climbing | [Hill climbing](https://en.wikipedia.org/wiki/Hill_climbing) |
| `CONSTRAINTS` | Feasible region | [Constraint satisfaction](https://en.wikipedia.org/wiki/Constraint_satisfaction_problem) |

---

## Inspiration

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).
The difference here is the deliberate commitment to plain-text control and a
small shell loop — easy to inspect, fork, and modify.
