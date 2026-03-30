#!/usr/bin/env bash
set -euo pipefail
agent="${AGENT:-codex}"
plan_path="${PLAN_PATH:-${PWD}/plan.example.txt}"
plan_explicit=0; [[ -n "${PLAN_PATH:-}" ]] && plan_explicit=1
agent_bin=""
agent_args_text=""
goal_text="${GOAL:-}"
generations="${GENERATIONS:-10}"
population="${POPULATION:-1}"
sleep_seconds="${SLEEP_SECONDS:-2}"
time_budget="${TIME_BUDGET:-0}"
stdout_mode="${STDOUT_MODE:-discard}"
dry_run="${DRY_RUN:-0}"
plan_seen=0
init_plan_path=""
yolo_mode=0
results_path=""

quit() { printf '%s\n' "$*" >&2; exit 1; }
arg() { [[ $# -ge 2 && -n "${2:-}" ]] || quit "Missing value for $1"; printf '%s\n' "$2"; }
set_plan() { (( plan_seen == 0 )) || quit "Provide the plan path once"; plan_seen=1; plan_explicit=1; plan_path="$1"; }
ensure_results_ledger() {
  [[ -n "$results_path" ]] || return 0
  if [[ ! -e "$results_path" ]]; then
    printf 'timestamp_utc\tgeneration\tmember\tstatus\tcommit\tnote\n' > "$results_path"
  fi
}
append_result() {
  [[ -n "$results_path" ]] || return 0
  local generation="$1" member="$2" status="$3" commit="$4" note="$5" timestamp
  ensure_results_ledger
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$timestamp" "$generation" "$member" "$status" "${commit:--}" "$note" >> "$results_path"
}
archive_parallel_branch() {
  local branch="$1" timestamp backup_branch
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_branch="psp/stale/${timestamp}-${branch#psp/}"
  git show-ref --verify --quiet "refs/heads/$backup_branch" && backup_branch="${backup_branch}-$$"
  git branch -m "$branch" "$backup_branch" >/dev/null 2>&1 \
    || quit "Could not archive stale parallel branch: $branch"
  printf 'PLANSELFPLAY | preserved stale branch as %s\n' "$backup_branch"
}
prepare_parallel_slot() {
  local branch="$1" path="$2" ahead=0
  git worktree remove --force "$path" 2>/dev/null || true
  if git show-ref --verify --quiet "refs/heads/$branch"; then
    ahead=$(git rev-list HEAD.."$branch" --count 2>/dev/null || echo 0)
    if (( ahead > 0 )); then
      archive_parallel_branch "$branch"
      return
    fi
    git branch -D "$branch" >/dev/null 2>&1 \
      || quit "Could not clear stale parallel branch: $branch"
  fi
}
usage() {
  cat <<EOF
Usage: ${0##*/} [options] [plan-path]
Replay a pure-text PLAN through a coding agent (codex, claude, or opencode).

Options:
  --agent codex|claude|opencode, -a  Coding agent to use (default: codex)
  --plan PATH, -p                    Plan file to replay
  --init-plan [PATH], -i             Write a starter plan file and exit (default: plan.example.txt)
  --yolo                             Use the unsafe permission-bypass preset for the selected agent
  --goal TEXT, -G                    Replace the GOAL: line in the plan with this text
  --generations N, -g                Positive integer (default: 10)
  --population N, -jN                Parallel agents per generation (default: 1)
  --sleep SECONDS, -s                Non-negative delay between generations
  --time-budget SECONDS, -t          Stop after this many wall-clock seconds (0 = no limit)
  --stdout discard|inherit, -o       Agent stdout handling
  --agent-bin PATH                   Agent executable override
  --agent-args STRING, -x            Full agent args override (replaces preset defaults)
  --dry-run                          Print the resolved command and exit
  -h, --help                         Show this help text

Agent presets (overridable via --agent-args):
  codex     -> codex --full-auto exec -
  claude    -> claude -p -
  opencode  -> opencode run -

Environment: AGENT PLAN_PATH GOAL AGENT_BIN AGENT_ARGS GENERATIONS POPULATION SLEEP_SECONDS TIME_BUDGET STDOUT_MODE DRY_RUN
             (legacy: CODEX_BIN CODEX_ARGS map to AGENT_BIN AGENT_ARGS for codex)
EOF
}

# Built-in ML-style plan template; used by --goal when no --plan is given.
# Update this function to change the default agent policy.
builtin_plan_template() {
  cat <<PLAN_TEMPLATE
DOMAIN: the current working directory and its contents.

GOAL: $1

LEARN FROM CURRENT MEMORY: read CURRENT_MEMORY.md first if it exists.

LEARN FROM PREVIOUS RUNS: read any local agent_*.md notes that seem relevant before changing anything so you extend the existing trajectory instead of restarting it.

APPLY SKILLS: before designing, read any skill_*.md files in this repo and apply relevant ones to your approach.

DEAD ENDS: before designing, read FAILED_PATHS.md if it exists and never re-try any listed approach. When you abandon an approach, append it to FAILED_PATHS.md with a one-line reason.

STRATEGY: use a 90%/10% probability split between refining the strongest current path and testing one mutation that could outperform it.

RETHINK: after the first design, pause and say exactly "Wait, let me rethink, how can I do this differently." Then improve the design based on rethink.

AT TASK COMPLETION: if the repo explicitly allows report files, write a UTC-timestamped agent_<topic>_memory.md with decisions, failed ideas, metrics, and reusable lessons.

RESULTS LEDGER: the runner maintains results.tsv as a tab-separated run ledger with timestamp, generation, member, status, commit, and note.

UPDATE CURRENT MEMORY: if this run produced a lesson likely to help upcoming runs in this repo, merge it into CURRENT_MEMORY.md in concise form.

WRITE SKILLS: promote a lesson into skill_<topic>.md only when it is reusable, concrete, and likely to help many future runs. Do not create a skill for a one-off repo quirk, a weak hunch, or a trick that succeeded only once.

SKILL HYGIENE: patch an existing skill when refining the same technique; create a new skill only for a genuinely different technique. Keep skills short, actionable, and low-duplication.

SELECTION:
- if the result is clearly better, create a local git commit whose message says what changed and what improved
- otherwise, \`git reset\` the repo to its pre-task state

CONSTRAINTS: work only inside this repo; never scan outside it; wrap every \`find\`, \`rg\`, or \`grep\` with \`timeout\` no longer than 10 minutes; prefer reversible edits; treat protected control files (such as PLAN files) as fixed unless the goal explicitly puts them in scope.
PLAN_TEMPLATE
}

while (( $# )); do
  case "$1" in
    -h|--help)    usage; exit 0 ;;
    --dry-run)    dry_run=1 ;;
    -a|--agent)      agent="$(arg "$@")"; shift ;;
    -p|--plan)       set_plan "$(arg "$@")"; shift ;;
    -i|--init-plan)
      if [[ $# -ge 2 && "${2:-}" != -* ]]; then
        init_plan_path="$2"
        shift
      else
        init_plan_path="plan.example.txt"
      fi
      ;;
    --yolo)       yolo_mode=1 ;;
    -G|--goal)       goal_text="$(arg "$@")"; shift ;;
    -g|--generations) generations="$(arg "$@")"; shift ;;
    -g*)           generations="${1#-g}" ;;
    --population)  population="$(arg "$@")"; shift ;;
    -j)            population="$(arg "$@")"; shift ;;
    -j*)           population="${1#-j}" ;;
    -s|--sleep)      sleep_seconds="$(arg "$@")"; shift ;;
    -t|--time-budget) time_budget="$(arg "$@")"; shift ;;
    -o|--stdout)     stdout_mode="$(arg "$@")"; shift ;;
    --agent-bin|--codex-bin)  agent_bin="$(arg "$@")"; shift ;;
    -x|--agent-args|--codex-args) agent_args_text="$(arg "$@")"; shift ;;
    --) shift; (( $# )) || quit "Missing plan path after --"; set_plan "$1" ;;
    -*) usage >&2; quit "Unknown option: $1" ;;
    *) set_plan "$1" ;;
  esac
  shift
done

if [[ -n "$init_plan_path" ]]; then
  if [[ -e "$init_plan_path" ]]; then
    quit "Refusing to overwrite existing file: $init_plan_path"
  fi
  builtin_plan_template "describe the improvement you want here" > "$init_plan_path"
  printf 'Wrote starter plan to %s\n' "$init_plan_path"
  exit 0
fi

# Apply agent presets (explicit --agent-bin / --agent-args flags take precedence)
case "$agent" in
  codex)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-${CODEX_BIN:-codex}}"
    if [[ -z "$agent_args_text" ]]; then
      if (( yolo_mode == 1 )); then
        agent_args_text="--yolo exec -"
      else
        agent_args_text="${AGENT_ARGS:-${CODEX_ARGS:---full-auto exec -}}"
      fi
    fi
    ;;
  claude)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-claude}"
    if [[ -z "$agent_args_text" ]]; then
      if (( yolo_mode == 1 )); then
        agent_args_text="-p --dangerously-skip-permissions -"
      else
        agent_args_text="${AGENT_ARGS:--p -}"
      fi
    fi
    ;;
  opencode)
    [[ -n "$agent_bin" ]]       || agent_bin="${AGENT_BIN:-opencode}"
    if [[ -z "$agent_args_text" ]]; then
      agent_args_text="${AGENT_ARGS:-run -}"
    fi
    if (( yolo_mode == 1 )); then
      printf '%s\n' "PLANSELFPLAY WARNING | --yolo is not supported for opencode; continuing with the normal preset" >&2
    fi
    ;;
  *) quit "Unknown agent: $agent. Valid values: codex, claude, opencode" ;;
esac

# Skip plan-file validation when --goal supplies the goal and no explicit --plan was given
if [[ -z "$goal_text" || "$plan_explicit" == 1 ]]; then
  [[ -n "$plan_path" && -r "$plan_path" ]] || quit "Plan file is not readable: $plan_path"
fi
[[ "$generations" =~ ^[1-9][0-9]*$ ]] || quit "GENERATIONS must be a positive integer: $generations"
[[ "$population" =~ ^[1-9][0-9]*$ ]] || quit "POPULATION must be a positive integer: $population"
[[ "$sleep_seconds" =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]] || quit "SLEEP_SECONDS must be a non-negative number: $sleep_seconds"
[[ "$time_budget" =~ ^[0-9]+$ ]] || quit "TIME_BUDGET must be a non-negative integer (seconds): $time_budget"
[[ "$dry_run" =~ ^[01]$ ]] || quit "DRY_RUN must be 0 or 1: $dry_run"
[[ "$stdout_mode" == discard || "$stdout_mode" == inherit ]] || quit "STDOUT_MODE must be 'discard' or 'inherit': $stdout_mode"
stdout_target=/dev/null
[[ "$stdout_mode" == inherit ]] && stdout_target=/dev/stdout
agent_args=()
[[ -n "$agent_args_text" ]] && read -r -a agent_args <<< "$agent_args_text"
agent_command=("$agent_bin" "${agent_args[@]}")

plan_display="$plan_path"
[[ -n "$goal_text" && "$plan_explicit" == 0 ]] && plan_display="(builtin)"
printf 'PLANSELFPLAY CONFIG | agent=%s | plan=%s | goal=%s | generations=%s | population=%s | sleep=%s | budget=%s | stdout=%s | bin=%s | args=%s\n' \
  "$agent" "$plan_display" "${goal_text:-(none)}" "$generations" "$population" "$sleep_seconds" "${time_budget}s" "$stdout_mode" "$agent_bin" "$agent_args_text"
if [[ "$dry_run" == 1 ]]; then
  printf 'PLANSELFPLAY DRY RUN |'; printf ' %q' "${agent_command[@]}"
  [[ "$plan_display" == "(builtin)" ]] && printf ' < <(builtin_plan_template %q)\n' "$goal_text" \
    || printf ' < %q\n' "$plan_path"
  exit 0
fi

command -v "$agent_bin" >/dev/null 2>&1 || quit "Required command not found on PATH: $agent_bin"

# Resolve plan_path to absolute so agents running in worktrees can still read it
[[ "$plan_path" = /* ]] || plan_path="${PWD}/${plan_path}"

tmp_plan=""
effective_plan="$plan_path"
if [[ -n "$goal_text" && "$plan_explicit" == 0 ]]; then
  # No explicit plan: generate from the built-in ML-style template
  tmp_plan=$(mktemp "${PWD}/plan.tmp.XXXXXX")
  builtin_plan_template "$goal_text" > "$tmp_plan"
  effective_plan="$tmp_plan"
elif [[ -n "$goal_text" ]]; then
  # Explicit plan: substitute the GOAL: line
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
if [[ -n "$repo_root" ]]; then
  results_path="${repo_root}/results.tsv"
else
  results_path="${PWD}/results.tsv"
fi
ensure_results_ledger

trap '[[ -n "$tmp_plan" ]] && rm -f "$tmp_plan"; [[ -n "$repo_root" ]] && { git worktree prune -q 2>/dev/null || true; rm -rf "${repo_root}/.psp"; }' EXIT

psp_start_time=$SECONDS
for ((generation=1; generation<=generations; generation++)); do
  if (( time_budget > 0 && SECONDS - psp_start_time >= time_budget )); then
    printf 'PLANSELFPLAY | time budget of %ds reached before generation %d/%d, stopping\n' \
      "$time_budget" "$generation" "$generations"
    break
  fi
  generation_start="$(git rev-parse HEAD 2>/dev/null || printf 'nogit')"
  pids=()
  for ((member=1; member<=population; member++)); do
    printf 'PLANSELFPLAY %d/%d [%d/%d] | agent=%s | plan=%s | bin=%s | args=%s\n' \
      "$generation" "$generations" "$member" "$population" "$agent" "$plan_display" "$agent_bin" "$agent_args_text"
    if (( population > 1 )); then
      wt_branch="psp/gen${generation}-m${member}"
      wt_path="${repo_root}/.psp/gen${generation}-m${member}"
      prepare_parallel_slot "$wt_branch" "$wt_path"
      git worktree add -q -b "$wt_branch" "$wt_path" HEAD
      (cd "$wt_path" && "${agent_command[@]}" < "$effective_plan" > "$stdout_target") &
    else
      "${agent_command[@]}" < "$effective_plan" > "$stdout_target" &
    fi
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
  if (( population > 1 )); then
    # Remove worktree paths first so branches are free to merge
    for ((member=1; member<=population; member++)); do
      git worktree remove --force "${repo_root}/.psp/gen${generation}-m${member}" 2>/dev/null || true
    done
    # Collect branches that produced new commits
    active_branches=()
    for ((member=1; member<=population; member++)); do
      wt_branch="psp/gen${generation}-m${member}"
      new_commits=$(git rev-list HEAD.."${wt_branch}" --count 2>/dev/null || echo 0)
      if (( new_commits > 0 )); then
        active_branches+=("$wt_branch")
      else
        printf 'PLANSELFPLAY %d/%d [%d/%d] | no new commits\n' \
          "$generation" "$generations" "$member" "$population"
        append_result "$generation" "$member" "no_commit" "-" "no new commits"
        git branch -D "${wt_branch}" 2>/dev/null || true
      fi
    done
    if (( ${#active_branches[@]} == 0 )); then
      printf 'PLANSELFPLAY %d/%d | no members produced commits\n' "$generation" "$generations"
    elif (( ${#active_branches[@]} > 1 )) && \
         git merge --no-ff -m "psp: octopus merge gen${generation} [$(IFS=,; echo "${active_branches[*]/#*-/}")]" "${active_branches[@]}" >/dev/null 2>&1; then
      # Tier 1: octopus merge — all branches, no conflicts
      printf 'PLANSELFPLAY %d/%d | octopus: merged all %d active branches\n' \
        "$generation" "$generations" "${#active_branches[@]}"
      for wt_branch in "${active_branches[@]}"; do
        member_num="${wt_branch##*-m}"
        member_head="$(git rev-parse "${wt_branch}" 2>/dev/null || printf '-')"
        append_result "$generation" "$member_num" "merged_octopus" "$member_head" "merged via octopus"
        git branch -D "${wt_branch}" 2>/dev/null || true
      done
    else
      git merge --abort 2>/dev/null || true
      # Tier 2: sequential per-branch merge, with -X ours fallback (Tier 3) on conflict
      for wt_branch in "${active_branches[@]}"; do
        member_num="${wt_branch##*-m}"
        new_commits=$(git rev-list HEAD.."${wt_branch}" --count 2>/dev/null || echo 0)
        if (( new_commits == 0 )); then
          git branch -D "${wt_branch}" 2>/dev/null || true
        elif git merge --no-ff -m "psp: merge [psp:gen${generation}-m${member_num}]" "${wt_branch}" >/dev/null 2>&1; then
          printf 'PLANSELFPLAY %d/%d [%d/%d] | merged %d commit(s)\n' \
            "$generation" "$generations" "$member_num" "$population" "$new_commits"
          member_head="$(git rev-parse "${wt_branch}" 2>/dev/null || printf '-')"
          append_result "$generation" "$member_num" "merged" "$member_head" "merged ${new_commits} commit(s)"
          git branch -D "${wt_branch}" 2>/dev/null || true
        else
          git merge --abort 2>/dev/null || true
          if git merge --no-ff -m "psp: partial merge [psp:gen${generation}-m${member_num}] (-X ours)" -X ours "${wt_branch}" >/dev/null 2>&1; then
            # Tier 3: ours strategy — non-conflicting hunks taken, main wins conflicts
            printf 'PLANSELFPLAY %d/%d [%d/%d] | partial merge (-X ours, %d commit(s))\n' \
              "$generation" "$generations" "$member_num" "$population" "$new_commits"
            member_head="$(git rev-parse "${wt_branch}" 2>/dev/null || printf '-')"
            append_result "$generation" "$member_num" "partial_merge" "$member_head" "merged with -X ours (${new_commits} commit(s))"
            git branch -D "${wt_branch}" 2>/dev/null || true
          else
            git merge --abort 2>/dev/null || true
            # Last resort: rescue knowledge artifacts
            printf 'PLANSELFPLAY %d/%d [%d/%d] | conflict, rescuing memory (branch kept: %s)\n' \
              "$generation" "$generations" "$member_num" "$population" "${wt_branch}"
            while IFS= read -r f; do
              [[ -z "$f" ]] && continue
              git show "${wt_branch}:${f}" > "${repo_root}/${f}" 2>/dev/null || true
            done < <(git diff --name-only HEAD "${wt_branch}" -- 'agent_*.md' 'skill_*.md' 'FAILED_PATHS.md' 'CURRENT_MEMORY.md' 2>/dev/null)
            git add -- 'agent_*.md' 'skill_*.md' 'FAILED_PATHS.md' 'CURRENT_MEMORY.md' 2>/dev/null || true
            git diff --cached --quiet \
              || git commit -m "psp: rescue knowledge artifacts from gen${generation}-m${member_num} (conflict)"
            member_head="$(git rev-parse "${wt_branch}" 2>/dev/null || printf '-')"
            append_result "$generation" "$member_num" "rescued" "$member_head" "code conflict; rescued knowledge artifacts"
          fi
        fi
      done
    fi
  else
    generation_end="$(git rev-parse HEAD 2>/dev/null || printf 'nogit')"
    if [[ "$generation_end" == "$generation_start" ]]; then
      append_result "$generation" "1" "no_commit" "-" "no new commit"
    else
      append_result "$generation" "1" "committed" "$generation_end" "HEAD advanced this generation"
    fi
  fi
  if (( generation < generations )); then sleep "$sleep_seconds"; fi
done
