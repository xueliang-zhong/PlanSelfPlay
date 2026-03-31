#!/usr/bin/env bash
set -euo pipefail

PSP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Defaults ──────────────────────────────────────────────────────────────────
agent="codex"
plan_path="${PWD}/plan.example.txt"
plan_explicit=0; [[ -n "${PLAN_PATH:-}" ]] && plan_explicit=1
agent_bin=""
agent_args_text=""
goal_text=""
generations="10"
sleep_seconds="2"
time_budget="0"
output_mode="discard"
dry_run="0"
plan_seen=0
init_plan_path=""
yolo_mode=0
results_path=""
PSP_DIR="${PSP_DIR:-${HOME}/.psp}"

quit()    { printf '%s\n' "$*" >&2; exit 1; }
arg()     { [[ $# -ge 2 && -n "${2:-}" ]] || quit "Missing value for $1"; printf '%s\n' "$2"; }
set_plan(){ (( plan_seen == 0 )) || quit "Provide the plan path once"; plan_seen=1; plan_explicit=1; plan_path="$1"; }

ensure_results_ledger() {
  [[ -n "$results_path" ]] || return 0
  [[ -e "$results_path" ]] || printf 'timestamp_utc\tgeneration\tstatus\tcommit\tnote\n' > "$results_path"
}
append_result() {
  [[ -n "$results_path" ]] || return 0
  local generation="$1" status="$2" commit="$3" note="$4" timestamp
  ensure_results_ledger
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\t%s\t%s\t%s\t%s\n' "$timestamp" "$generation" "$status" "${commit:--}" "$note" >> "$results_path"
}

# Load ~/.psp/config.toml — flat key = value, TOML subset.
# Priority: defaults < config.toml < env vars < CLI flags.
load_config() {
  local cfg="$PSP_DIR/config.toml"
  [[ -f "$cfg" ]] || return 0
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$|\[) ]] && continue
    [[ "$line" =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_-]*)[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$ ]] || continue
    key="${BASH_REMATCH[1]}"; val="${BASH_REMATCH[2]}"
    if   [[ "$val" == '"'* ]]; then val="${val#\"}"; val="${val%%\"*}";
    elif [[ "$val" == "'"* ]]; then val="${val#\'}"; val="${val%%\'*}";
    else val="${val%%[[:space:]]*#*}"; val="${val%"${val##*[! $'\t']}"}"; fi
    case "$key" in
      agent)        agent="$val" ;;
      generations)  generations="$val" ;;
      sleep)        sleep_seconds="$val" ;;
      time_budget)  time_budget="$val" ;;
      output)       output_mode="$val" ;;
      agent_bin)    agent_bin="$val" ;;
      agent_args)   agent_args_text="$val" ;;
      yolo)         [[ "$val" == "true" ]] && yolo_mode=1 ;;
    esac
  done < "$cfg"
}

# Copy bundled skills to ~/.psp/skills/ (skips files that already exist).
write_default_skills() {
  local src_dir="$PSP_SCRIPT_DIR/skills"
  local dst_dir="$PSP_DIR/skills"
  [[ -d "$src_dir" ]] || { printf 'No bundled skills directory found at %s\n' "$src_dir" >&2; return 1; }
  mkdir -p "$dst_dir"
  local copied=0 name src dst
  for src in "$src_dir"/*.md; do
    [[ -e "$src" ]] || continue
    name="${src##*/}"; dst="$dst_dir/$name"
    if [[ -e "$dst" ]]; then
      printf 'Skipping (already exists): %s\n' "$dst"
    else
      cp "$src" "$dst"
      printf 'Installed: %s\n' "$dst"
      (( ++copied )) || true
    fi
  done
  (( copied > 0 )) && printf 'Installed %d skill(s) to %s\n' "$copied" "$dst_dir" \
                   || printf 'All skills already installed in %s\n' "$dst_dir"
}

