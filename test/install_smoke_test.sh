#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_home="$(mktemp -d "${TMPDIR:-/tmp}/psp-install-test.XXXXXX")"
trap 'rm -rf "$tmp_home"' EXIT

assert_file_contains() {
  local path="$1" needle="$2"
  grep -F "$needle" "$path" >/dev/null 2>&1 || {
    printf 'Expected %s to contain: %s\n' "$path" "$needle" >&2
    exit 1
  }
}

assert_file_not_contains() {
  local path="$1" needle="$2"
  ! grep -F "$needle" "$path" >/dev/null 2>&1 || {
    printf 'Did not expect %s to contain: %s\n' "$path" "$needle" >&2
    exit 1
  }
}

assert_exact_line_count() {
  local path="$1" needle="$2" expected="$3" actual
  actual="$(grep -Fxc "$needle" "$path" || true)"
  [[ "$actual" == "$expected" ]] || {
    printf 'Expected %s to contain %s copies of: %s (got %s)\n' "$path" "$expected" "$needle" "$actual" >&2
    exit 1
  }
}

assert_symlink_target() {
  local path="$1" expected="$2" actual
  [[ -L "$path" ]] || {
    printf 'Expected symlink: %s\n' "$path" >&2
    exit 1
  }
  actual="$(readlink "$path")"
  [[ "$actual" == "$expected" ]] || {
    printf 'Expected symlink %s -> %s, got %s\n' "$path" "$expected" "$actual" >&2
    exit 1
  }
}

run_install() {
  LC_ALL=C LANG=C HOME="$tmp_home" bash "$repo_root/psp" --install >/tmp/psp-install.out 2>/tmp/psp-install.err
}

printf '%s\n' 'export PATH="$HOME/.local/bin:$PATH"' > "$tmp_home/.zshrc"
printf '%s\n' '# existing bash config' 'export PATH="$HOME/.local/bin:$PATH"' > "$tmp_home/.bashrc"

run_install

assert_symlink_target "$tmp_home/.local/bin/psp" "$repo_root/psp"
assert_exact_line_count "$tmp_home/.zshrc" 'export PATH="$HOME/.local/bin:$PATH"' '1'
assert_exact_line_count "$tmp_home/.bashrc" 'export PATH="$HOME/.local/bin:$PATH"' '1'
assert_file_not_contains "$tmp_home/.zshrc" '# >>> psp >>>'
assert_file_not_contains "$tmp_home/.bashrc" '# >>> psp >>>'
assert_file_contains "$tmp_home/.psp/config.toml" '# ~/.psp/config.toml — PSP user defaults'
[[ ! -d "$tmp_home/.psp/skills" ]]
HOME="$tmp_home" PATH="$tmp_home/.local/bin:$PATH" psp --help >/tmp/psp-installed-help.out
assert_file_contains /tmp/psp-installed-help.out 'Usage: psp [options] [plan-path]'
assert_file_not_contains /tmp/psp-installed-help.out '--init-skills'

run_install

assert_exact_line_count "$tmp_home/.zshrc" 'export PATH="$HOME/.local/bin:$PATH"' '1'
assert_exact_line_count "$tmp_home/.bashrc" 'export PATH="$HOME/.local/bin:$PATH"' '1'

printf 'install smoke test passed\n'
