#!/usr/bin/env bash
set -euo pipefail
agent="${AGENT:-codex}"
plan_path="${PLAN_PATH:-${PWD}/PLAN.example.txt}"
agent_bin=""
agent_args_text=""
goal_text="${GOAL:-}"
generations="${GENERATIONS:-10}"
population="${POPULATION:-1}"
sleep_seconds="${SLEEP_SECONDS:-2}"
stdout_mode="${STDOUT_MODE:-discard}"
dry_run="${DRY_RUN:-0}"
plan_seen=0

quit() { printf '%s\n' "$*" >&2; exit 1; }
arg() { [[ $# -ge 2 && -n "${2:-}" ]] || quit "Missing value for $1"; printf '%s\n' "$2"; }
set_plan() { (( plan_seen == 0 )) || quit "Provide the plan path once"; plan_seen=1; plan_path="$1"; }
usage() {
  cat <<EOF
Usage: ${0##*/} [options] [plan-path]
Replay a pure-text PLAN through a coding agent (codex, claude, or opencode).

Options:
  --agent codex|claude|opencode  Coding agent to use (default: codex)
  --plan PATH                    Plan file to replay
  --goal TEXT                    Replace the GOAL: line in the plan with this text
  --generations N                Positive integer
  --population N, -jN            Parallel agents per generation (default: 1)
  --sleep SECONDS                Non-negative delay between generations
  --stdout discard|inherit       Agent stdout handling
  --agent-bin PATH               Agent executable override
  --agent-args STRING            Full agent args override (replaces preset defaults)
  --dry-run                      Print the resolved command and exit
  -h, --help                     Show this help text

Agent presets (overridable via --agent-args):
  codex     -> codex --full-auto exec -
  claude    -> claude -p -
  opencode  -> opencode run -

Environment: AGENT PLAN_PATH GOAL AGENT_BIN AGENT_ARGS GENERATIONS POPULATION SLEEP_SECONDS STDOUT_MODE DRY_RUN
             (legacy: CODEX_BIN CODEX_ARGS map to AGENT_BIN AGENT_ARGS for codex)
EOF
}

while (( $# )); do
  case "$1" in
    -h|--help)    usage; exit 0 ;;
    --dry-run)    dry_run=1 ;;
    --agent)      agent="$(arg "$@")"; shift ;;
    --plan)       set_plan "$(arg "$@")"; shift ;;
    --goal)       goal_text="$(arg "$@")"; shift ;;
    --generations) generations="$(arg "$@")"; shift ;;
    --population)  population="$(arg "$@")"; shift ;;
    -j)            population="$(arg "$@")"; shift ;;
    -j*)           population="${1#-j}" ;;
    --sleep)      sleep_seconds="$(arg "$@")"; shift ;;
    --stdout)     stdout_mode="$(arg "$@")"; shift ;;
    --agent-bin|--codex-bin)  agent_bin="$(arg "$@")"; shift ;;
    --agent-args|--codex-args) agent_args_text="$(arg "$@")"; shift ;;
    --) shift; (( $# )) || quit "Missing plan path after --"; set_plan "$1" ;;
    -*) usage >&2; quit "Unknown option: $1" ;;
    *) set_plan "$1" ;;
  esac
  shift
done

# Apply agent presets (explicit --agent-bin / --agent-args flags take precedence)
case "$agent" in
  codex)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-${CODEX_BIN:-codex}}"
    [[ -n "$agent_args_text" ]] || agent_args_text="${AGENT_ARGS:-${CODEX_ARGS:---full-auto exec -}}"
    ;;
  claude)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-claude}"
    [[ -n "$agent_args_text" ]] || agent_args_text="${AGENT_ARGS:--p -}"
    ;;
  opencode)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-opencode}"
    [[ -n "$agent_args_text" ]] || agent_args_text="${AGENT_ARGS:-run -}"
    ;;
  *) quit "Unknown agent: $agent. Valid values: codex, claude, opencode" ;;
esac

