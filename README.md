# PlanSelfPlay

PlanSelfPlay (psp) is a simple CLI tool for agent self-improvement loops.
It runs your agent on a goal across N generations - each run reads notes from the last and refines its approach.

Works with **codex**, **claude**, and **opencode** out of the box.

Two flavours:
- **`psp`** (full-featured Python CLI)
- **`psp-nano`** (minimal bash)

## Install

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/xueliang-zhong/PlanSelfPlay.git ~/PlanSelfPlay
~/PlanSelfPlay/psp --install
```

`psp --install` creates `~/.local/bin/psp`, adds a managed PATH block to
`~/.zshrc` and `~/.bashrc`, and bootstraps `~/.psp/config.toml`. Open a new
shell and `psp` is ready to use from anywhere.

Requirements: `bash`, at least one of `codex` / `claude` / `opencode` on `PATH`, and `fzf` for `--fzf`.

## Usage

```bash
echo "improve test coverage" | psp         # pipe a goal and run
psp --history | fzf | psp                  # pick a past goal with fzf and re-run
psp --fzf                                  # structured history picker with metadata preview

psp --init-plan plan.txt                   # write a starter plan file
psp -p plan.txt -g20                       # run a custom plan for 20 generations

psp --help                                 # all options
```

No Python? Use **psp-nano** - a self-contained bash script with the same core loop and no dependencies beyond the agent:

```bash
echo "improve test coverage" | psp-nano    # pipe a goal and run
psp-nano --help                            # all options
```

`psp --install` installs both `psp` and `psp-nano` to `~/.local/bin`.

See **[doc/guide.md](doc/guide.md)** for the full user guide.

## Core Idea

```bash
GOAL="your optimisation goal"
GENERATIONS=100
for ((i=0; i<$GENERATIONS; i++)); do
  sed "s/GOAL:.*/GOAL: $GOAL/" PLAN_TEMPLATE.txt > plan.txt
  codex --full-auto exec - < plan.txt
done
```

That's it. PSP wraps this loop with a self-improvement [PLAN template](plan.template.txt), goal and history management, and built-in presets for codex, claude, and opencode.

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

## License

MIT — see [LICENSE](LICENSE).
