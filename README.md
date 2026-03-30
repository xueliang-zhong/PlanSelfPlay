# PlanSelfPlay

> One PLAN file, one shell loop, and visible agent self-improvement.

PlanSelfPlay is a small reference repo for one simple loop: keep the agent
policy in a plain-text PLAN file, replay it with a short shell script, and let
improvements land as ordinary diffs, commits, and notes instead of disappearing
into framework internals.

You can read the whole setup in a few minutes, see what each generation
changed, and copy the pattern into another repo the same day.

Works with **codex**, **claude** (Claude Code), and **opencode** out of the box.

## At A Glance

| Part | What it is | Why it matters |
| --- | --- | --- |
| Policy | `PLAN.example.txt` | Keeps the agent rules, memory, strategy, and constraints in plain text |
| Runner | `planselfplay.sh` | Replays the plan through the chosen agent with a tiny shell loop |
| Outputs | diffs, commits, and optional `agent_*.md` notes | Keeps the trajectory visible in normal repo artifacts |

## Quickstart

Requirements: `bash`, at least one of `codex` / `claude` / `opencode` on
`PATH`, and `timeout` if you want the bundled bounded-scan rule.

If you want proof before theory, start here:

```bash
# 1. preview: print the resolved command without running anything
./planselfplay.sh --dry-run

# 2. zero-config: no plan file needed, just describe the goal
./planselfplay.sh --goal "reduce lines of code"
./planselfplay.sh --goal "maximise function-level test coverage"
./planselfplay.sh --goal "eliminate duplicate logic"

# 3. bring your own plan
cp PLAN.example.txt plan.txt
# edit plan.txt, then:
./planselfplay.sh --plan plan.txt --generations 6

# 4. scale up: 3 parallel agents per generation (burns 3x tokens)
./planselfplay.sh --plan plan.txt --generations 6 -j3

# 5. swap the agent
./planselfplay.sh --agent claude --plan plan.txt --generations 6
./planselfplay.sh --agent opencode --plan plan.txt --generations 6
```

## Agent Presets

Each agent is pre-configured to read the plan from stdin in non-interactive mode:

| Agent | Default command |
| --- | --- |
| `codex` | `codex --full-auto exec -` |
| `claude` | `claude -p -` |
| `opencode` | `opencode run -` |

Override any preset with `--agent-bin` and `--agent-args`, or via env vars
`AGENT_BIN` and `AGENT_ARGS`.

## Repo Map

The public surface area is intentionally small and easy to audit:

| File | Role |
| --- | --- |
| [PLAN.example.txt](PLAN.example.txt) | Bundled example PLAN and plain-text appendix |
| [planselfplay.sh](planselfplay.sh) | Small driver that replays a PLAN through the chosen agent |
| [README.md](README.md) | Overview, quickstart, adaptation guide, and optional ML mapping |
| [LICENSE](LICENSE) | MIT license |

Pick the shortest reading path that matches what you need:

- Want the idea first: read `PLAN.example.txt`.
- Want the mechanics first: read `planselfplay.sh`.
- Want the shortest runnable path: jump to Quickstart.
- Want the research framing: jump to the optional ML mapping section below.

## How It Works

The mechanics stay small on purpose: one plain-text file defines the policy,
and one shell script replays it. A quick example can be found at
`PLAN.example.txt`, but the runner can replay any readable plan path.

**Example plan shape**
```text
DOMAIN: this repo/folder contains ___ (topic).
GOAL: optimize this work to have less/more of ___.
LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes before changing anything.
STRATEGY: use a 90%/10% split between refinement and one mutation.
RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently."
AT TASK COMPLETION: write agent_<topic>_memory.md.
SELECTION: keep candidates (git commit patches) with better results than previous work.
```

**Simplified runner loop**
```bash
GENERATIONS=100
for ((i=1; i<=$GENERATIONS; i++)); do
  codex --full-auto exec - < PLAN.txt
done
```

In practice, each generation reads prior notes, works inside the repo-level
constraints, and leaves behind artifacts that the next generation can inspect.

## Adapting It

Start with [`PLAN.example.txt`](PLAN.example.txt). In most repos, that is
where most of the customization lives.

Then:

1. Rewrite `DOMAIN` and `GOAL` so they match the repo and the optimization target.
2. Keep `LEARN FROM PREVIOUS RUNS`, `STRATEGY`, `RETHINK`, and `AT TASK COMPLETION` unless you intentionally want a different memory or search loop.
3. Update `SUCCESS CONDITION` and `CONSTRAINTS` to fit the environment you care about.
4. Preserve plain-text trajectory artifacts such as `agent_*.md`, diffs, and
   commits so the next run can retrieve prior cases instead of starting cold.

## Design Choices

- Pure text over hidden state: the PLAN is the policy.
- One small loop over framework glue: the runner stays easy to audit.
- Ordinary artifacts over special storage: diffs, commits, and `agent_*.md`
  preserve the trajectory.
