# PlanSelfPlay

> One PLAN file, one shell loop, and visible agent self-improvement.

PlanSelfPlay is a small reference repo for one simple loop: keep the agent
policy in a plain-text PLAN file, replay it with a short shell script, and let
improvements land as ordinary diffs, commits, and notes instead of disappearing
into framework internals.

You can read the whole setup in a few minutes, see what each generation
changed, and copy the pattern into another repo the same day.

## At A Glance

| Part | What it is | Why it matters |
| --- | --- | --- |
| Policy | `PLAN.example.txt` | Keeps the agent rules, memory, strategy, and constraints in plain text |
| Runner | `planselfplay.sh` | Replays the plan through `codex exec -` with a tiny shell loop |
| Outputs | diffs, commits, and optional `codex_*.md` notes | Keeps the trajectory visible in normal repo artifacts |

## Start Here

- Want the policy first: read `PLAN.example.txt`.
- Want the shell mechanics first: read `planselfplay.sh`.
- Want the shortest runnable path: run `./planselfplay.sh --dry-run`.

## When This Pattern Helps

- Portable: copy the repo, edit the PLAN, and rerun the loop.
- Inspectable: the policy stays in readable text, not hidden orchestration state.
- Low overhead: you can try it with `bash`, `codex`, and normal git habits.
- Reusable: each run leaves behind human-readable artifacts that the next run
  can learn from.

## What A Run Leaves Behind

After a useful run, you usually have some mix of:

- A working-tree diff you can inspect with normal git tools
- A local commit when the result is clearly better
- A `codex_*.md` note when your plan asks the agent to write one

That makes the loop useful both as a research trace and as an engineering
workflow you can review, replay, and tighten with normal git habits.

## Quickstart

Requirements: `bash`, `codex` on `PATH`, and `timeout` if you want the bundled
bounded-scan rule.

If you want proof before theory, start here:

```bash
# preview the exact command without running it
./planselfplay.sh --dry-run

# watch a short run live
STDOUT_MODE=inherit ./planselfplay.sh --generations 3

# copy the example PLAN, then customize it
cp PLAN.example.txt plan.txt
# edit plan.txt with your goals and workflow rules
./planselfplay.sh --plan plan.txt --generations 6
```

## Repo Map

The public surface area is intentionally small and easy to audit:

| File | Role |
| --- | --- |
| [PLAN.example.txt](PLAN.example.txt) | Bundled example PLAN and plain-text appendix |
| [planselfplay.sh](planselfplay.sh) | Small driver that replays a PLAN through `codex exec -` |
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
LEARN FROM PREVIOUS RUNS: read any local codex_*.md notes before changing anything.
STRATEGY: use a 90%/10% split between refinement and one mutation.
RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently."
AT TASK COMPLETION: write codex_<topic>_memory.md.
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
4. Preserve plain-text trajectory artifacts such as `codex_*.md`, diffs, and
   commits so the next run can retrieve prior cases instead of starting cold.

## Why It Stays Small

- Pure text over hidden state: the PLAN is the policy.
- One small loop over framework glue: the runner stays easy to audit.
- Ordinary artifacts over special storage: diffs, commits, and `codex_*.md`
  preserve the trajectory.
- Small control surface over broad automation: fewer moving parts make the
  pattern easier to reuse and review.

## Mapping PLAN File to ML Concepts

The PLAN is closer to a compact search policy with external memory, so each
control maps to the nearest optimization or agent-learning role.

| PLAN File (Line by Line)                                                                                      | ML / Optimization Concepts                                                          | References                                                                                                                                                                                                                                                                                                                       |
|---------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| DOMAIN: this repo/folder contains ___ (topic).                                                                | Problem formulation plus state space: what task and repo state the run can explore. | [Wiki: Optimization problem](https://en.wikipedia.org/wiki/Optimization_problem)<br>[Wiki: State-space search](https://en.wikipedia.org/wiki/State-space_search)                                                                                                                                                                 |
| GOAL: optimize this work to have less/more of ___.                                                            | Loss / fitness function: what counts as better.                                     | [Wiki: Loss function](https://en.wikipedia.org/wiki/Loss_function)<br>[Wiki: Fitness function](https://en.wikipedia.org/wiki/Fitness_function)                                                                                                                                                                                   |
| LEARN FROM PREVIOUS RUNS: read any local codex_*.md notes before changing anything.                           | Retrieved case memory: reuse prior cases instead of updating weights.               | [Wiki: Case-based reasoning](https://en.wikipedia.org/wiki/Case-based_reasoning)<br>[Paper: Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)                                                                                                                                     |
| STRATEGY: use a 90%/10% split between refinement and one mutation.                                            | Exploration/exploitation policy: mostly local search, with a small mutation budget. | [Wiki: Exploration-exploitation dilemma](https://en.wikipedia.org/wiki/Exploration%E2%80%93exploitation_dilemma)<br>[Wiki: Local search (optimization)](https://en.wikipedia.org/wiki/Local_search_(optimization))<br>[Wiki: Mutation (evolutionary algorithm)](https://en.wikipedia.org/wiki/Mutation_(evolutionary_algorithm)) |
| RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently." | Mandatory self-critique and revision step.                                          | [Paper: Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)                                                                                                                                                                                                                                  |
| AT TASK COMPLETION: write codex_<topic>_memory.md.                                                            | Memory write-back: compress the run into a reusable case.                           | [Paper: ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144)<br>[Wiki: Case-based reasoning](https://en.wikipedia.org/wiki/Case-based_reasoning)                                                                                                                                                       |
| SELECTION: keep candidates (git commit patches) with better results.                                          | Selection rule: keep (git commit) only clearly better candidates.                   | [Wiki: Selection (evolutionary algorithm)](https://en.wikipedia.org/wiki/Selection_(evolutionary_algorithm))                                                                                                                                                                                                                     |
| CONSTRAINTS: ...                                                                                              | Hard constraints and feasible region: what must stay valid while optimizing.        |                                                                                                                                                                                                                                                                                                                                  |

Taken together, the PLAN is closer to a compact search loop with retrieval:
define the problem and objective, retrieve prior cases, spend most effort on
local search with some exploration, force one critique pass, write back a
reusable case, and keep only candidates that satisfy the acceptance rule and
constraints.

## Inspiration

This project is inspired by `karpathy/autoresearch`. The difference here is the
deliberate commitment to plain-text control and a small shell loop, so the
pattern stays easy to inspect, fork, and modify.

## License

Released under the MIT License. See [LICENSE](LICENSE).
