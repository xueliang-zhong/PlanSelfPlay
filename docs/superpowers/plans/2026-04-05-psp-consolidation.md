# PSP Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate post-`v0.2.1` features into a cleaner `psp` architecture with consistent precedence, output behavior, and documentation while preserving current functionality.

**Architecture:** Keep `psp` as the CLI entrypoint, but tighten it around explicit phases: option resolution, normalization/validation, presentation, and execution. Extract repeated branches into clearer helpers, align env/config/CLI precedence under one model, and update docs/tests so behavior is explicit and stable.

**Tech Stack:** Python 3 standard library, `unittest`, shell-based CLI docs/examples

---

### Task 1: Consolidate Resolution Flow

**Files:**
- Modify: `psp`
- Test: `tests/test_psp.py`

- [ ] **Step 1: Add failing tests for the precedence and resolution edge cases**

Add or extend tests that exercise the final resolution path through `main()` / `--config-show` for:

```python
def test_cli_configurable_options_override_config_file(self) -> None: ...
def test_env_overrides_config_file_but_cli_still_wins(self) -> None: ...
def test_non_tty_stdout_disables_color_by_default(self) -> None: ...
```

- [ ] **Step 2: Run the focused tests and confirm failures before any new consolidation logic**

Run:

```bash
python3 -m unittest \
  tests.test_psp.PSPPortTests.test_cli_configurable_options_override_config_file \
  tests.test_psp.PSPPortTests.test_env_overrides_config_file_but_cli_still_wins \
  tests.test_psp.PSPPortTests.test_non_tty_stdout_disables_color_by_default
```

Expected: at least one failure on the pre-consolidated version, proving the resolution path needs correction.

- [ ] **Step 3: Refactor the resolution pipeline into one coherent sequence**

Keep `main()` structured around:

```python
parsed = parse_args(opts, argv)
if parsed is not None:
    return parsed

_apply_env_overrides(opts)
_load_config_for_opts(opts)
_init_colors_for_opts(opts)
```

And ensure config/env helpers respect source keys consistently:

```python
if src_key in opts._sources:
    return
```

- [ ] **Step 4: Run the focused tests again**

Run the same focused `unittest` command from Step 2.

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add psp tests/test_psp.py
git commit --signoff -m "refactor: consolidate option resolution flow"
```

### Task 2: Consolidate Mode Dispatch and Presentation Helpers

**Files:**
- Modify: `psp`
- Test: `tests/test_psp.py`

- [ ] **Step 1: Write or refine tests around output and mode dispatch stability**

Keep/extend coverage for:

```python
def test_no_banner_dry_run_hides_header(self) -> None: ...
def test_config_show_format_json(self) -> None: ...
def test_progress_dry_run_matches_shell(self) -> None: ...
def test_stats_format_json(self) -> None: ...
```

- [ ] **Step 2: Run the focused presentation/mode tests**

Run:

```bash
python3 -m unittest \
  tests.test_psp.PSPPortTests.test_no_banner_dry_run_hides_header \
  tests.test_psp.PSPPortTests.test_config_show_format_json \
  tests.test_psp.PSPPortTests.test_progress_dry_run_matches_shell \
  tests.test_psp.PSPPortTests.test_stats_format_json
```

Expected: current behavior captured before helper cleanup.

- [ ] **Step 3: Refine helper boundaries for presentation and mode handling**

Keep mode dispatch explicit and small:

```python
if opts.config_show:
    return print_config_show(opts)
if opts.print_plan:
    return _handle_print_plan(opts)
if opts.install_mode:
    install_self(opts)
    return 0
```

Keep presentation centralized:

```python
_init_colors_for_opts(opts)
_print_header(...)
_build_goal_note(opts)
_run_summary(...)
```

Reduce repeated branching or duplicated formatting logic where it does not change behavior.

- [ ] **Step 4: Re-run the focused presentation/mode tests**

Run the same focused `unittest` command from Step 2.

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add psp tests/test_psp.py
git commit --signoff -m "refactor: simplify psp mode dispatch and output helpers"
```

### Task 3: Align Docs With Actual Behavior

**Files:**
- Modify: `README.md`
- Modify: `doc/guide.md`
- Test: `tests/test_psp.py`

- [ ] **Step 1: Identify documentation gaps versus current CLI behavior**

Specifically verify docs mention:

```text
default < config < env < CLI
TTY-aware color output
new flags added since v0.2.1
mode-specific JSON output support
```

- [ ] **Step 2: Update the docs to reflect the consolidated UX**

Refresh the relevant sections in:

```text
README.md
doc/guide.md
```

Cover the precedence chain and the newer operational modes without duplicating the entire help text in both places.

- [ ] **Step 3: Run the full test suite**

Run:

```bash
python3 -m unittest tests.test_psp -v
```

Expected: full suite passes.

- [ ] **Step 4: Commit**

```bash
git add README.md doc/guide.md psp tests/test_psp.py
git commit --signoff -m "docs: align psp docs with consolidated behavior"
```

### Task 4: Final Quality Pass

**Files:**
- Modify: `psp`
- Modify: `README.md`
- Modify: `doc/guide.md`
- Modify: `tests/test_psp.py`

- [ ] **Step 1: Do a final readability pass on naming, comments, and helper ordering**

Keep changes constrained to clarity improvements such as:

```python
def _init_colors_for_opts(opts: Options) -> None: ...
def _load_config_for_opts(opts: Options) -> None: ...
def _resolve_cwd(opts: Options) -> None: ...
```

- [ ] **Step 2: Re-run the full suite after the final pass**

Run:

```bash
python3 -m unittest tests.test_psp -v
```

Expected: all tests pass, no behavior regressions.

- [ ] **Step 3: Commit**

```bash
git add README.md doc/guide.md psp tests/test_psp.py
git commit --signoff -m "refactor: polish psp consolidation pass"
```
