# Dry-Run Quote Parity Memory

## Decisions

- Kept `psp.sh` as the oracle and fixed only the Python dry-run quoting path.
- Replaced the custom Python `%q` approximation with a direct Bash `printf '%q'` call so control-character escaping stays exact.

## Failed Ideas

- A shared-temp differential sweep produced false install mismatches because the shell variant mutated the fixture before the Python variant ran.

## Metrics

- Added 1 regression parity test for multiline builtin-goal dry-run output.
- Verification command: `python3 -m unittest -v tests/test_psp_port.py`
- Verification result: 15 tests passed.

## Reusable Lessons

- For shell-parity diagnostics, isolate the shell and Python runs in separate temp dirs whenever either variant can mutate the filesystem.
- When parity depends on Bash `%q`, prefer delegating the rendering to Bash instead of maintaining an incomplete Python reimplementation.
