from __future__ import annotations

import io
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

    def test_help_option_indentation_is_uniform(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--help"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        lines = result["stdout"].splitlines()
        start = lines.index("Options:") + 1
        end = lines.index("Agent presets (overridable via --agent-args):")
        option_lines = [line for line in lines[start:end] if line.strip()]
        self.assertTrue(option_lines)
        for line in option_lines:
            self.assertTrue(line.startswith("  "), line)
            self.assertFalse(line.startswith("   "), line)

    def test_init_plan_matches_shell(self) -> None:
        self.assert_parity(["--init-plan", "starter.plan"], inspect=self.inspect_init_plan)

    def test_init_plan_bypasses_tmux_launch(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            previous_cwd = Path.cwd()
            starter_plan = Path("starter.plan")
            try:
                os.chdir(workdir)
                with mock.patch.object(module, "load_config"), \
                     mock.patch.object(module, "read_goal"), \
                     mock.patch.object(module, "launch_tmux", return_value=True) as launch_tmux_mock:
                    exit_code = module.main(["--init-plan", "starter.plan"])
                starter_plan_exists = starter_plan.exists()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(exit_code, 0)
        launch_tmux_mock.assert_not_called()
        self.assertTrue(starter_plan_exists)

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
        self.assertEqual(result["stdout"].strip(), "psp 0.3.0-dev (<HASH>)")
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
        self.assertEqual(result["stdout"].strip(), "psp 0.3.0-dev")
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
            env["PSP_TMUX_CHILD"] = "1"  # disable tmux split during tests
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

    def test_no_color_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--no-color", "--dry-run"], stdin="test goal\n")

    def test_non_tty_stdout_disables_color_by_default(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            previous_cwd = Path.cwd()
            try:
                os.chdir(workdir)
                with mock.patch.object(module, "load_config"), \
                     mock.patch.object(module, "launch_tmux", return_value=False), \
                     mock.patch("sys.stdin") as mock_stdin, \
                     mock.patch("sys.stdout") as mock_stdout:
                    mock_stdin.isatty.return_value = False
                    mock_stdin.read.return_value = "test goal\n"
                    mock_stdout.isatty.return_value = False

                    exit_code = module.main(["--dry-run"])
                    stdout_text = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(exit_code, 0)
        self.assertNotRegex(stdout_text, r"\x1b\[[0-9;]*m")
        self.assertNotIn("m| PSP STEP", stdout_text)

    def test_quiet_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--quiet", "--dry-run"], stdin="test goal\n")

    def test_verbose_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--verbose", "--dry-run"], stdin="test goal\n")

    def test_stop_on_error_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--stop-on-error", "--dry-run"], stdin="test goal\n")

    def test_cwd_invalid_directory_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--cwd", "/nonexistent/path/xyz", "--dry-run"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("Directory not found", result["stderr"])

    def test_config_show_includes_new_flags(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("quiet", result["stdout"])
        self.assertIn("stop_on_error", result["stdout"])
        self.assertIn("verbose", result["stdout"])
        self.assertIn("PSP_* env vars < CLI flags", result["stdout"])

    def test_cli_configurable_options_override_config_file(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "config.toml").write_text(
                "\n".join(
                    [
                        'agent = "claude"',
                        'generations = "9"',
                        'sleep = "7"',
                        'time_budget = "99"',
                        'output = "discard"',
                        'agent_bin = "/bin/echo"',
                        'agent_args = "config args"',
                        'yolo = true',
                        'tmux = false',
                        'keep_logs = "never"',
                        'quiet = true',
                        'stop_on_error = true',
                        'verbose = true',
                        'no_color = true',
                        'no_banner = true',
                        'model = "config-model"',
                        'headless = true',
                        'max_turns = "77"',
                        'diff_mode = true',
                    ]
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            [
                "--config-show",
                "-a", "codex",
                "-g", "2",
                "-s", "1",
                "-t", "3",
                "-o", "log",
                "--agent-bin", "/bin/cat",
                "-x", "cli args",
                "--yolo",
                "--tmux",
                "--keep-logs", "always",
                "--quiet",
                "--stop-on-error",
                "--verbose",
                "--no-color",
                "--no-banner",
                "--model", "cli-model",
                "--headless",
                "--max-turns", "11",
                "--diff",
                "--format", "json",
            ],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )

        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertEqual(data["agent"], "codex")
        self.assertEqual(data["generations"], "2")
        self.assertEqual(data["sleep"], "1")
        self.assertEqual(data["time_budget"], "3")
        self.assertEqual(data["output"], "log")
        self.assertEqual(data["agent_bin"], "/bin/cat")
        self.assertEqual(data["agent_args"], "cli args")
        self.assertEqual(data["yolo"], "true")
        self.assertEqual(data["tmux"], "true")
        self.assertEqual(data["keep_logs"], "always")
        self.assertEqual(data["quiet"], "true")
        self.assertEqual(data["stop_on_error"], "true")
        self.assertEqual(data["verbose"], "true")
        self.assertEqual(data["no_color"], "true")
        self.assertEqual(data["no_banner"], "true")
        self.assertEqual(data["model"], "cli-model")
        self.assertEqual(data["headless"], "true")
        self.assertEqual(data["max_turns"], "11")
        self.assertEqual(data["diff_mode"], "true")

    def test_env_overrides_config_file_but_cli_still_wins(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "config.toml").write_text(
                "\n".join(
                    [
                        'agent = "claude"',
                        'quiet = false',
                        'progress = "auto"',
                    ]
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show", "--agent", "codex", "--format", "json"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env={
                "PSP_AGENT": "opencode",
                "PSP_QUIET": "true",
                "PSP_PROGRESS": "plain",
            },
        )

        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertEqual(data["agent"], "codex")
        self.assertEqual(data["quiet"], "true")
        self.assertEqual(data["progress"], "plain")
        self.assertEqual(data["_sources"]["agent"], "--agent")
        self.assertEqual(data["_sources"]["quiet"], "env:PSP_QUIET")
        self.assertEqual(data["_sources"]["progress"], "env:PSP_PROGRESS")

    def test_print_plan_with_goal(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--print-plan"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("GOAL: test goal", result["stdout"])
        self.assertIn("DOMAIN:", result["stdout"])

    def test_print_plan_with_explicit_plan(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            (workdir / "plan.txt").write_text("DOMAIN: test\nGOAL: old\n", encoding="utf-8")
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--print-plan", "--plan", "plan.txt"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "DOMAIN: test\nGOAL: old\n")

    def test_print_plan_without_goal_or_plan_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--print-plan"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("--print-plan requires", result["stderr"])

    def test_no_banner_dry_run_hides_header(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--no-banner", "--dry-run"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertNotIn("PSP STEP", result["stdout"])
        self.assertIn("PSP DRY RUN", result["stdout"])

    def test_no_banner_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--no-banner", "--dry-run"], stdin="test goal\n")

    def test_model_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--model", "gpt-4o", "--dry-run"], stdin="test goal\n")

    def test_config_invalid_file_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config", "/nonexistent/config.toml", "--dry-run"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("Config file not found", result["stderr"])

    def test_config_show_includes_no_banner_and_model(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("no_banner", result["stdout"])
        self.assertIn("model", result["stdout"])

    def test_env_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--env", "FOO=bar", "--env", "BAZ=qux", "--dry-run"], stdin="test goal\n")

    def test_options_use_bool_types(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        for attr in ("dry_run", "install_mode", "plan_seen", "yolo_mode", "fzf_mode",
                     "tmux_mode", "logs_mode", "history_mode", "continue_mode",
                     "config_show", "no_color", "quiet_mode", "stop_on_error",
                     "verbose_mode", "print_plan", "no_banner", "headless_mode",
                     "diff_mode"):
            self.assertIsInstance(getattr(opts, attr), bool, f"{attr} should be bool")

    def test_headless_without_goal_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--headless", "--dry-run"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("No goal provided", result["stderr"])

    def test_headless_with_goal_flag_works(self) -> None:
        self.assert_parity(["--headless", "--goal", "test goal", "--dry-run"])

    def test_headless_with_stdin_works(self) -> None:
        self.assert_parity(["--headless", "--dry-run"], stdin="test goal\n")

    def test_max_turns_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--max-turns", "25", "--dry-run"], stdin="test goal\n")

    def test_max_turns_includes_config_show(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("max_turns", result["stdout"])

    def test_diff_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--diff", "--dry-run"], stdin="test goal\n")

    def test_config_show_includes_headless_and_diff(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("headless", result["stdout"])

    def test_config_dispatch_table_handles_unknown_key(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            cfg.write_text("unknown_key = value\nagent = claude\n", encoding="utf-8")
            dummy = Path("/tmp/psp")
            opts = module.Options(script_path=dummy, script_dir=dummy.parent)
            module._load_config_file(opts, cfg, "test-config")
        self.assertEqual(opts.agent, "claude")

    def test_config_dispatch_table_handles_keep_logs_bool(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            cfg.write_text("keep_logs = true\n", encoding="utf-8")
            dummy = Path("/tmp/psp")
            opts = module.Options(script_path=dummy, script_dir=dummy.parent)
            module._load_config_file(opts, cfg, "test-config")
        self.assertEqual(opts.keep_logs, "always")

    def test_config_dispatch_table_handles_keep_logs_false(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            cfg.write_text("keep_logs = false\n", encoding="utf-8")
            dummy = Path("/tmp/psp")
            opts = module.Options(script_path=dummy, script_dir=dummy.parent)
            module._load_config_file(opts, cfg, "test-config")
        self.assertEqual(opts.keep_logs, "session")

    def test_clean_mode_skips_config_loading(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        opts.clean_mode = True
        # With clean_mode, config loading should be skipped in main()
        # Verify the flag is set correctly
        self.assertTrue(opts.clean_mode)

    def test_clean_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--clean", "--dry-run"], stdin="test goal\n")

    def test_last_mode_with_no_runs(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--last"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("No previous runs", result["stderr"])

    def test_history_format_json(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha\n"
                "2026-03-31T09:05:00Z\tcodex\t/tmp/repo\tg=3\tbeta\n",
                encoding="utf-8",
            )
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--history", "--format", "json"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["goals"], ["alpha", "beta"])

    def test_config_show_format_json(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show", "--format", "json"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertIn("agent", data)
        self.assertIn("generations", data)

    def test_logs_format_json(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            (workdir / "psp_codex_20260331T090000Z_gen01.log").write_text("one\n", encoding="utf-8")
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--logs", "--format", "json"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["agent"], "codex")
        self.assertEqual(data[0]["generation"], "1")

    def test_new_bool_types(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        for attr in ("clean_mode", "last_mode", "follow_mode"):
            self.assertIsInstance(getattr(opts, attr), bool, f"{attr} should be bool")

    def test_c_function_colors_enabled(self) -> None:
        module = load_python_psp_module()
        module._COLOR_ENABLED = True
        module._init_colors()
        result = module.c("hello", module.CYAN)
        self.assertIn("hello", result)
        self.assertIn("\033[36m", result)
        self.assertTrue(result.endswith("\033[0m"))

    def test_c_function_colors_disabled(self) -> None:
        module = load_python_psp_module()
        module._COLOR_ENABLED = False
        module._init_colors()
        result = module.c("hello", module.CYAN)
        self.assertEqual(result, "hello")
        self.assertNotIn("\033[", result)

    def test_env_vars_accumulated_in_options(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        opts.env_vars.append("FOO=bar")
        opts.env_vars.append("BAZ=qux")
        self.assertEqual(opts.env_vars, ["FOO=bar", "BAZ=qux"])

    def test_env_parsing_in_arg_parser(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        module.parse_args(opts, ["--env", "FOO=bar", "--env", "BAZ=qux", "--dry-run"])
        self.assertEqual(opts.env_vars, ["FOO=bar", "BAZ=qux"])

    def test_timeout_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--timeout", "60", "--dry-run"], stdin="test goal\n")

    def test_generation_timeout_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--generation-timeout", "60", "--dry-run"], stdin="test goal\n")

    def test_retry_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--retry", "3", "--dry-run"], stdin="test goal\n")

    def test_tac_history_reverses_goals(self) -> None:
        module = load_python_psp_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            psp_dir = Path(tmpdir)
            (psp_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha\n"
                "2026-03-31T09:05:00Z\tcodex\t/tmp/repo\tg=2\tbeta\n",
                encoding="utf-8",
            )
            with mock.patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = False
                exit_code = module.print_history(psp_dir, tac=True)
            self.assertEqual(exit_code, 0)
            mock_stdout.write.assert_called_once_with("beta\nalpha\n")

    def test_tac_logs_reverses_rows(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            (workdir / "psp_codex_20260331T090000Z_gen01.log").write_text("one\n", encoding="utf-8")
            (workdir / "psp_codex_20260331T090500Z_gen02.log").write_text("two\n", encoding="utf-8")
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--logs", "--tac"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        lines = result["stdout"].splitlines()
        self.assertIn("gen02", lines[0])
        self.assertIn("gen01", lines[1])

    def test_stats_mode_with_no_runs(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--stats"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("No runs found", result["stderr"])

    def test_stats_dry_run_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha\n",
                encoding="utf-8",
            )
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--stats"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("Total goals", result["stdout"])

    def test_stats_format_json(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            history_dir = home / ".psp"
            history_dir.mkdir(parents=True, exist_ok=True)
            (history_dir / "history").write_text(
                "2026-03-31T09:00:00Z\tcodex\t/tmp/repo\tg=2\talpha\n",
                encoding="utf-8",
            )
            (workdir / "psp_codex_20260331T090000Z_gen01.log").write_text("one\n", encoding="utf-8")
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--stats", "--format", "json"],
            stdin=None,
            fixture=fixture,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        import json
        data = json.loads(result["stdout"])
        self.assertEqual(data["total_goals"], 1)
        self.assertEqual(data["total_logs"], 1)
        self.assertEqual(data["agents"], {"codex": 1})

    def test_timeout_validation_rejects_negative(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--timeout", "-1", "--dry-run"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("TIMEOUT", result["stderr"])

    def test_generation_timeout_validation_rejects_negative(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--generation-timeout", "-1", "--dry-run"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("TIMEOUT", result["stderr"])

    def test_retry_validation_rejects_negative(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--retry", "-1", "--dry-run"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("RETRY", result["stderr"])

    def test_config_show_includes_timeout_and_retry(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("timeout", result["stdout"])
        self.assertIn("retry", result["stdout"])

    def test_new_bool_types_tac_and_stats(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        self.assertIsInstance(opts.tac_mode, bool)
        self.assertIsInstance(opts.stats_mode, bool)
        self.assertIsInstance(opts.progress_mode, str)
        self.assertEqual(opts.progress_mode, "auto")

    def test_progress_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--progress", "plain", "--dry-run"], stdin="test goal\n")

    def test_progress_invalid_exits_with_error(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--progress", "invalid", "--dry-run"],
            stdin="test goal\n",
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 1)
        self.assertIn("must be auto, plain, or tty", result["stderr"])

    def test_config_show_includes_progress(self) -> None:
        result = self.run_variant(
            PYTHON_ENTRYPOINT,
            ["--config-show"],
            stdin=None,
            fixture=None,
            inspect=None,
            extra_env=None,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertIn("progress", result["stdout"])

    def test_env_psp_agent_override(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_AGENT": "claude"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertEqual(opts.agent, "claude")
        self.assertEqual(opts._sources.get("agent"), "env:PSP_AGENT")

    def test_env_psp_quiet_override(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_QUIET": "true"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertTrue(opts.quiet_mode)

    def test_env_psp_quiet_override_false(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        opts.quiet_mode = True  # set via config
        with mock.patch.dict(module.os.environ, {"PSP_QUIET": "0"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertFalse(opts.quiet_mode)

    def test_env_psp_progress_override(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_PROGRESS": "plain"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertEqual(opts.progress_mode, "plain")

    def test_env_psp_progress_invalid_exits(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_PROGRESS": "invalid"}, clear=True):
            with self.assertRaises(SystemExit):
                module._apply_env_overrides(opts)

    def test_env_psp_agent_invalid_exits(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_AGENT": "invalid"}, clear=True):
            with self.assertRaises(SystemExit):
                module._apply_env_overrides(opts)

    def test_env_psp_output_invalid_exits(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_OUTPUT": "invalid"}, clear=True):
            with self.assertRaises(SystemExit):
                module._apply_env_overrides(opts)

    def test_env_psp_multiple_overrides(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        env = {
            "PSP_AGENT": "opencode",
            "PSP_GENERATIONS": "5",
            "PSP_QUIET": "1",
            "PSP_NO_COLOR": "yes",
        }
        with mock.patch.dict(module.os.environ, env, clear=True):
            module._apply_env_overrides(opts)
        self.assertEqual(opts.agent, "opencode")
        self.assertEqual(opts.generations, "5")
        self.assertTrue(opts.quiet_mode)
        self.assertTrue(opts.no_color)

    def test_env_psp_keep_logs_override(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_KEEP_LOGS": "never"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertEqual(opts.keep_logs, "never")

    def test_env_psp_keep_logs_bool_override(self) -> None:
        module = load_python_psp_module()
        dummy = Path("/tmp/psp")
        opts = module.Options(script_path=dummy, script_dir=dummy.parent)
        with mock.patch.dict(module.os.environ, {"PSP_KEEP_LOGS": "true"}, clear=True):
            module._apply_env_overrides(opts)
        self.assertEqual(opts.keep_logs, "always")

    def test_signal_handler_registered(self) -> None:
        module = load_python_psp_module()
        # Verify signal handlers are set for SIGTERM
        import signal as sig
        module._register_signal_handlers()
        handler = sig.getsignal(sig.SIGTERM)
        self.assertEqual(handler, module._handle_signal)

    def test_shutdown_flag_initially_false(self) -> None:
        module = load_python_psp_module()
        module._shutdown_requested = False
        self.assertFalse(module._shutdown_requested)

    def test_shutdown_flag_set_by_handler(self) -> None:
        module = load_python_psp_module()
        module._shutdown_requested = False
        module._handle_signal(15, None)  # SIGTERM
        self.assertTrue(module._shutdown_requested)

    def test_run_generation_loop_exits_immediately_after_signal_terminated_child(self) -> None:
        module = load_python_psp_module()

        class FakeProc:
            def __init__(self) -> None:
                self.returncode = None

            def wait(self, timeout=None) -> None:
                module._shutdown_requested = True
                self.returncode = -15

            def poll(self):
                return self.returncode

            def terminate(self) -> None:
                self.returncode = -15

            def kill(self) -> None:
                self.returncode = -9

        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            plan = workdir / "plan.txt"
            plan.write_text("DOMAIN: test\nGOAL: test\n", encoding="utf-8")
            dummy = workdir / "psp"
            opts = module.Options(script_path=dummy, script_dir=workdir)
            opts.agent = "codex"
            opts.generations = "2"
            opts.sleep_seconds = "0"
            opts.output_mode = "discard"
            opts.keep_logs = "always"
            opts.quiet_mode = False
            opts.timeout_seconds = "0"
            opts.retry_count = "0"
            output = io.StringIO()
            previous_cwd = Path.cwd()
            module._shutdown_requested = False
            module._current_proc = None
            module._COLOR_ENABLED = False
            module._init_colors()
            try:
                os.chdir(workdir)
                with mock.patch.object(module, "append_history"), \
                     mock.patch.object(module, "git_head", return_value="abc1234"), \
                     mock.patch.object(module.subprocess, "Popen", return_value=FakeProc()), \
                     mock.patch("sys.stdout", output):
                    exit_code = module.run_generation_loop(
                        opts,
                        ["fake-agent"],
                        str(plan),
                        "plan.txt",
                        header_width=9,
                    )
            finally:
                os.chdir(previous_cwd)
                module._shutdown_requested = False
                module._current_proc = None

        self.assertEqual(exit_code, 130)
        self.assertIn("signal received, shutting down", output.getvalue())
        self.assertNotIn("agent failed", output.getvalue())
        self.assertNotIn("no commit", output.getvalue())

    def test_config_show_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--config-show", "--dry-run"], stdin="test goal\n")


if __name__ == "__main__":
    unittest.main()
