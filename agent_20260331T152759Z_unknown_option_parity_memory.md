# Unknown Option Parity Memory

## Decisions

- Kept the shell script as the oracle and fixed only the Python port's output-stream behavior for unknown options.
- Refactored `usage()` to accept an explicit output stream so normal help stays on `stdout` while parser errors can mirror the shell on `stderr`.

## Failed Ideas

- None abandoned; the differential sweep isolated the bug quickly enough that a broader rewrite was unnecessary.

## Metrics

- Added 1 regression parity test for unknown-option handling.
- Full verification command: `python3 -m unittest -v tests/test_psp_port.py`
- Verification result: 13 tests passed.

## Reusable Lessons

- Differential CLI checks should capture `stdout` and `stderr` separately, not just combined text, because shell parity bugs can hide in the output channel even when content matches.