[[ -n "$plan_path" && -r "$plan_path" ]] || quit "Plan file is not readable: $plan_path"
[[ "$generations" =~ ^[1-9][0-9]*$ ]] || quit "GENERATIONS must be a positive integer: $generations"
[[ "$population" =~ ^[1-9][0-9]*$ ]] || quit "POPULATION must be a positive integer: $population"
[[ "$sleep_seconds" =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]] || quit "SLEEP_SECONDS must be a non-negative number: $sleep_seconds"
[[ "$dry_run" =~ ^[01]$ ]] || quit "DRY_RUN must be 0 or 1: $dry_run"
[[ "$stdout_mode" == discard || "$stdout_mode" == inherit ]] || quit "STDOUT_MODE must be 'discard' or 'inherit': $stdout_mode"
stdout_target=/dev/null
[[ "$stdout_mode" == inherit ]] && stdout_target=/dev/stdout
agent_args=()
[[ -n "$agent_args_text" ]] && read -r -a agent_args <<< "$agent_args_text"
agent_command=("$agent_bin" "${agent_args[@]}")

printf 'PLANSELFPLAY CONFIG | agent=%s | plan=%s | goal=%s | generations=%s | population=%s | sleep=%s | stdout=%s | bin=%s | args=%s\n' \
  "$agent" "$plan_path" "${goal_text:-(none)}" "$generations" "$population" "$sleep_seconds" "$stdout_mode" "$agent_bin" "$agent_args_text"
if [[ "$dry_run" == 1 ]]; then
  printf 'PLANSELFPLAY DRY RUN |'; printf ' %q' "${agent_command[@]}"; printf ' < %q\n' "$plan_path"; exit 0
fi

command -v "$agent_bin" >/dev/null 2>&1 || quit "Required command not found on PATH: $agent_bin"

# Resolve plan_path to absolute so agents running in worktrees can still read it
[[ "$plan_path" = /* ]] || plan_path="${PWD}/${plan_path}"

tmp_plan=""
effective_plan="$plan_path"
if [[ -n "$goal_text" ]]; then
  tmp_plan=$(mktemp "${PWD}/$(basename "${plan_path%.*}").tmp.XXXXXX")
  awk -v goal="$goal_text" '/^GOAL:/{print "GOAL: " goal; next} {print}' "$plan_path" > "$tmp_plan"
  effective_plan="$tmp_plan"
fi

repo_root=""
if (( population > 1 )); then
  git rev-parse --git-dir >/dev/null 2>&1 \
    || quit "POPULATION > 1 requires a git repository; use -j1 outside git repos"
  repo_root=$(git rev-parse --show-toplevel)
fi

trap '[[ -n "$tmp_plan" ]] && rm -f "$tmp_plan"; [[ -n "$repo_root" ]] && { git worktree prune -q 2>/dev/null || true; rm -rf "${repo_root}/.psp"; }' EXIT

for ((generation=1; generation<=generations; generation++)); do
  pids=()
  for ((member=1; member<=population; member++)); do
    printf 'PLANSELFPLAY %d/%d [%d/%d] | agent=%s | plan=%s | bin=%s | args=%s\n' \
      "$generation" "$generations" "$member" "$population" "$agent" "$plan_path" "$agent_bin" "$agent_args_text"
    if (( population > 1 )); then
      wt_branch="psp/gen${generation}-m${member}"
      wt_path="${repo_root}/.psp/gen${generation}-m${member}"
      git worktree add -q -b "$wt_branch" "$wt_path" HEAD
      (cd "$wt_path" && "${agent_command[@]}" < "$effective_plan" > "$stdout_target") &
    else
      "${agent_command[@]}" < "$effective_plan" > "$stdout_target" &
    fi
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
  if (( population > 1 )); then
    for ((member=1; member<=population; member++)); do
      git worktree remove --force "${repo_root}/.psp/gen${generation}-m${member}" 2>/dev/null || true
    done
    printf 'PLANSELFPLAY %d/%d | member branches available: psp/gen%d-m{1..%d}\n' \
      "$generation" "$generations" "$generation" "$population"
  fi
  if (( generation < generations )); then sleep "$sleep_seconds"; fi
done
