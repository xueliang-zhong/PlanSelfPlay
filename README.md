# PlanSelfPlay

> One PLAN file, one shell loop, and visible agent self-improvement.

PlanSelfPlay is a small reference repo for one simple loop: keep the agent
policy in a plain-text PLAN file, replay it with a short shell script, and let
improvements land as ordinary diffs, commits, and notes instead of disappearing
into framework internals.

You can read the whole setup in a few minutes, see what each generation
changed, and copy the pattern into another repo the same day.

Works with **codex**, **claude** (Claude Code), and **opencode** out of the box.

`psp` is a symlink to `planselfplay.sh` — use whichever you prefer.

## At A Glance

| Part | What it is | Why it matters |
| --- | --- | --- |
| Policy | `plan.example.txt` | Keeps the agent rules, memory, strategy, and constraints in plain text |
| Runner | `planselfplay.sh` | Replays the plan through the chosen agent with a tiny shell loop |
| Shortcut | `psp` | Symlink to `planselfplay.sh` for shorter daily use |
| Outputs | diffs, commits, and optional `agent_*.md` notes | Keeps the trajectory visible in normal repo artifacts |

## Quickstart

Requirements: `bash`, at least one of `codex` / `claude` / `opencode` on
`PATH`, and `timeout` if you want the bundled bounded-scan rule.

If you want proof before theory, start here:

```bash
# Preview the resolved command without running anything
./psp --dry-run

# Run the built-in plan template with a custom goal (no plan file needed)
echo "reduce lines of code" | ./psp
echo "maximise function-level test coverage" | ./psp

# Create your own starter plan file
./psp --init-plan plan.txt

# Run your own plan for 6 generations
./psp -p plan.txt -g6

# Run 3 agents per generation in parallel
./psp -p plan.txt -g6 -j3

# Run with a time budget instead of fixed generations
echo "reduce lines of code" | ./psp -t 3600

# Run with Claude or opencode
./psp -a claude -p plan.txt -g6
echo "reduce lines of code" | ./psp -a opencode -g6
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
| [plan.example.txt](plan.example.txt) | Bundled example PLAN and plain-text appendix |
| [planselfplay.sh](planselfplay.sh) | Small driver that replays a PLAN through the chosen agent |
| [psp](psp) | Symlink to `planselfplay.sh` for shorter daily use |
| [README.md](README.md) | Overview, quickstart, adaptation guide, and optional ML mapping |
| [LICENSE](LICENSE) | MIT license |

Pick the shortest reading path that matches what you need:

- Want the idea first: read `plan.example.txt`.
- Want the mechanics first: read `planselfplay.sh`.
- Want the shortest runnable path: jump to Quickstart.
- Want the research framing: jump to the optional ML mapping section below.

## How It Works

The mechanics stay small on purpose: one plain-text file defines the policy,
and one shell script replays it. A quick example can be found at
`plan.example.txt`, but the runner can replay any readable plan path.

**Example plan shape**
```text
DOMAIN: this repo/folder contains ___ (topic).
GOAL: optimize this work to have less/more of ___.
LEARN FROM CURRENT MEMORY: read CURRENT_MEMORY.md first if it exists.
LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes that seem relevant before changing anything.
APPLY SKILLS: read any skill_*.md files and apply relevant ones.
DEAD ENDS: read FAILED_PATHS.md; never re-try listed approaches; append new failures with reason.
STRATEGY: use a 90%/10% split between refinement and one mutation.
RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently."
AT TASK COMPLETION: write agent_<topic>_memory.md.
RESULTS LEDGER: the runner maintains results.tsv as a tab-separated run ledger with timestamp, generation, member, status, commit, and note.
UPDATE CURRENT MEMORY: merge still-relevant lessons into CURRENT_MEMORY.md.
WRITE SKILLS: promote a lesson into skill_<topic>.md only when it is reusable, concrete, and likely to help many future runs. Do not create a skill for a one-off repo quirk, a weak hunch, or a trick that succeeded only once.
SKILL HYGIENE: patch an existing skill when refining the same technique; create a new skill only for a genuinely different technique. Keep skills short, actionable, and low-duplication.
SELECTION: keep candidates (git commit patches) with better results than previous work.
CONSTRAINTS: work only inside this repo; never scan outside it.
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

Start with [`plan.example.txt`](plan.example.txt). In most repos, that is
where most of the customization lives.

Then:

