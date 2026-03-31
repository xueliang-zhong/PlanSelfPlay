# PSP Python Port Memory

## Decisions

- Replaced tracked `psp` with a single-file Python CLI instead of introducing a package layout; for this repo size, focused functions in one executable file are easier to maintain than a premature module split.
- Kept the shell implementation as `psp.sh` so parity has a concrete oracle.
- Used `unittest` integration tests instead of adding new test dependencies, since `pytest` is not installed in the environment.

## Failed Ideas

- None abandoned during implementation; the chosen path stayed stable once the shell-oracle parity harness was in place.

## Metrics

- Added 12 end-to-end tests covering help, history, init-plan, dry-run, install, yolo presets, logged runs, and commit detection.
- Verification command: `python3 -m unittest -v tests/test_psp_port.py`

## Reusable Lessons

- For CLI ports, treat the old implementation as the spec and compare observable behavior in temp fixtures instead of translating line-by-line.
- Normalize timestamps, commit hashes, and elapsed seconds in parity tests so failures point to semantic drift rather than incidental runtime noise.
