#!/usr/bin/env bash
set -euo pipefail
plan_path="${PLAN_PATH:-${PWD}/PLAN.example.txt}"
codex_bin="${CODEX_BIN:-codex}"
codex_args_text="${CODEX_ARGS:---full-auto}"
generations="${GENERATIONS:-10}"
sleep_seconds="${SLEEP_SECONDS:-2}"
stdout_mode="${STDOUT_MODE:-discard}"
dry_run="${DRY_RUN:-0}"
plan_seen=0

die() { printf '%s\n' "$*" >&2; exit 1; }
arg() { [[ $# -ge 2 && -n "${2:-}" ]] || die "Missing value for $1"; printf '%s\n' "$2"; }
set_plan() { (( plan_seen == 0 )) || die "Provide the plan path once"; plan_seen=1; plan_path="$1"; }
usage() {
  cat <<EOF
Usage: ${0##*/} [options] [plan-path]
Replay a pure-text PLAN through \`codex exec -\`.

Options:
  --plan PATH              Plan file to replay
  --generations N          Positive integer
  --sleep SECONDS          Non-negative delay between generations
  --stdout discard|inherit Codex stdout handling
  --codex-bin PATH         Codex executable or wrapper
  --codex-args STRING      Extra args, split on shell whitespace
  --dry-run                Print the resolved command and exit
  -h, --help               Show this help text

Environment: PLAN_PATH CODEX_BIN CODEX_ARGS GENERATIONS SLEEP_SECONDS STDOUT_MODE DRY_RUN
EOF
}

while (( $# )); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --dry-run) dry_run=1 ;;
    --plan) set_plan "$(arg "$@")"; shift ;;
    --generations) generations="$(arg "$@")"; shift ;;
    --sleep) sleep_seconds="$(arg "$@")"; shift ;;
    --stdout) stdout_mode="$(arg "$@")"; shift ;;
    --codex-bin) codex_bin="$(arg "$@")"; shift ;;
    --codex-args) codex_args_text="$(arg "$@")"; shift ;;
    --) shift; (( $# )) || die "Missing plan path after --"; set_plan "$1" ;;
    -*) usage >&2; die "Unknown option: $1" ;;
    *) set_plan "$1" ;;
  esac
  shift
done

[[ -n "$plan_path" && -r "$plan_path" ]] || die "Plan file is not readable: $plan_path"
[[ "$generations" =~ ^[1-9][0-9]*$ ]] || die "GENERATIONS must be a positive integer: $generations"
[[ "$sleep_seconds" =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]] || die "SLEEP_SECONDS must be a non-negative number: $sleep_seconds"
[[ "$dry_run" =~ ^[01]$ ]] || die "DRY_RUN must be 0 or 1: $dry_run"
[[ "$stdout_mode" == discard || "$stdout_mode" == inherit ]] || die "STDOUT_MODE must be 'discard' or 'inherit': $stdout_mode"
stdout_target=/dev/null
[[ "$stdout_mode" == inherit ]] && stdout_target=/dev/stdout
codex_args=()
[[ -n "$codex_args_text" ]] && read -r -a codex_args <<< "$codex_args_text"
codex_command=("$codex_bin" "${codex_args[@]}" exec -)

printf 'PLANSELFPLAY CONFIG | plan=%s | generations=%s | sleep=%s | stdout=%s | codex=%s | args=%s\n' \
  "$plan_path" "$generations" "$sleep_seconds" "$stdout_mode" "$codex_bin" "$codex_args_text"
if [[ "$dry_run" == 1 ]]; then
  printf 'PLANSELFPLAY DRY RUN |'; printf ' %q' "${codex_command[@]}"; printf ' < %q\n' "$plan_path"; exit 0
fi

command -v "$codex_bin" >/dev/null 2>&1 || die "Required command not found on PATH: $codex_bin"
for ((generation=1; generation<=generations; generation++)); do
  printf 'PLANSELFPLAY %d/%d | plan=%s | codex=%s | args=%s\n' \
    "$generation" "$generations" "$plan_path" "$codex_bin" "$codex_args_text"
  "${codex_command[@]}" < "$plan_path" > "$stdout_target"
  (( generation < generations )) && sleep "$sleep_seconds"
done