1. Rewrite `DOMAIN` and `GOAL` so they match the repo and the optimization target.
2. Keep `LEARN FROM CURRENT MEMORY`, `LEARN FROM PREVIOUS RUNS`, `APPLY SKILLS`, `DEAD ENDS`, `STRATEGY`, `RETHINK`, `AT TASK COMPLETION`, `RESULTS LEDGER`, `UPDATE CURRENT MEMORY`, and `WRITE SKILLS` unless you intentionally want a different memory or search loop.
3. Update `SUCCESS CONDITION` and `CONSTRAINTS` to fit the environment you care about.
4. Preserve plain-text trajectory artifacts such as `agent_*.md`, diffs, and
   commits so the next run can retrieve prior cases instead of starting cold.

## Design Choices

- Pure text over hidden state: the PLAN is the policy.
- One small loop over framework glue: the runner stays easy to audit.
- Ordinary artifacts over special storage: diffs, commits, `agent_*.md`,
  `CURRENT_MEMORY.md`, `skill_*.md`, and `results.tsv`
  preserve the trajectory.
- Small control surface over broad automation: fewer moving parts make the
  pattern easier to reuse and review.
- Agent-agnostic by default: codex, claude, and opencode all work with the
  same PLAN file and the same shell loop.

## Mapping PLAN File to ML Concepts

The PLAN is close to a compact search policy with external memory, so each
control maps to the nearest optimization or agent-learning role.