# Write a starter ~/.psp/config.toml (will not overwrite an existing file).
write_default_config() {
  local cfg="$PSP_DIR/config.toml"
  mkdir -p "$PSP_DIR"
  [[ -e "$cfg" ]] && { printf 'Config already exists: %s\n' "$cfg"; return 1; }
  cat > "$cfg" <<'TOML'
# ~/.psp/config.toml — PSP user defaults
# Priority: this file < environment variables < command-line flags
# All keys are optional; uncomment and edit the ones you want.

# agent       = "codex"       # codex | claude | opencode
# generations = 10            # number of self-play generations
# sleep       = 2             # seconds to pause between generations
# time_budget = 0             # wall-clock cap in seconds (0 = no limit)
# output      = "discard"     # discard | inherit | log  (log = per-generation files in $PWD)
# agent_bin   = ""            # override the agent executable path
# agent_args  = ""            # override the full agent argument string
# yolo        = false         # true = pass --yolo / --dangerously-skip-permissions
TOML
  printf 'Wrote default config to %s\n' "$cfg"
}

# Append one line to ~/.psp/history per run.
append_history() {
  mkdir -p "$PSP_DIR"
  printf '%s\t%s\t%s\tg=%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$agent" "$PWD" "$generations" \
    "${goal_text:-(plan: ${plan_display})}" \
    >> "$PSP_DIR/history"
}

