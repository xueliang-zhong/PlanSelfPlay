# PlanSelfPlay

A simple CLI for agent self-improvement loops.

Works with **codex**, **claude**, and **opencode** out of the box.

## Core Idea

```bash
GOAL="your optimisation goal"
GENERATIONS=100
for ((i=0; i<$GENERATIONS; i++)); do
  # Inject goal into a self improving plan template
  sed "s/GOAL:.*/GOAL: $GOAL/" PLAN_TEMPLATE.txt > plan.txt
  # Run agent - plan template instructs it to read memory from previous generations and write new ones
  codex --full-auto exec - < plan.txt
done
```

That's it. PSP wraps this loop with a self-improvement [PLAN template](plan.template.txt), goal and history management, and built-in presets for codex, claude, and opencode.

## Install

```bash
git clone https://github.com/xueliang-zhong/PlanSelfPlay.git ~/PlanSelfPlay
~/PlanSelfPlay/psp --install
```

`psp --install` creates `~/.local/bin/psp`, adds a managed PATH block to
`~/.zshrc` and `~/.bashrc`, and bootstraps `~/.psp/config.toml`. Open a new
shell and `psp` is ready to use from anywhere.

## Usage

```bash
echo "improve test coverage" | psp         # run with a goal
psp -p plan.txt -g 6                       # run your own plan
psp --init-plan plan.txt                   # write a starter plan
psp --history | fzf | psp                  # re-run a past goal
psp --help                                 # all options
```

Requirements: `bash`, and at least one of `codex` / `claude` / `opencode` on `PATH`.

See **[doc/guide.md](doc/guide.md)** for the full user guide.

## License

MIT — see [LICENSE](LICENSE).
