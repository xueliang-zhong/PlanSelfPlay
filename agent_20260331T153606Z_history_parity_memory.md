# History Parity Memory

## Decisions

- Kept `psp.sh` as the oracle and fixed only the Python `--history` projection logic.
- Matched shell behavior at the text-processing level instead of inventing a stricter parser, because the shell implementation uses `cut -f5 | awk '!seen[$0]++'`.

## Failed Ideas

- None abandoned; the differential check isolated the mismatch before any broader redesign was needed.

## Metrics

- Added 1 regression parity test for malformed history lines.
- Full verification command: `python3 -m unittest -v tests/test_psp_port.py`
- Verification result: 14 tests passed.

## Reusable Lessons

- For shell-to-Python CLI ports, parity bugs can hide in Unix text-filter edge cases; when the shell implementation pipes through tools like `cut` and `awk`, mirror their observable semantics instead of “cleaning up” malformed input.