usage() {
  cat <<EOF
Usage: ${0##*/} [options] [plan-path]
       echo "GOAL" | ${0##*/} [options]
Replay a pure-text PLAN through a coding agent (codex, claude, or opencode).
When stdin is a pipe the goal is read from it; a plan file is optional.

Options:
  --agent codex|claude|opencode, -a  Coding agent to use (default: codex)
  --plan PATH, -p                    Plan file to replay
  --init-plan [PATH], -i             Write a starter plan file and exit (default: plan.example.txt)
  --init-config                      Write a starter ~/.psp/config.toml and exit
  --init-skills                      Install bundled skills into ~/.psp/skills/ and exit
  --yolo                             Use the unsafe permission-bypass preset for the selected agent
  --generations N, -g                Positive integer (default: 10)
  --sleep SECONDS, -s                Non-negative delay between generations
  --time-budget SECONDS, -t          Stop after this many wall-clock seconds (0 = no limit)
  --output discard|inherit|log, -o   Agent output handling (log = per-generation files)
  --agent-bin PATH                   Agent executable override
  --agent-args STRING, -x            Full agent args override (replaces preset defaults)
  --dry-run                          Print the resolved command and exit
  --history                          Print ~/.psp/history and exit (pipe through fzf | psp to re-run)
  -h, --help                         Show this help text

Agent presets (overridable via --agent-args):
  codex     -> codex --full-auto exec -
  claude    -> claude -p -
  opencode  -> opencode run -

Config:      ~/.psp/config.toml  (key = value defaults, lowest priority)
             ~/.psp/history      (append-only run log; browse with --history)
             ~/.psp/skills/      (pre-installed skill files; injected into every plan)
Environment: AGENT PLAN_PATH GOAL AGENT_BIN AGENT_ARGS GENERATIONS SLEEP_SECONDS TIME_BUDGET OUTPUT_MODE DRY_RUN
             (legacy: CODEX_BIN CODEX_ARGS map to AGENT_BIN AGENT_ARGS for codex)
EOF
}

# Built-in ML-style plan template; used when goal is piped via stdin and no --plan is given.
# Update this function to change the default agent policy.
builtin_plan_template() {
  # Build the list of pre-installed skills from ~/.psp/skills/ to inject into the plan.
  local psp_skills_note=""
  if [[ -d "$PSP_DIR/skills" ]]; then
    local -a _sf=()
    while IFS= read -r _f; do _sf+=("$_f"); done < <(ls -1 "$PSP_DIR/skills"/*.md 2>/dev/null || true)
    if (( ${#_sf[@]} > 0 )); then
      psp_skills_note=$'\n  PSP pre-installed skills (also read these):\n'
      for _f in "${_sf[@]}"; do psp_skills_note+="    $_f"$'\n'; done
    fi
  fi
  cat <<PLAN_TEMPLATE
DOMAIN: the current working directory and its contents.

GOAL: $1

LEARN FROM CURRENT MEMORY: read CURRENT_MEMORY.md first if it exists.

LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes that seem relevant before changing anything so you extend the existing trajectory instead of restarting it.

APPLY SKILLS: before designing, read any skill_*.md files in this repo and apply relevant ones to your approach.${psp_skills_note}
DEAD ENDS: before designing, read FAILED_PATHS.md if it exists and never re-try any listed approach. When you abandon an approach, append it to FAILED_PATHS.md with a one-line reason.

STRATEGY: use a 90%/10% probability split between refining the strongest current path and testing one mutation that could outperform it.

RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently." Then improve the design based on rethink.

AT TASK COMPLETION: if the repo explicitly allows report files, write a UTC-timestamped agent_<topic>_memory.md with decisions, failed ideas, metrics, and reusable lessons.

RESULTS LEDGER: the runner maintains results.tsv as a tab-separated run ledger with timestamp, generation, status, commit, and note.

UPDATE CURRENT MEMORY: if this run produced a lesson likely to help upcoming runs in this repo, merge it into CURRENT_MEMORY.md in concise form.

WRITE SKILLS: promote a lesson into skill_<topic>.md only when it is reusable, concrete, and likely to help many future runs. Do not create a skill for a one-off repo quirk, a weak hunch, or a trick that succeeded only once.

SKILL HYGIENE: patch an existing skill when refining the same technique; create a new skill only for a genuinely different technique. Keep skills short, actionable, and low-duplication.

SELECTION:
- if the result is clearly better, create a local git commit whose message says what changed and what improved
- otherwise, \`git reset\` the repo to its pre-task state

CONSTRAINTS: work only inside this repo; never scan outside it; wrap every \`find\`, \`rg\`, or \`grep\` with \`timeout\` no longer than 10 minutes; prefer reversible edits; treat protected control files (such as PLAN files) as fixed unless the goal explicitly puts them in scope.
PLAN_TEMPLATE
}

# ── Config file then env vars (env vars win over config.toml) ─────────────────
load_config
agent="${AGENT:-$agent}"
goal_text="${GOAL:-$goal_text}"
generations="${GENERATIONS:-$generations}"
sleep_seconds="${SLEEP_SECONDS:-$sleep_seconds}"
time_budget="${TIME_BUDGET:-$time_budget}"
output_mode="${OUTPUT_MODE:-$output_mode}"
dry_run="${DRY_RUN:-$dry_run}"
[[ -n "${PLAN_PATH:-}" ]] && { plan_path="$PLAN_PATH"; plan_explicit=1; }

while (( $# )); do
  case "$1" in
    -h|--help)       usage; exit 0 ;;
    --init-config)   write_default_config; exit $? ;;
    --init-skills)   write_default_skills; exit $? ;;
    --history)
      [[ -f "$PSP_DIR/history" ]] || { printf 'No history yet.\n' >&2; exit 0; }
      cut -f5 "$PSP_DIR/history"; exit 0 ;;
    --dry-run)       dry_run=1 ;;
    -a|--agent)      agent="$(arg "$@")"; shift ;;
    -p|--plan)       set_plan "$(arg "$@")"; shift ;;
    -i|--init-plan)
      if [[ $# -ge 2 && "${2:-}" != -* ]]; then init_plan_path="$2"; shift
      else init_plan_path="plan.example.txt"; fi ;;
    --yolo)          yolo_mode=1 ;;
    -g|--generations) generations="$(arg "$@")"; shift ;;
    -g*)             generations="${1#-g}" ;;
    -s|--sleep)      sleep_seconds="$(arg "$@")"; shift ;;
    -t|--time-budget) time_budget="$(arg "$@")"; shift ;;
    -o|--output)     output_mode="$(arg "$@")"; shift ;;
    --agent-bin|--codex-bin)      agent_bin="$(arg "$@")"; shift ;;
    -x|--agent-args|--codex-args) agent_args_text="$(arg "$@")"; shift ;;
    --) shift; (( $# )) || quit "Missing plan path after --"; set_plan "$1" ;;
    -*) usage >&2; quit "Unknown option: $1" ;;
    *)  set_plan "$1" ;;
  esac
  shift
done

# Read goal from stdin.
#   Piped:       echo "improve tests" | psp   — read silently
#   Interactive: ./psp with no plan/goal      — show "Goal: " prompt
if [[ ! -t 0 ]]; then
  stdin_goal=$(cat)
  # If it looks like a history entry, extract the goal (last field).
  if [[ "$stdin_goal" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'\t'[^$'\t']*$'\t'[^$'\t']*$'\t'g=[^$'\t']*$'\t'(.*) ]]; then
    stdin_goal="${BASH_REMATCH[1]}"
  fi
  [[ -n "$stdin_goal" ]] && goal_text="$stdin_goal"
elif [[ -z "$goal_text" && "$plan_explicit" == 0 ]]; then
  printf 'Goal: ' >&2
  IFS= read -r goal_text </dev/tty
  [[ -n "$goal_text" ]] || quit "No goal provided"
fi

if [[ -n "$init_plan_path" ]]; then
  [[ -e "$init_plan_path" ]] && quit "Refusing to overwrite existing file: $init_plan_path"
  builtin_plan_template "describe the improvement you want here" > "$init_plan_path"
  printf 'Wrote starter plan to %s\n' "$init_plan_path"
  exit 0
fi

# Apply agent presets (explicit --agent-bin / --agent-args flags take precedence)
case "$agent" in
  codex)
    [[ -n "$agent_bin" ]] || agent_bin="${AGENT_BIN:-${CODEX_BIN:-codex}}"
    if [[ -z "$agent_args_text" ]]; then
      (( yolo_mode )) && agent_args_text="--yolo exec -" \
                      || agent_args_text="${AGENT_ARGS:-${CODEX_ARGS:---full-auto exec -}}"
    fi ;;
  claude)
    [[ -n "$agent_bin" ]] || agent_bin="${AGENT_BIN:-claude}"
    if [[ -z "$agent_args_text" ]]; then
      (( yolo_mode )) && agent_args_text="-p --dangerously-skip-permissions -" \
                      || agent_args_text="${AGENT_ARGS:--p -}"
    fi ;;
  opencode)
    [[ -n "$agent_bin" ]] || agent_bin="${AGENT_BIN:-opencode}"
    [[ -z "$agent_args_text" ]] && agent_args_text="${AGENT_ARGS:-run -}"
    (( yolo_mode )) && printf 'PSP WARNING | --yolo is not supported for opencode; ignored\n' >&2 ;;
  *) quit "Unknown agent: $agent. Valid values: codex, claude, opencode" ;;
esac

# Validate
if [[ -z "$goal_text" || "$plan_explicit" == 1 ]]; then
  [[ -n "$plan_path" && -r "$plan_path" ]] || quit "Plan file is not readable: $plan_path"
fi
[[ "$generations"   =~ ^[1-9][0-9]*$ ]]                        || quit "GENERATIONS must be a positive integer: $generations"
[[ "$sleep_seconds" =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]]    || quit "SLEEP_SECONDS must be a non-negative number: $sleep_seconds"
[[ "$time_budget"   =~ ^[0-9]+$ ]]                             || quit "TIME_BUDGET must be a non-negative integer (seconds): $time_budget"
[[ "$dry_run"       =~ ^[01]$ ]]                               || quit "DRY_RUN must be 0 or 1: $dry_run"
[[ "$output_mode" == discard || "$output_mode" == inherit || "$output_mode" == log ]] \
  || quit "OUTPUT_MODE must be 'discard', 'inherit', or 'log': $output_mode"
output_target=/dev/null; [[ "$output_mode" == inherit ]] && output_target=/dev/stdout
agent_args=(); [[ -n "$agent_args_text" ]] && read -r -a agent_args <<< "$agent_args_text"
agent_command=("$agent_bin" "${agent_args[@]}")

plan_display="$plan_path"
[[ -n "$goal_text" && "$plan_explicit" == 0 ]] && plan_display="(builtin)"
printf 'PSP Step | plan: %s | goal: %s | agent: %s | generations: %s\n' \
  "$plan_display" "${goal_text:-(none)}" "$agent" "$generations"
if [[ "$dry_run" == 1 ]]; then
  printf 'PSP DRY RUN |'; printf ' %q' "${agent_command[@]}"
  [[ "$plan_display" == "(builtin)" ]] && printf ' < <(builtin_plan_template %q)\n' "$goal_text" \
                                       || printf ' < %q\n' "$plan_path"
  exit 0
fi

command -v "$agent_bin" >/dev/null 2>&1 || quit "Required command not found on PATH: $agent_bin"
[[ "$plan_path" = /* ]] || plan_path="${PWD}/${plan_path}"

tmp_plan=""
effective_plan="$plan_path"
if [[ -n "$goal_text" && "$plan_explicit" == 0 ]]; then
  tmp_plan=$(mktemp "${PWD}/plan.tmp.XXXXXX")
  builtin_plan_template "$goal_text" > "$tmp_plan"
  effective_plan="$tmp_plan"
elif [[ -n "$goal_text" ]]; then
  tmp_plan=$(mktemp "${PWD}/$(basename "${plan_path%.*}").tmp.XXXXXX")
  awk -v goal="$goal_text" '/^GOAL:/{print "GOAL: " goal; next} {print}' "$plan_path" > "$tmp_plan"
  effective_plan="$tmp_plan"
fi

results_path="${PWD}/results.tsv"
ensure_results_ledger
trap '[[ -n "$tmp_plan" ]] && rm -f "$tmp_plan"' EXIT

# For --output log: fix a single run timestamp shared across all generation logs.
run_ts=""
[[ "$output_mode" == log ]] && run_ts="$(date -u +%Y%m%dT%H%M%SZ)"

append_history
psp_start_time=$SECONDS
for ((generation=1; generation<=generations; generation++)); do
  if (( time_budget > 0 && SECONDS - psp_start_time >= time_budget )); then
    printf 'PSP | time budget of %ds reached before generation %d/%d, stopping\n' \
      "$time_budget" "$generation" "$generations"
    break
  fi
  # Resolve output target for this generation.
  gen_output_target="$output_target"
  gen_log_note=""
  if [[ "$output_mode" == log ]]; then
    gen_log_file="${PWD}/psp_${agent}_${run_ts}_gen$(printf '%02d' "$generation").log"
    gen_output_target="$gen_log_file"
    gen_log_note=" → ${gen_log_file##*/}"
  fi
  generation_start="$(git rev-parse HEAD 2>/dev/null || printf 'nogit')"
  printf 'PSP %d/%d | running...%s\n' "$generation" "$generations" "$gen_log_note"
  "${agent_command[@]}" < "$effective_plan" > "$gen_output_target" 2>&1
  generation_end="$(git rev-parse HEAD 2>/dev/null || printf 'nogit')"
  if [[ "$generation_end" == "$generation_start" ]]; then
    append_result "$generation" "no_commit" "-" "no new commit"
    printf 'PSP %d/%d | no commit\n' "$generation" "$generations"
  else
    append_result "$generation" "committed" "$generation_end" "HEAD advanced"
    printf 'PSP %d/%d | committed %s\n' "$generation" "$generations" "${generation_end:0:7}"
  fi
  (( generation < generations )) && sleep "$sleep_seconds"
done