| PLAN File (Line by Line)                                                                                      | ML / Optimization Concept                                                                                   | References                                                                                                                                                                                                                                                                      |
|---------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| DOMAIN: this repo/folder contains ___ (topic).                                                                | Problem formulation and search space: defines scope, context, and valid states the agent may explore.       | [Wiki: State space](https://en.wikipedia.org/wiki/State_space_(computer_science))<br>[Wiki: Search problem](https://en.wikipedia.org/wiki/Search_algorithm)                                                                                                                     |
| GOAL: optimize this work to have less/more of ___.                                                            | Loss / fitness function: the scalar signal that defines "better" and drives selection.                      | [Wiki: Loss function](https://en.wikipedia.org/wiki/Loss_function)<br>[Wiki: Fitness function](https://en.wikipedia.org/wiki/Fitness_function)                                                                                                                                  |
| LEARN FROM CURRENT MEMORY: read CURRENT_MEMORY.md first if it exists.                                          | Active working memory: load the current high-signal summary before diving into detailed archives.            | [Wiki: Working memory](https://en.wikipedia.org/wiki/Working_memory)<br>[Wiki: Memory consolidation](https://en.wikipedia.org/wiki/Memory_consolidation)                                                                                                                         |
| LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes that seem relevant before changing anything.        | Episodic memory retrieval: load prior experience so the agent extends the trajectory instead of restarting. | [Wiki: Episodic memory](https://en.wikipedia.org/wiki/Episodic_memory)<br>[Wiki: Case-based reasoning](https://en.wikipedia.org/wiki/Case-based_reasoning)<br>[Paper: Reflexion](https://arxiv.org/abs/2303.11366)                                                              |
| APPLY SKILLS: read any skill_*.md files and apply relevant ones.                                               | Procedural memory retrieval: reuse distilled techniques rather than re-deriving from scratch.               | [Wiki: Procedural memory](https://en.wikipedia.org/wiki/Procedural_memory)<br>[Wiki: Transfer learning](https://en.wikipedia.org/wiki/Transfer_learning)<br>[Paper: Voyager (skill library for open-ended agents)](https://arxiv.org/abs/2305.16291)                            |
| DEAD ENDS: read FAILED_PATHS.md; never re-try listed approaches; append new failures with reason.              | Negative experience memory: prune the search space by excluding approaches known to fail.                   | [Wiki: Tabu search](https://en.wikipedia.org/wiki/Tabu_search)<br>[Wiki: Constraint satisfaction](https://en.wikipedia.org/wiki/Constraint_satisfaction_problem)                                                                                                                |
| STRATEGY: use a 90%/10% split between refinement and one mutation.                                            | Exploration/exploitation policy: mostly local search around the current best, with a small mutation budget. | [Wiki: Exploration-exploitation dilemma](https://en.wikipedia.org/wiki/Exploration%E2%80%93exploitation_dilemma)<br>[Wiki: Local search](https://en.wikipedia.org/wiki/Local_search_(optimization))<br>[Wiki: Mutation (evolutionary algorithm)](https://en.wikipedia.org/wiki/Mutation_(evolutionary_algorithm)) |
| RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently." | Mandatory self-critique: forces a revision pass before acting, reducing premature commitment.               | [Paper: Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)<br>[Paper: Tree of Thoughts](https://arxiv.org/abs/2305.10601)                                                                                                                  |
| AT TASK COMPLETION: write agent_<topic>_memory.md.                                                            | Episodic memory write-back: compress the run into a retrievable case for future generations.                | [Paper: ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144)<br>[Wiki: Episodic memory](https://en.wikipedia.org/wiki/Episodic_memory)                                                                                                                |
| RESULTS LEDGER: the runner maintains results.tsv with timestamp, generation, member, status, commit, and note. | Transparent experiment ledger: keep a machine-friendly audit trail of what each generation actually produced. | [Wiki: Tab-separated values](https://en.wikipedia.org/wiki/Tab-separated_values)<br>[Wiki: Experimental record](https://en.wikipedia.org/wiki/Laboratory_notebook) |
| UPDATE CURRENT MEMORY: merge still-relevant lessons into CURRENT_MEMORY.md.                                   | Memory curation: promote short-horizon lessons into a compact active summary for future runs.               | [Wiki: Working memory](https://en.wikipedia.org/wiki/Working_memory)<br>[Wiki: Knowledge management](https://en.wikipedia.org/wiki/Knowledge_management)                                                                                                                         |
| WRITE SKILLS: promote a lesson into `skill_<topic>.md` only when it is reusable, concrete, and likely to help many future runs. | Skill distillation with a promotion threshold: only stable, broadly useful techniques become procedural knowledge. | [Wiki: Procedural knowledge](https://en.wikipedia.org/wiki/Procedural_knowledge)<br>[Paper: Voyager (skill library for open-ended agents)](https://arxiv.org/abs/2305.16291) |
| SELECTION: keep candidates (git commit patches) with better results.                                          | Selection pressure: keep only the strictly better candidate; reset otherwise.                               | [Wiki: Selection (evolutionary algorithm)](https://en.wikipedia.org/wiki/Selection_(evolutionary_algorithm))<br>[Wiki: Hill climbing](https://en.wikipedia.org/wiki/Hill_climbing)                                                                                              |
| CONSTRAINTS: work only inside this repo; never scan outside it.                                               | Feasible region and hard constraints: defines the boundary within which all solutions must remain valid.    | [Wiki: Feasible region](https://en.wikipedia.org/wiki/Feasible_region)<br>[Wiki: Constraint satisfaction problem](https://en.wikipedia.org/wiki/Constraint_satisfaction_problem)                                                                                                |

Taken together, the PLAN is a compact search loop with layered memory: define the problem and objective, load active memory first, retrieve relevant prior episodes and skills, avoid known dead ends, spend most effort on local refinement with a small mutation budget, force one critique pass, write back a compressed case, update the current summary, distill durable skills, then keep only candidates that clear the acceptance bar and satisfy hard constraints.

## Tiered Memory

PSP works best with a tiered memory model: keep the full timestamped timeline, but promote only the parts that deserve broader reuse.

| Tier | Artifact | When to write or update | Retention | Reuse scope | Memory type |
| --- | --- | --- | --- | --- | --- |
| 1 | `agent_<timestamp>_<topic>_memory.md` | Write after each successful run to preserve the detailed episode. | Long | Narrow, run-specific | Episodic |
| 2 | `CURRENT_MEMORY.md` | Update when a lesson is likely to help the next few runs in this repo. | Medium | Repo-wide, near-term | Active |
| 3 | `skill_<topic>.md` | Create or update when a lesson becomes a reusable technique, not just a one-off observation. | Long | Broad, many future agents | Procedural |
| 4 | `FAILED_PATHS.md` | Append when a failure pattern is clear enough that future runs should avoid repeating it. | Medium to long | Repo-wide avoidance | Negative |
| 5 | `results.tsv` | The runner appends one row per generation or member outcome with a compact status and note. | Medium | Repo-wide audit trail | Ledger |
| Promotion rule | All tiers | Never promote memory automatically; promotion should always require judgment. | Always | Applies to every tier | Governance |


## Tips

### Running

**🔹 Start small.** Use `--generations 2` for a first run to check that the agent reads the plan and produces sensible output before committing to a long loop.

**👀 Watch live output.** Add `--stdout inherit` to print agent output directly to the terminal instead of discarding it, useful when debugging a new plan.

**🔎 Inspect the effective plan.** When a goal is piped in, the script writes a `plan.tmp.<id>` file (built-in template) or `<plan>.tmp.<id>` file (explicit plan) in the repo for the duration of the run. Open it to confirm the `GOAL:` line and the full policy before the first generation finishes.

**🧪 Preview without running.** `--dry-run` prints the resolved agent command and exits, useful for checking `--agent-bin` / `--agent-args` overrides without invoking the agent.

**🎯 Pipe goals for targeted experiments.** Keep one canonical `plan.txt` and vary the objective via stdin. Each run gets its own uniquely named temp file so parallel or sequential experiments stay traceable.

**✍️ Edit the plan on the fly.** You can often revise `plan.txt` mid-run and let the next generation pick up the new instructions automatically. Because the script invokes the agent once per generation, changes take effect at the next generation boundary without restarting the whole loop. In practice, this feels a bit like steering an active Codex session, but through the plan file.

**⏱️ Time budget (`--time-budget`).** Caps the total wall-clock run time. The loop exits cleanly before starting a generation that would exceed the budget, so runs are always comparable and predictable. Useful for overnight experiments or CI pipelines with a hard time limit:

```bash
echo "reduce lines of code" | ./psp --time-budget 3600   # stop after 1 hour
```

**💸 Token budget.** Long runs with capable models burn tokens quickly. Set `--generations` conservatively (6–10) and increase only when earlier generations show consistent improvement. With `-jN`, each generation multiplies token spend by N, so start with `-j2` before going wider.

**⚠️ Unblocking agents (use with caution).** When system restrictions or access controls prevent the agent from proceeding, `--yolo` selects the unsafe preset for supported agents:

```bash
# codex: bypass system restrictions and access controls
./planselfplay.sh --yolo --plan plan.txt

# claude: bypass permission checks
./planselfplay.sh --agent claude --yolo --plan plan.txt
```

`opencode` currently ignores `--yolo` and prints a warning.

> [!WARNING]
> These flags remove every guardrail. The agent will run destructive commands without asking. Useful for keeping long runs unblocked, but commit your work and use a throwaway branch first. There could be no undo.

### Memory

**🧱 Dead ends (`FAILED_PATHS.md`).** The plan instructs agents to read `FAILED_PATHS.md` before designing and to append any abandoned approach with a one-line reason. This prevents the same dead-end being re-tried in generation 7 that already failed in generation 2. The file is plain text, human-editable, and rescued alongside skill and memory files in conflict scenarios.

**🧠 Current memory (`CURRENT_MEMORY.md`).** Use this as the compact front door for repo-specific lessons that should help the next few generations. Keep it short and curated. Timestamped `agent_*.md` files remain the detailed timeline; `CURRENT_MEMORY.md` is the active summary layer that future runs should read first.

**🛠️ Skills (`skill_*.md`).** Promote a lesson into a skill only when it is reusable, concrete, and likely to help many future runs, not when it is just a one-off repo quirk or a trick that worked once. Patch an existing skill when refining the same technique; create a new skill only for a genuinely different technique. Keep each skill short, actionable, and low-duplication. Future generations read all `skill_*.md` files at the start of each run via `APPLY SKILLS` and build on accumulated know-how rather than re-deriving it. Skills are tracked in git like any other file. In `-jN` mode, skill files are rescued alongside `agent_*.md` memory files even when code conflicts prevent a full merge.

**📒 Results ledger (`results.tsv`).** The runner maintains a tab-separated ledger with `timestamp_utc`, `generation`, `member`, `status`, `commit`, and `note`. This keeps the run history machine-friendly without hiding it behind a database. Use it as the compact audit trail; keep richer explanations in memory files.

### Parallelism

**⚡ Population (`-jN`).** Runs N agents in parallel per generation. Each member gets its own git worktree and branch so agents never race. After all members finish, their work is automatically merged back into the main branch using a three-tier cascade: (1) octopus merge when all branches are conflict-free, (2) sequential per-branch merge otherwise, (3) `-X ours` fallback for stubborn conflicts. Knowledge artifacts such as `agent_*.md`, `CURRENT_MEMORY.md`, `skill_*.md`, and `FAILED_PATHS.md` are always rescued and committed even when code conflicts prevent a full merge. Branches that produced no commits are dropped silently.

## Inspiration

This project is inspired by `karpathy/autoresearch`. The difference here is the
deliberate commitment to plain-text control and a small shell loop, so the
pattern stays easy to inspect, fork, and modify.

## License

Released under the MIT License. See [LICENSE](LICENSE).
