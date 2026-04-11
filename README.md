# PlanSelfPlay (psp)

PlanSelfPlay (psp) is a simple CLI tool for agent self-improvement loops.
It runs your agent on a goal across N generations - each run reads notes from the last and refines its approach.

Works with **codex**, **claude**, and **opencode** out of the box.

## Install

```bash
git clone https://github.com/xueliang-zhong/PlanSelfPlay.git ~/PlanSelfPlay
~/PlanSelfPlay/psp --install
source <(psp --generate-completion)         # optional: tab completion
```

Open a new shell and `psp` is ready to use from anywhere.
Requirements: Python 3, and at least one of `codex` / `claude` / `opencode` on `PATH`.

## Usage

```bash
echo "improve test coverage" | psp          # pipe a goal and run
psp -G "improve test coverage"              # or use a flag

psp --history | fzf | psp                   # pick a past goal and re-run
psp --fzf                                   # same as above

psp --init-plan plan.txt                    # write a starter plan file
psp -p plan.txt -g 20                       # run a custom plan for 20 generations
psp --config-show                           # audit resolved config and sources
PSP_AGENT=claude psp --config-show          # inspect env/config/CLI precedence
psp --help                                  # all options
```

Resolution order is explicit and inspectable: defaults < `~/.psp/config.toml` < `PSP_*` env vars < CLI flags.
Color output is TTY-aware by default, and `--no-color` forces plain output when you need deterministic logs or pipes.

No Python? **`psp-nano`** is a self-contained bash script with the same core loop:

```bash
echo "improve test coverage" | psp-nano     # pipe a goal and run
psp-nano --help                             # all options
```

## Core Idea

PSP runs your agent on a goal with a loop over N generations.

```bash
GOAL="your optimisation goal"
GENERATIONS=100
for ((i=0; i<$GENERATIONS; i++)); do
  sed "s/GOAL:.*/GOAL: $GOAL/" PLAN_TEMPLATE.txt > plan.txt
  codex --full-auto --ask-for-approval never exec - < plan.txt
done
```


PSP wraps this loop with following simple self-improvement plan template, goal and history management, and built-in presets for codex, claude, and opencode.

```bash
DOMAIN: the current working directory and its contents.
GOAL: # improve code quality.
AUTONOMY: never prompt the user, make every decision yourself.
LEARN FROM PREVIOUS RUNS: read any local agent_memory_*.md notes before changing anything.
STRATEGY: 90% refine the best path, 10% try one mutation.
SELECTION: git commit if better, git reset otherwise, write agent_memory_<topic>.md to summarise your work.
CONSTRAINTS: work only inside this repo, never delete this plan file.
```
## Fun Demos

Port psp to C++20:

```bash
echo "Rewrite psp to C++20 to reach feature parity, maximise new C++ feature usage." | psp
```

Port psp to Rust:

```bash
echo "Rewrite psp to Rust to achieve feature parity, maximise runtime performance." | psp
```

Rewrite psp in bash:

```bash
echo "Using TDD, rewrite psp in bash to reach feature parity, optimise for readability." | psp
```

Or run it on your own codebase:

```bash
echo "Maximise test coverage starting with the most critical code paths." | psp
echo "Find and fix the top 3 performance bottlenecks; benchmark before and after each change." | psp
echo "Minimise dead code: unused functions, imports, and unreachable branches." | psp
```
## Comparison with similar agent loop tools

| | **psp** | **Claude /loop** | **Karpathy autoresearch** |
|---|---|---|---|
| Stopping criterion | N generations (configurable) | Task complete (model judges) | Fixed compute budget per run |
| Fitness function | Expressive prose goal | Human intent | Single numeric metric (val_bpb) |
| Memory / knowledge | Plain-text notes + git commits | None between sessions | Git history + in-context window |
| Scope | Any repo, any goal | Unbounded, human-steered | One file, one domain |
| Human role | Sets goal + policy document | Orchestrates in real time | Absentee (set and forget) |
| Autonomy level | Fully independent (any goal) | Agentic (human-supervised) | Fully independent (narrow domain) |
| Transparency | Inspectable markdown artefacts | Conversation only | Git log + in-context |
| Best for | Tasks that improve through optimisation over many generations | General tasks, exploration | Tight metric optimisation loops |

In short:
- **Claude /loop** - breadth, human-steered.
- **Autoresearch** - speed, metric-locked.
- **psp** - open-ended goals, memory-persistent, fully autonomous.

## See Also

**[doc/guide.md](doc/guide.md)** - full option reference and config guide.

## License

MIT - see [LICENSE](LICENSE).
