from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import importlib.util
from unittest import mock
from pathlib import Path
from importlib.machinery import SourceFileLoader


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ENTRYPOINT = REPO_ROOT / "psp"

TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
RUN_TS_RE = re.compile(r"\d{8}T\d{6}Z")
HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
TOOK_RE = re.compile(r"took: \d+s")


def load_python_psp_module():
    loader = SourceFileLoader("psp_module", str(PYTHON_ENTRYPOINT))
    spec = importlib.util.spec_from_loader("psp_module", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PSPPortTests(unittest.TestCase):
    maxDiff = None

    def test_psp_entrypoint_is_python(self) -> None:
        first_line = PYTHON_ENTRYPOINT.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first_line, "#!/usr/bin/env python3")

    def test_help_matches_shell(self) -> None:
        self.assert_parity(["--help"])

    def test_init_plan_matches_shell(self) -> None:
        self.assert_parity(["--init-plan", "starter.plan"], inspect=self.inspect_init_plan)

    def test_history_without_history_file_matches_shell(self) -> None:
        self.assert_parity(["--history"])

    def test_history_deduplicates_goal_lines_like_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "history").write_text(
                "\n".join(
                    [
                        "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha",
                        "2026-03-31T09:05:00Z\tcodex\t/tmp/repo\tg=2\talpha",
                        "2026-03-31T09:10:00Z\tclaude\t/tmp/repo\tg=3\tbeta",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        self.assert_parity(["--history"], fixture=fixture)

    def test_history_preserves_malformed_lines_like_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "history").write_text(
                "\n".join(
                    [
                        "malformed line without tabs",
                        "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha",
                        "short\tline",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        self.assert_parity(["--history"], fixture=fixture)

    def test_history_pipes_spaced_output_to_pager_on_tty(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            psp_dir = Path(tmpdir)
            (psp_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\tgoal A\n"
                "2026-03-31T09:01:00Z\tcodex\t/tmp/repo\tg=2\tgoal B\n",
                encoding="utf-8",
            )
            with mock.patch("sys.stdout") as mock_stdout, \
                 mock.patch.dict(module.os.environ, {}, clear=True), \
                 mock.patch.object(module.shutil, "which", return_value="/usr/bin/less"), \
                 mock.patch.object(module.subprocess, "run") as run_mock:
                mock_stdout.isatty.return_value = True
                exit_code = module.print_history(psp_dir)

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()
        cmd, = run_mock.call_args.args
        self.assertEqual(cmd, ["less", "-FRX", "+G"])
        # spaced: blank line before each goal (equiv to sed "s/^/\n/")
        self.assertEqual(run_mock.call_args.kwargs["input"], "\ngoal A\n\ngoal B\n\n")
        mock_stdout.write.assert_not_called()

    def test_history_writes_plain_text_when_piped(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            psp_dir = Path(tmpdir)
            (psp_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\tgoal A\n"
                "2026-03-31T09:01:00Z\tcodex\t/tmp/repo\tg=2\tgoal B\n",
                encoding="utf-8",
            )
            with mock.patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = False
                exit_code = module.print_history(psp_dir)

        self.assertEqual(exit_code, 0)
        mock_stdout.write.assert_called_once_with("goal A\ngoal B\n")

    def test_history_always_appends_plus_G_when_pager_is_less(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            psp_dir = Path(tmpdir)
            (psp_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\tgoal A\n",
                encoding="utf-8",
            )
            with mock.patch("sys.stdout") as mock_stdout, \
                 mock.patch.dict(module.os.environ, {"PAGER": "less"}, clear=True), \
                 mock.patch.object(module.shutil, "which", return_value="/usr/bin/less"), \
                 mock.patch.object(module.subprocess, "run") as run_mock:
                mock_stdout.isatty.return_value = True
                module.print_history(psp_dir)

        cmd, = run_mock.call_args.args
        self.assertIn("+G", cmd)

    def test_dry_run_builtin_goal_matches_shell(self) -> None:
        self.assert_parity(["--dry-run"], stdin="reduce lines of code\n")

    def test_dry_run_builtin_goal_with_multiline_text_matches_shell(self) -> None:
        self.assert_parity(["--dry-run"], stdin="line1\nline2")

    def test_dry_run_explicit_plan_with_goal_override_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            (workdir / "plan.txt").write_text(
                "DOMAIN: repo\nGOAL: old goal\nCONSTRAINTS: none\n",
                encoding="utf-8",
            )

        self.assert_parity(["--dry-run", "--plan", "plan.txt"], stdin="new goal\n", fixture=fixture)

    def test_run_with_logged_output_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            fake_agent = workdir / "fake-agent"
            fake_agent.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import sys

                    plan = sys.stdin.read()
                    sys.stdout.write("AGENT START\\n")
                    sys.stdout.write(plan)
                    """
                ),
                encoding="utf-8",
            )
            fake_agent.chmod(fake_agent.stat().st_mode | stat.S_IXUSR)

        env = {"AGENT_BIN": "./fake-agent"}
        self.assert_parity(
            ["--generations", "2", "--sleep", "0", "--output", "log", "--keep-logs", "always"],
            stdin="improve docs\n",
            fixture=fixture,
            inspect=self.inspect_logged_run,
            extra_env=env,
        )

    def test_run_with_commit_detection_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            self.init_git_repo(workdir)
            fake_agent = workdir / "fake-agent"
            fake_agent.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import pathlib
                    import subprocess
                    import sys

                    state = pathlib.Path(".fake-agent-count")
                    count = int(state.read_text() if state.exists() else "0") + 1
                    state.write_text(str(count))
                    sys.stdout.write(sys.stdin.read())
                    if count == 1:
                        pathlib.Path("agent-output.txt").write_text("changed\\n")
                        subprocess.run(["git", "add", "agent-output.txt"], check=True)
                        subprocess.run(
                            [
                                "git",
                                "commit",
                                "--signoff",
                                "-m",
                                "test: fake agent commit",
                            ],
                            check=True,
                        )
                    """
                ),
                encoding="utf-8",
            )
            fake_agent.chmod(fake_agent.stat().st_mode | stat.S_IXUSR)

        env = {"AGENT_BIN": "./fake-agent"}
        self.assert_parity(
            ["--generations", "2", "--sleep", "0", "--output", "discard"],
            stdin="improve tests\n",
            fixture=fixture,
            inspect=self.inspect_history,
            extra_env=env,
        )

    def test_install_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            pass

        self.assert_parity(["--install"], fixture=fixture, inspect=self.inspect_install)

    def test_version_reports_installed_git_sha_when_metadata_exists(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--version"],
            stdin=None,
            fixture=self.fixture_installed_version_metadata,
            inspect=None,
            extra_env=None,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "psp 0.2.1-dev (<HASH>)")
        self.assertEqual(result["stderr"], "")

    def test_version_omits_git_sha_without_installed_metadata(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--version"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "psp 0.2.1-dev")
        self.assertEqual(result["stderr"], "")

    def test_claude_yolo_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--agent", "claude", "--yolo", "--dry-run"], stdin="ship it\n")

    def test_opencode_yolo_warning_matches_shell(self) -> None:
        self.assert_parity(["--agent", "opencode", "--yolo", "--dry-run"], stdin="ship it\n")

    def test_unknown_option_matches_shell(self) -> None:
        self.assert_parity(["--wat"])

    def test_read_log_rows_returns_chronological_order(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            (workdir / "psp_codex_20260331T090000Z_gen01.log").write_text("one\n", encoding="utf-8")
            (workdir / "psp_claude_20260331T090500Z_gen02.log").write_text("two\n", encoding="utf-8")
            (workdir / "notes.txt").write_text("ignore\n", encoding="utf-8")

            rows = module.read_log_rows(workdir)

        self.assertEqual([row.filename for row in rows], [
            "psp_codex_20260331T090000Z_gen01.log",
            "psp_claude_20260331T090500Z_gen02.log",
        ])
        self.assertEqual(rows[0].agent, "codex")
        self.assertEqual(rows[0].generation, "1")
        self.assertEqual(rows[1].run_timestamp, "20260331T090500Z")

    def test_logs_outputs_plain_paths(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            (workdir / "psp_codex_20260331T090000Z_gen01.log").write_text("one\n", encoding="utf-8")
            (workdir / "psp_claude_20260331T090500Z_gen02.log").write_text("two\n", encoding="utf-8")

        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--logs"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(
            result["stdout"].splitlines(),
            [
                "<TMP>/work/psp_codex_<RUN_TS>_gen01.log",
                "<TMP>/work/psp_claude_<RUN_TS>_gen02.log",
            ],
        )

    def test_goal_flag_sets_goal_without_stdin(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        opts.goal_flag = "fix the tests"
        # read_goal must use goal_flag when stdin is a tty (no piped input)
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            module.read_goal(opts)
        self.assertEqual(opts.goal_text, "fix the tests")

    def test_goal_flag_loses_to_stdin(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        opts.goal_flag = "from flag"
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "from stdin\n"
            module.read_goal(opts)
        self.assertEqual(opts.goal_text, "from stdin")

    def test_goal_flag_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--goal", "improve coverage", "--dry-run"])

    def test_goal_short_flag_dry_run_matches_shell(self) -> None:
        self.assert_parity(["-G", "improve coverage", "--dry-run"])

    def test_continue_uses_last_history_goal(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            psp_dir = Path(tmpdir)
            (psp_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\tgoal A\n"
                "2026-03-31T10:00:00Z\tcodex\t/tmp/repo\tg=2\tgoal B\n",
                encoding="utf-8",
            )
            goals = module.read_history_goals(psp_dir)
        self.assertEqual(goals[-1], "goal B")

    def test_continue_no_history_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--continue", "--dry-run"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("No history", result["stderr"])

    def assert_parity(
        self,
        args: list[str],
        *,
        stdin: str | None = None,
        fixture=None,
        inspect=None,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            args,
            stdin=stdin,
            fixture=fixture,
            inspect=inspect,
            extra_env=extra_env,
        )
        # Basic sanity: must not crash unexpectedly (exit 1 is fine for usage errors)
        self.assertIn(result["returncode"], (0, 1))
        return result

    def run_variant(
        self,
        script_path: Path,
        args: list[str],
        *,
        stdin: str | None,
        fixture,
        inspect,
        extra_env: dict[str, str] | None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workdir = root / "work"
            home = root / "home"
            workdir.mkdir()
            home.mkdir()

            launch_path = workdir / "psp"
            launch_path.symlink_to(script_path)

            if fixture is not None:
                fixture(workdir, home)

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["LC_ALL"] = "C"
            env["PATH"] = f"{workdir}{os.pathsep}{env.get('PATH', '')}"
            if extra_env:
                env.update(extra_env)

            completed = subprocess.run(
                [str(launch_path), *args],
                cwd=workdir,
                input=stdin,
                text=True,
                capture_output=True,
                env=env,
                timeout=30,
            )
            snapshot = {
                "returncode": completed.returncode,
                "stdout": self.normalize_text(completed.stdout, root, script_path),
                "stderr": self.normalize_text(completed.stderr, root, script_path),
            }
            if inspect is not None:
                snapshot["artifacts"] = inspect(workdir, home, script_path)
            return snapshot

    def normalize_text(self, value: str, root: Path, script_path: Path) -> str:
        normalized = value.replace(f"/private{root}", "<TMP>")
        normalized = normalized.replace(str(root), "<TMP>")
        normalized = normalized.replace(str(script_path.resolve()), "<SCRIPT>")
        normalized = normalized.replace(str(script_path), "<SCRIPT>")
        normalized = TIMESTAMP_RE.sub("<TIMESTAMP>", normalized)
        normalized = RUN_TS_RE.sub("<RUN_TS>", normalized)
        normalized = HASH_RE.sub("<HASH>", normalized)
        normalized = TOOK_RE.sub("took: <SECONDS>s", normalized)
        return normalized

    def inspect_init_plan(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        return {
            "starter.plan": self.normalize_text(
                (workdir / "starter.plan").read_text(encoding="utf-8"),
                workdir.parent,
                script_path,
            )
        }

    def inspect_logged_run(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        artifacts = self.inspect_history(workdir, home, script_path)
        log_files = sorted(path.name for path in workdir.glob("psp_*_gen*.log"))
        self.assertEqual(len(log_files), 2)
        artifacts["log_files"] = [self.normalize_text(name, workdir.parent, script_path) for name in log_files]
        artifacts["log_contents"] = [
            self.normalize_text(path.read_text(encoding="utf-8"), workdir.parent, script_path)
            for path in sorted(workdir.glob("psp_*_gen*.log"))
        ]
        return artifacts

    def inspect_history(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        history = (home / ".psp" / "history").read_text(encoding="utf-8")
        return {
            "history": self.normalize_text(history, workdir.parent, script_path),
        }

    def inspect_install(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        link = home / ".local" / "bin" / "psp"
        version_file = home / ".local" / "bin" / ".psp-version"
        config = home / ".psp" / "config.toml"
        zshrc = home / ".zshrc"
        bashrc = home / ".bashrc"
        return {
            "link_target": self.normalize_text(os.path.realpath(link), workdir.parent, script_path),
            ".psp-version": self.normalize_text(version_file.read_text(encoding="utf-8"), workdir.parent, script_path),
            "config.toml": self.normalize_text(config.read_text(encoding="utf-8"), workdir.parent, script_path),
            ".zshrc": self.normalize_text(zshrc.read_text(encoding="utf-8"), workdir.parent, script_path),
            ".bashrc": self.normalize_text(bashrc.read_text(encoding="utf-8"), workdir.parent, script_path),
        }

    def init_git_repo(self, workdir: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=workdir, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "PSP Tests"],
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "psp-tests@example.com"],
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
        )
        (workdir / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=workdir, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "--signoff", "-m", "test: initial commit"],
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
        )

    def fixture_installed_version_metadata(self, workdir: Path, home: Path) -> None:
        bin_dir = home / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / ".psp-version").write_text("abcdef1\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
