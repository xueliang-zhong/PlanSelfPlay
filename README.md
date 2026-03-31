# PlanSelfPlay

One PLAN file. One shell loop. Visible agent self-improvement.

Works with **codex**, **claude**, and **opencode** out of the box.

## Usage

```bash
echo "improve test coverage" | ./psp        # run with a goal
./psp -p plan.txt -g 6                      # run your own plan
./psp --init-plan plan.txt                  # write a starter plan
./psp --init-config                         # write ~/.psp/config.toml
./psp --history | fzf | ./psp              # re-run a past goal
./psp --help                                # all options
```

Requirements: `bash`, and at least one of `codex` / `claude` / `opencode` on `PATH`.

See **[doc/guide.md](doc/guide.md)** for the full user guide.

## License

MIT — see [LICENSE](LICENSE).