- Small control surface over broad automation: fewer moving parts make the
  pattern easier to reuse and review.
- Agent-agnostic by default: codex, claude, and opencode all work with the
  same PLAN file and the same shell loop.

## Mapping PLAN File to ML Concepts

The PLAN is close to a compact search policy with external memory, so each
control maps to the nearest optimization or agent-learning role.

| PLAN File (Line by Line)                                                                                      | ML / Optimization Concepts                                                          | References                                                                                                                                                                                                         |
|---------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| DOMAIN: this repo/folder contains ___ (topic).                                                                | Problem formulation plus state space: what task and repo state the run can explore. |                                                                                                                                                                                                                    |
| GOAL: optimize this work to have less/more of ___.                                                            | Loss / fitness function: what counts as better.                                     | [Wiki: Loss function](https://en.wikipedia.org/wiki/Loss_function)<br>[Wiki: Fitness function](https://en.wikipedia.org/wiki/Fitness_function)                                                                     |
| LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes before changing anything.                           | Retrieved case memory: reuse prior cases instead of updating weights.               | [Wiki: Case-based reasoning](https://en.wikipedia.org/wiki/Case-based_reasoning)<br>[Paper: Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)                       |
| STRATEGY: use a 90%/10% split between refinement and one mutation.                                            | Exploration/exploitation policy: mostly local search, with a small mutation budget. | [Wiki: Exploration-exploitation dilemma](https://en.wikipedia.org/wiki/Exploration%E2%80%93exploitation_dilemma)<br>[Wiki: Local search (optimization)](https://en.wikipedia.org/wiki/Local_search_(optimization)) |
| RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently." | Mandatory self-critique and revision step.                                          | [Paper: Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)                                                                                                                    |
| AT TASK COMPLETION: write agent_<topic>_memory.md.                                                            | Memory write-back: compress the run into a reusable case.                           | [Paper: ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144)<br>[Wiki: Case-based reasoning](https://en.wikipedia.org/wiki/Case-based_reasoning)                                         |
| SELECTION: keep candidates (git commit patches) with better results.                                          | Selection rule: keep (git commit) only clearly better candidates.                   | [Wiki: Selection (evolutionary algorithm)](https://en.wikipedia.org/wiki/Selection_(evolutionary_algorithm))                                                                                                       |
| CONSTRAINTS: ...                                                                                              | Hard constraints and feasible region: what must stay valid while optimizing.        |                                                                                                                                                                                                                    |

Taken together, the PLAN is closer to a compact search loop with retrieval:
define the problem and objective, retrieve prior cases, spend most effort on
local search with some exploration, force one critique pass, write back a
reusable case, and keep only candidates that satisfy the acceptance rule and
constraints.


## Tips

**Start small.** Use `--generations 2` for a first run to check that the agent reads the plan and produces sensible output before committing to a long loop.

**Watch live output.** Add `--stdout inherit` to print agent output directly to the terminal instead of discarding it, useful when debugging a new plan.

**Inspect the effective plan.** When using `--goal`, the script writes a `<plan>.tmp.<id>` file in the repo for the duration of the run. Open it to confirm the `GOAL:` line was substituted as expected before the first generation finishes.

**Preview without running.** `--dry-run` prints the resolved agent command and exits, useful for checking `--agent-bin` / `--agent-args` overrides without invoking the agent.

**Use `--goal` for targeted experiments.** Keep one canonical `plan.txt` and vary the objective at the command line. Each run gets its own uniquely named temp file so parallel or sequential experiments stay traceable.

**Token budget.** Long runs with capable models burn tokens quickly. Set `--generations` conservatively (6–10) and increase only when earlier generations show consistent improvement. With `-jN`, each generation multiplies token spend by N, so start with `-j2` before going wider.

**Unblocking agents (use with caution).** When system restrictions or access controls prevent the agent from proceeding, permission flags can lift those barriers and keep the loop running unattended. Pass them via `--agent-args`:

```bash
# codex: bypass system restrictions and access controls
./planselfplay.sh --agent-args "--full-auto --yolo exec -" --plan plan.txt

# claude: bypass permission checks
./planselfplay.sh --agent claude --agent-args "-p --dangerously-skip-permissions -" --plan plan.txt
```

**These flags remove every guardrail.** The agent will run destructive commands without asking. Useful for keeping long runs unblocked, but commit your work and use a throwaway branch first. There could be no undo.

**Population (`-jN`).** Runs N agents in parallel per generation. Git worktree isolation per member is enabled by default for `-jN` runs, so each agent works on its own branch without racing. After each generation, worktree paths are cleaned up and the member branches (`psp/gen{g}-m{1..N}`) are left for inspection and merging.

## Inspiration

This project is inspired by `karpathy/autoresearch`. The difference here is the
deliberate commitment to plain-text control and a small shell loop, so the
pattern stays easy to inspect, fork, and modify.

## License

Released under the MIT License. See [LICENSE](LICENSE).
