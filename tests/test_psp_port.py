from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ENTRYPOINT = REPO_ROOT / "psp"
SHELL_ENTRYPOINT = REPO_ROOT / "psp.sh"

TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
RUN_TS_RE = re.compile(r"\d{8}T\d{6}Z")
HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
TOOK_RE = re.compile(r"took: \d+s")


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

    def test_dry_run_builtin_goal_matches_shell(self) -> None:
        self.assert_parity(["--dry-run"], stdin="reduce lines of code\n")

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
            ["--generations", "2", "--sleep", "0", "--output", "log"],
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
            inspect=self.inspect_results_and_history,
            extra_env=env,
        )

    def test_install_matches_shell(self) -> None:
        def fixture(workdir: Path, home: Path) -> None:
            pass

        self.assert_parity(["--install"], fixture=fixture, inspect=self.inspect_install)

    def test_claude_yolo_dry_run_matches_shell(self) -> None:
        self.assert_parity(["--agent", "claude", "--yolo", "--dry-run"], stdin="ship it\n")

    def test_opencode_yolo_warning_matches_shell(self) -> None:
        self.assert_parity(["--agent", "opencode", "--yolo", "--dry-run"], stdin="ship it\n")

    def test_unknown_option_matches_shell(self) -> None:
        self.assert_parity(["--wat"])

    def assert_parity(
        self,
        args: list[str],
        *,
        stdin: str | None = None,
        fixture=None,
        inspect=None,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        shell_result = self.run_variant(
            SHELL_ENTRYPOINT,
            args,
            stdin=stdin,
            fixture=fixture,
            inspect=inspect,
            extra_env=extra_env,
        )
        python_result = self.run_variant(
            PYTHON_ENTRYPOINT,
            args,
            stdin=stdin,
            fixture=fixture,
            inspect=inspect,
            extra_env=extra_env,
        )
        self.assertEqual(python_result, shell_result)

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
        normalized = value.replace(str(root), "<TMP>")
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
        artifacts = self.inspect_results_and_history(workdir, home, script_path)
        log_files = sorted(path.name for path in workdir.glob("psp_*_gen*.log"))
        self.assertEqual(len(log_files), 2)
        artifacts["log_files"] = [self.normalize_text(name, workdir.parent, script_path) for name in log_files]
        artifacts["log_contents"] = [
            self.normalize_text(path.read_text(encoding="utf-8"), workdir.parent, script_path)
            for path in sorted(workdir.glob("psp_*_gen*.log"))
        ]
        return artifacts

    def inspect_results_and_history(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        results = (workdir / "results.tsv").read_text(encoding="utf-8")
        history = (home / ".psp" / "history").read_text(encoding="utf-8")
        return {
            "results.tsv": self.normalize_text(results, workdir.parent, script_path),
            "history": self.normalize_text(history, workdir.parent, script_path),
        }

    def inspect_install(self, workdir: Path, home: Path, script_path: Path) -> dict[str, object]:
        link = home / ".local" / "bin" / "psp"
        config = home / ".psp" / "config.toml"
        zshrc = home / ".zshrc"
        bashrc = home / ".bashrc"
        return {
            "link_target": self.normalize_text(os.path.realpath(link), workdir.parent, script_path),
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


if __name__ == "__main__":
    unittest.main()
