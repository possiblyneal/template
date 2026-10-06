from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from test_preflight import git, git_output

MODULE_PATH = Path(__file__).parents[1] / "retrofit.py"
SETUP = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
PAYLOAD = MODULE_PATH.parents[4] / "apps/github-repository-template/src/base-repo"


def retrofit_fixture(directory: str) -> dict[str, str]:
    root = Path(directory) / "fixture"
    subprocess.run(
        ["python3", str(SETUP), "retrofit", str(root)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    fixture = json.loads((root / "fixture.json").read_text())
    fixture["base"] = git_output("rev-parse", "HEAD", cwd=fixture["destination"])
    return fixture


def payload_arguments(fixture: dict[str, str]) -> list[str]:
    return [
        "--template-repo",
        fixture["template_repo"],
        "--target",
        fixture["target_commit"],
        "--subtree",
        fixture["subtree"],
    ]


def records(candidate: Path) -> list[str]:
    """A record prefix beside the candidate, where a step's JSON lands."""
    return ["--records", str(candidate.parent / "records")]


def run(
    *arguments: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MODULE_PATH), *arguments],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class ProofsTests(unittest.TestCase):
    """Both proofs, measured from the index before the flow's first commit."""

    def _overlay(self, fixture: dict[str, str]) -> Path:
        """Write the payload over the destination and move its source, staged."""
        destination = Path(fixture["destination"])
        export = Path(fixture["template_repo"]).parent / "export"
        git("clone", "-q", fixture["template_repo"], str(export))
        git("checkout", "-q", fixture["target_commit"], cwd=export)
        payload = export / fixture["subtree"]
        shutil.rmtree(payload / "apps/app-name")
        shutil.copytree(payload, destination, dirs_exist_ok=True)

        (destination / "apps/ledger").mkdir(parents=True)
        git("mv", "src", "apps/ledger/src", cwd=destination)
        git("mv", "tests", "apps/ledger/tests", cwd=destination)
        # An edit riding along inside a move: the case rename purity exists for.
        moved_test = destination / "apps/ledger/tests/test_rates.py"
        moved_test.write_text(moved_test.read_text() + "# rode along\n")
        with (destination / "scripts/check").open("a") as check:
            check.write("# extended by the flow\n")
        (destination / ".gitignore").write_text("docs/agents/domain.md\n")
        git("add", "-A", cwd=destination)
        return destination

    def _proofs(self, fixture: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return run(*self._arguments(fixture))

    def _arguments(
        self, fixture: dict[str, str], records: Path | None = None
    ) -> list[str]:
        destination = Path(fixture["destination"])
        return [
            "proofs",
            "--records",
            str(records or destination.parent / "records"),
            *payload_arguments(fixture),
            "--candidate",
            fixture["destination"],
            "--base",
            fixture["base"],
        ]

    def test_counts_copies_and_names_what_differs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            self._overlay(fixture)
            result = self._proofs(fixture)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["schema_version"], 1)
            copy = report["copy"]
            self.assertEqual(
                copy["differing"],
                [{"class": "extended", "ignored": False, "path": "scripts/check"}],
            )
            self.assertEqual(copy["missing"], [])
            self.assertEqual(copy["total"], copy["identical"] + 1)
            self.assertIn(".gitignore", report["authored"])
            self.assertEqual(report["replaced"], [])

    def test_records_manifests_configuration_and_the_issue_tracker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            (destination / "apps/ledger/.unit.json").write_text("{}\n")
            (destination / "apps/ledger/pyproject.toml").write_text(
                '[project]\nname = "ledger"\n\n[tool.ruff]\n'
            )
            (destination / "docs/agents/issue-tracker.md").write_text(
                "# Issue tracker: Local markdown\n"
            )
            git("add", "-A", cwd=destination)
            result = self._proofs(fixture)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(
                report["manifests"],
                [
                    {
                        "path": "apps/ledger/pyproject.toml",
                        "status": "new",
                        "added": ["project.name", "tool.ruff"],
                        "changed": [],
                        "removed": [],
                    }
                ],
            )
            self.assertEqual(
                report["configuration"]["apps/ledger"], ["pyproject.toml [tool.ruff]"]
            )
            self.assertIn(".", report["configuration"])
            self.assertEqual(
                report["issue_tracker"], {"tracker": "Local markdown", "payload": False}
            )

    def test_names_a_destination_file_an_exact_copy_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = Path(fixture["destination"])
            lessons = destination / "docs/LESSONS.md"
            lessons.parent.mkdir(parents=True, exist_ok=True)
            lessons.write_text("# Our own lessons\n")
            git("add", "-A", cwd=destination)
            git("commit", "-q", "-m", "docs: lessons", cwd=destination)
            fixture = {
                **fixture,
                "base": git_output("rev-parse", "HEAD", cwd=destination),
            }
            self._overlay(fixture)
            report = json.loads(self._proofs(fixture).stdout)

            self.assertEqual(report["replaced"], ["docs/LESSONS.md"])
            self.assertIn("docs/LESSONS.md", report["copy"]["identical_paths"])

    def test_lists_every_byte_identical_copy_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            self._overlay(fixture)
            report = json.loads(self._proofs(fixture).stdout)

            paths = report["copy"]["identical_paths"]
            self.assertEqual(paths, sorted(paths))
            self.assertEqual(
                len(paths), report["copy"]["identical"] + report["unchanged"]
            )
            self.assertNotIn("scripts/check", paths)

    def test_accounts_for_applied_emptied_and_untriggered_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            residue = destination / "src/__pycache__"
            residue.mkdir(parents=True)
            (residue / "rates.pyc").write_bytes(b"")
            with (destination / ".git/info/exclude").open("a") as exclude:
                exclude.write("__pycache__/\n")
            workflows = destination / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text("on: [push, pull_request]\n")
            (workflows / "release.yml").write_text(
                "# not on pull_request\non: [push, pull_request_target]\n"
            )
            git("add", "-A", cwd=destination)
            # Untracked and not ignored holds the directory open just the same.
            (destination / "src/notes.txt").write_text("mine\n")
            prefix = Path(directory) / "ledger.aaaaaaaaaaaa"
            result = run(*self._arguments(fixture, prefix))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(Path(f"{prefix}.proofs.json").read_text(), result.stdout)
            self.assertEqual(report["payload_total"], report["copy"]["total"])
            # The destination ignores docs/agents/domain.md, so the branch never
            # carries that copy.
            self.assertEqual(report["applied"], report["copy"]["total"] - 1)
            self.assertEqual(report["unchanged"], 0)
            self.assertEqual(report["preserved"], [])
            emptied = {item["path"]: item["residue"] for item in report["emptied"]}
            self.assertEqual(emptied["tests"], [])
            self.assertIn("src/notes.txt", emptied["src"])
            self.assertTrue(all(path.startswith("src/") for path in emptied["src"]))
            self.assertEqual(
                report["workflows_without_pull_request"],
                [".github/workflows/release.yml"],
            )

    def test_reads_a_payload_path_the_destination_ignores_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            (destination / "docs/agents/domain.md").write_text("changed\n")
            report = json.loads(self._proofs(fixture).stdout)

            self.assertIn(
                {"class": "extended", "ignored": True, "path": "docs/agents/domain.md"},
                report["copy"]["differing"],
            )

    def test_leaves_an_overridden_path_out_of_every_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            (destination / ".repo-template.json").write_text(
                json.dumps(
                    {
                        "generation": {
                            "overrides": [{"path": "scripts/check", "reason": "ours"}]
                        }
                    }
                )
            )
            git("add", "-A", cwd=destination)
            report = json.loads(self._proofs(fixture).stdout)

            self.assertEqual(report["copy"]["differing"], [])
            self.assertEqual(
                report["payload_total"],
                report["copy"]["total"]
                + report["unchanged"]
                + len(report["preserved"])
                + len(report["overridden"])
                + len(report["copy"]["missing"]),
            )

    def test_names_a_payload_path_that_never_landed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            git("rm", "-q", "--cached", "docs/agents/triage-labels.md", cwd=destination)
            (destination / "docs/agents/triage-labels.md").unlink()
            report = json.loads(self._proofs(fixture).stdout)

            self.assertEqual(
                report["copy"]["missing"], ["docs/agents/triage-labels.md"]
            )

    def test_names_an_impure_move_with_its_line_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            self._overlay(fixture)
            purity = json.loads(self._proofs(fixture).stdout)["rename_purity"]

            impure = [move for move in purity["moves"] if not move["identical"]]
            self.assertEqual(
                [(m["to"], m["added"], m["removed"]) for m in impure],
                [("apps/ledger/tests/test_rates.py", 1, 0)],
            )
            self.assertEqual(purity["identical"], purity["total"] - 1)

    def test_names_a_move_edited_past_the_rename_threshold_as_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            (destination / "apps/ledger/tests/test_rates.py").write_text("rewritten\n")
            git("add", "-A", cwd=destination)
            report = json.loads(self._proofs(fixture).stdout)

            self.assertEqual(report["deleted"], ["tests/test_rates.py"])
            self.assertIn("apps/ledger/tests/test_rates.py", report["authored"])
            self.assertNotIn(
                "tests/test_rates.py",
                [move["from"] for move in report["rename_purity"]["moves"]],
            )

    def test_records_whether_the_candidate_carries_a_pre_commit_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            before = json.loads(self._proofs(fixture).stdout)
            (destination / ".pre-commit-config.yaml").write_text("repos: []\n")
            git("add", "-A", cwd=destination)
            after = json.loads(self._proofs(fixture).stdout)

            self.assertFalse(before["candidate"]["pre_commit_config"])
            self.assertTrue(after["candidate"]["pre_commit_config"])

    def test_refuses_an_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            result = self._proofs(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("nothing is staged", result.stderr)

    def test_refuses_once_the_flow_has_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = self._overlay(fixture)
            git("commit", "-q", "-m", "build: overlay", cwd=destination)
            result = self._proofs(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("commits past its base", result.stderr)


def candidate_repository(directory: str, files: dict[str, bytes]) -> Path:
    """A committed repository holding `files`, standing in for a candidate."""
    candidate = Path(directory) / "candidate"
    candidate.mkdir()
    git("init", "-q", cwd=candidate)
    git("config", "core.autocrlf", "false", cwd=candidate)
    for name, content in files.items():
        path = candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    git("add", "-A", cwd=candidate)
    git("commit", "-q", "-m", "chore: base", cwd=candidate)
    return candidate


def write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


class NormalizeTests(unittest.TestCase):
    """The rewrites the first commit would make, made before the proofs."""

    def test_renormalizes_line_endings_and_clears_stray_executable_bits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(directory, {"notes.txt": b"x\r\n"})
            (candidate / ".gitattributes").write_text("* text=auto eol=lf\n")
            (candidate / "docs").mkdir()
            git("mv", "notes.txt", "docs/notes.txt", cwd=candidate)
            write_script(candidate / "scripts/tool", "true")
            (candidate / "data.json").write_text("{}\n")
            (candidate / "data.json").chmod(0o755)
            # A NUL in its head reads as binary, which may be a real program.
            (candidate / "tool.bin").write_bytes(b"\x7fELF\0\0")
            (candidate / "tool.bin").chmod(0o755)
            git("add", "-A", cwd=candidate)
            result = run(
                "normalize", "--candidate", str(candidate), *records(candidate)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["renormalized"], ["docs/notes.txt"])
            self.assertEqual(report["executable_cleared"], ["data.json"])
            staged_binary = git_output("ls-files", "-s", "tool.bin", cwd=candidate)
            self.assertTrue(staged_binary.startswith("100755"))
            self.assertEqual(report["hooks_run"], [])
            staged = git_output("ls-files", "-s", "data.json", cwd=candidate)
            self.assertTrue(staged.startswith("100644"))

    def test_clears_an_executable_bit_where_git_ignores_file_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(directory, {"README.md": b"base\n"})
            (candidate / "data.json").write_text("{}\n")
            (candidate / "data.json").chmod(0o755)
            git("add", "-A", cwd=candidate)
            git("commit", "-q", "-m", "chore: data", cwd=candidate)
            git("config", "core.fileMode", "false", cwd=candidate)
            (candidate / "assets").mkdir()
            git("mv", "data.json", "assets/data.json", cwd=candidate)
            result = run(
                "normalize", "--candidate", str(candidate), *records(candidate)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            staged = git_output("ls-files", "-s", "assets/data.json", cwd=candidate)
            self.assertTrue(staged.startswith("100644"))

    @unittest.skipUnless(shutil.which("pre-commit"), "pre-commit is not installed")
    def test_stages_a_file_a_hook_wrote_and_no_other_untracked_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(directory, {"README.md": b"base\n"})
            (candidate / ".pre-commit-config.yaml").write_text(
                "repos:\n"
                "  - repo: local\n"
                "    hooks:\n"
                "      - id: 'adr-index'  # writes the index\n"
                "        name: adr-index\n"
                "        entry: sh -c 'echo index > index.md'\n"
                "        language: system\n"
                "        pass_filenames: false\n"
            )
            git("add", "-A", cwd=candidate)
            (candidate / "operator.txt").write_text("the bar disposes of this\n")
            result = run(
                "normalize", "--candidate", str(candidate), *records(candidate)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["hooks_run"], ["adr-index"])
            self.assertEqual(report["rewritten"], ["index.md"])
            self.assertEqual(
                git_output("ls-files", "--others", "--exclude-standard", cwd=candidate),
                "operator.txt",
            )

    @unittest.skipUnless(shutil.which("pre-commit"), "pre-commit is not installed")
    def test_runs_a_configured_rewriting_hook_and_restages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(directory, {"README.md": b"base\n"})
            (candidate / ".pre-commit-config.yaml").write_text(
                "repos:\n"
                "  - repo: local\n"
                "    hooks:\n"
                "      - id: trailing-whitespace\n"
                "        name: trailing-whitespace\n"
                "        entry: sed -i -e 's/[[:space:]]*$//'\n"
                "        language: system\n"
                "        types: [text]\n"
            )
            (candidate / "notes.md").write_text("trailing   \n")
            git("add", "-A", cwd=candidate)
            result = run(
                "normalize", "--candidate", str(candidate), *records(candidate)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["hooks_run"], ["trailing-whitespace"])
            self.assertEqual(report["rewritten"], ["notes.md"])
            self.assertEqual(report["still_failing"], [])
            self.assertEqual(git_output("show", ":notes.md", cwd=candidate), "trailing")


class FactsTests(unittest.TestCase):
    """Each unit's declared facts, executed once."""

    def test_reads_the_message_the_payloads_commands_print(self) -> None:
        for command in ("run", "package"):
            with self.subTest(command=command):
                script = (PAYLOAD / "scripts" / command).read_text()
                self.assertIn('echo "No project manifest found', script)

    def test_a_failed_step_leaves_no_earlier_record_behind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(directory, {"README.md": b"base\n"})
            stale = candidate.parent / "records.facts.json"
            stale.write_text("{}\n")
            result = run(
                "facts", "--candidate", str(candidate / "absent"), *records(candidate)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(stale.exists())

    def test_names_the_autofix_commit_and_an_adapterless_unit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(
                directory,
                {
                    "apps/ledger/.unit.json": (
                        b'{"schema_version": 1, "run": "none", "ships": {"kind": "none"}}\n'
                    ),
                    "apps/ledger/pyproject.toml": b'[project]\nname = "ledger"\n',
                },
            )
            (candidate / "README.md").write_text("fixed\n")
            git("add", "-A", cwd=candidate)
            git(
                "commit",
                "-q",
                "-m",
                "style: apply the destination's own autofix",
                cwd=candidate,
            )
            sha = git_output("rev-parse", "HEAD", cwd=candidate)
            write_script(candidate / "scripts/package", "exit 0")
            write_script(candidate / "scripts/run", "exit 0")
            result = run("facts", "--candidate", str(candidate), *records(candidate))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["autofix_commit"], sha)
            self.assertEqual(report["units"][0]["adapterless"], "python")

    def test_records_each_units_package_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(
                directory, {"apps/ledger/.unit.json": b"{}\n"}
            )
            write_script(candidate / "scripts/package", 'echo "boom $1"; exit 1')
            write_script(
                candidate / "scripts/run",
                'echo "No project manifest found here ($CI_DRY_RUN)"',
            )
            result = run("facts", "--candidate", str(candidate), *records(candidate))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["shipped"])
            self.assertEqual(
                report["units"],
                [
                    {
                        "unit": "ledger",
                        "adapterless": None,
                        "package": {
                            "exit": 1,
                            "tail": "boom ledger",
                            "no_manifest": False,
                        },
                        "run": {
                            "exit": 0,
                            "tail": "No project manifest found here (1)",
                            "no_manifest": True,
                        },
                    }
                ],
            )

    def test_reports_a_payload_that_ships_neither_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = candidate_repository(
                directory, {"apps/ledger/.unit.json": b"{}\n"}
            )
            report = json.loads(
                run("facts", "--candidate", str(candidate), *records(candidate)).stdout
            )

            self.assertEqual((report["shipped"], report["units"]), (False, []))


class AutofixTests(unittest.TestCase):
    """The destination's own autofix, with payload copies held to the payload."""

    def _arguments(self, fixture: dict[str, str], candidate: Path) -> list[str]:
        return [
            "autofix",
            *payload_arguments(fixture),
            "--candidate",
            str(candidate),
            "--records",
            str(candidate.parent / "records"),
        ]

    def _candidate(self, directory: str, fixture: dict[str, str]) -> Path:
        copy = git_output(
            "show",
            f"{fixture['target_commit']}:{fixture['subtree']}/docs/agents/domain.md",
            cwd=fixture["template_repo"],
        )
        candidate = candidate_repository(
            directory,
            {"docs/agents/domain.md": f"{copy}\n".encode(), "rates.py": b"x=1\n"},
        )
        write_script(
            candidate / "scripts/fix",
            "echo '# fixed' >> rates.py; echo '# fixed' >> docs/agents/domain.md",
        )
        git("add", "-A", cwd=candidate)
        git("commit", "-q", "-m", "chore: fix script", cwd=candidate)
        return candidate

    def test_reverts_a_payload_copy_the_pass_rewrote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            candidate = self._candidate(directory, fixture)
            result = run(*self._arguments(fixture, candidate))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["rewritten"], ["rates.py"])
            self.assertEqual(report["reverted"], ["docs/agents/domain.md"])
            self.assertEqual(report["passes"], 2)
            self.assertEqual(
                git_output("status", "--porcelain", cwd=candidate), "M rates.py"
            )

    def test_refuses_uncommitted_tracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            candidate = self._candidate(directory, fixture)
            (candidate / "rates.py").write_text("x = 2\n")
            result = run(*self._arguments(fixture, candidate))

            self.assertEqual(result.returncode, 2)
            self.assertIn("uncommitted changes", result.stderr)


def hook_environments_unavailable() -> str | None:
    """Why the payload's hooks cannot run here, or None when they can.

    The outcome checks run the real hooks, and pre-commit builds their
    environments from the network the first time. A stub would prove nothing
    about them, so a machine that cannot build them skips rather than passes.
    """
    if shutil.which("pre-commit") is None:
        return "pre-commit is not installed"
    built = subprocess.run(
        ["pre-commit", "install-hooks", "--config", ".pre-commit-config.yaml"],
        cwd=PAYLOAD,
        capture_output=True,
        text=True,
        check=False,
    )
    if built.returncode != 0:
        return "pre-commit could not build the payload's hook environments, offline?"
    return None


def write_hooks(directory: Path, hooks: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in hooks.items():
        hook = directory / name
        hook.write_text(body)
        hook.chmod(0o755)


class HooksTests(unittest.TestCase):
    """The destination clone's hooks, installed after the merge and proved."""

    def _merged(self, directory: str) -> Path:
        """The fixture clone once the merge landed the payload, on a feature branch.

        The payload itself stands in for the merged tree, because it is a tree
        its own hooks pass and the retrofit fixture's foreign layout is not.
        """
        reason = hook_environments_unavailable()
        if reason:
            self.skipTest(reason)
        fixture = retrofit_fixture(directory)
        destination = Path(fixture["destination"])
        git("rm", "-rq", ".", cwd=destination)
        shutil.copytree(PAYLOAD, destination, dirs_exist_ok=True)
        # The record a landed retrofit merge puts on the default branch.
        (destination / ".repo-template.json").write_text("{}\n")
        git("add", "-A", cwd=destination)
        git("commit", "-q", "-m", "build: land the payload", cwd=destination)
        git("push", "-q", "origin", "main", cwd=destination)
        git("checkout", "-q", "-b", "feature", cwd=destination)
        return destination

    def _env(
        self, directory: str, global_hooks: dict[str, str] | None = None
    ) -> dict[str, str]:
        """An operator's global config, isolated from this machine's, with a
        global hooks directory holding `global_hooks` where it is given."""
        root = Path(directory) / "global"
        root.mkdir()
        config = ""
        if global_hooks is not None:
            write_hooks(root / "hooks", global_hooks)
            config = f"[core]\n\thooksPath = {root / 'hooks'}\n"
        (root / "gitconfig").write_text(config)
        return {
            **os.environ,
            "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
            "GIT_AUTHOR_NAME": "Repo Builder Test",
            "GIT_AUTHOR_EMAIL": "repo-builder-test@example.invalid",
            "GIT_COMMITTER_NAME": "Repo Builder Test",
            "GIT_COMMITTER_EMAIL": "repo-builder-test@example.invalid",
        }

    def _hooks(
        self, destination: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return run(
            "hooks",
            "--clone",
            str(destination),
            "--default-branch",
            "main",
            "--resume-record",
            str(destination.parent / "record.json"),
            "--scratch",
            str(destination.parent / "hook-test"),
            "--records",
            str(destination.parent / "records"),
            env=env,
        )

    def _assert_proved(self, report: dict[str, object], destination: Path) -> None:
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            report["checks"],
            {
                "default_branch_refused": True,
                "malformed_subject_refused": True,
                "trailer_rewritten": True,
            },
        )
        self.assertEqual(
            git_output("config", "--local", "core.hooksPath", cwd=destination),
            str(destination / ".git/hooks"),
        )
        self.assertTrue(report["worktree_removed"])

    def test_installs_the_hooks_and_proves_all_three_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            fired = Path(directory) / "fired"
            hooks = destination / ".git/hooks"
            write_hooks(hooks, {"pre-commit": f'#!/bin/sh\ntouch "{fired}"\n'})
            result = self._hooks(destination, self._env(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self._assert_proved(report, destination)
            prior = {"scope": "default", "path": str(hooks)}
            self.assertEqual(report["prior_hooks"], prior)
            self.assertEqual(
                json.loads((destination.parent / "record.json").read_text()),
                {"prior_hooks": prior},
            )
            # The clone's own hook is chained, not destroyed: it fired.
            self.assertEqual(
                report["moved_aside"][0]["to"], str(hooks / "pre-commit.legacy")
            )
            self.assertTrue(fired.exists())
            self.assertEqual(report["chained"], [])
            self.assertEqual(
                git_output("worktree", "list", "--porcelain", cwd=destination).count(
                    "worktree "
                ),
                1,
            )
            self.assertEqual(
                git_output("for-each-ref", "--format=%(refname)", cwd=destination),
                "refs/heads/feature\nrefs/heads/main\nrefs/remotes/origin/main",
            )

    def test_chains_the_global_hooks_and_leaves_the_clones_own_dormant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            own_fired = Path(directory) / "own-fired"
            global_fired = Path(directory) / "global-fired"
            hooks = destination / ".git/hooks"
            # Dormant: git was reading the global directory, not this one.
            write_hooks(hooks, {"pre-commit": f'#!/bin/sh\ntouch "{own_fired}"\n'})
            env = self._env(
                directory,
                {
                    "pre-commit": f'#!/bin/sh\ntouch "{global_fired}"\n',
                    "prepare-commit-msg": (
                        PAYLOAD / "scripts/attribute-commit"
                    ).read_text(),
                    "post-rewrite": "#!/bin/sh\nexit 0\n",
                },
            )
            result = self._hooks(destination, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self._assert_proved(report, destination)
            global_dir = Path(directory) / "global/hooks"
            self.assertEqual(
                report["prior_hooks"], {"scope": "global", "path": str(global_dir)}
            )
            self.assertTrue(global_fired.exists())
            self.assertFalse(own_fired.exists())
            self.assertEqual(
                report["moved_aside"],
                [
                    {
                        "from": str(hooks / "pre-commit"),
                        "to": str(hooks / "pre-commit.dormant"),
                    }
                ],
            )
            self.assertEqual(
                sorted(
                    (Path(h["hook"]).name, h["disposition"]) for h in report["chained"]
                ),
                [
                    ("post-rewrite", "linked"),
                    ("pre-commit", "linked"),
                    ("prepare-commit-msg", "duplicate"),
                ],
            )
            self.assertEqual(
                (hooks / "pre-commit.legacy").resolve(), global_dir / "pre-commit"
            )

    def test_chains_a_local_hooks_path_and_reads_it_back_on_a_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            local_fired = Path(directory) / "local-fired"
            global_fired = Path(directory) / "global-fired"
            local_dir = Path(directory) / "local-hooks"
            write_hooks(
                local_dir, {"pre-commit": f'#!/bin/sh\ntouch "{local_fired}"\n'}
            )
            git("config", "core.hooksPath", str(local_dir), cwd=destination)
            env = self._env(
                directory, {"pre-commit": f'#!/bin/sh\ntouch "{global_fired}"\n'}
            )
            first = self._hooks(destination, env)

            self.assertEqual(first.returncode, 0, first.stderr)
            report = json.loads(first.stdout)
            self._assert_proved(report, destination)
            prior = {"scope": "local", "path": str(local_dir)}
            self.assertEqual(report["prior_hooks"], prior)
            self.assertTrue(local_fired.exists())
            self.assertFalse(global_fired.exists())

            # The key now names the shims, so only the record still knows.
            local_fired.unlink()
            second = self._hooks(destination, env)

            self.assertEqual(second.returncode, 0, second.stderr)
            resumed = json.loads(second.stdout)
            self._assert_proved(resumed, destination)
            self.assertEqual(resumed["prior_hooks"], prior)
            self.assertEqual(resumed["chained"], report["chained"])
            self.assertTrue(local_fired.exists())

    def test_reads_a_local_hooks_path_symlinked_to_its_own_hooks_in_place(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            fired = Path(directory) / "fired"
            hooks = destination / ".git/hooks"
            write_hooks(hooks, {"pre-commit": f'#!/bin/sh\ntouch "{fired}"\n'})
            link = Path(directory) / "hooks-link"
            link.symlink_to(hooks)
            git("config", "core.hooksPath", str(link), cwd=destination)
            result = self._hooks(destination, self._env(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self._assert_proved(report, destination)
            # Chained in place rather than renamed dormant and linked to itself.
            self.assertEqual(
                report["moved_aside"][0]["to"], str(hooks / "pre-commit.legacy")
            )
            self.assertEqual(report["chained"], [])
            self.assertTrue(fired.exists())

    def test_reports_a_worktree_it_could_not_remove_and_forces_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            # A chained hook that leaves a file no step commits.
            write_hooks(
                destination / ".git/hooks", {"pre-commit": "#!/bin/sh\ntouch stray\n"}
            )
            result = self._hooks(destination, self._env(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["worktree_removed"])
            self.assertIn("not removed", report["findings"][0])
            self.assertTrue((destination.parent / "hook-test/stray").exists())

    def test_refuses_before_the_merge_has_landed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = Path(fixture["destination"])
            result = self._hooks(destination, self._env(directory))

            self.assertEqual(result.returncode, 2)
            self.assertIn(".repo-template.json", result.stderr)

    def test_reports_not_applicable_where_the_payload_ships_no_hooks_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = Path(fixture["destination"])
            # The merge landed: its record is on the default branch, no hooks config.
            (destination / ".repo-template.json").write_text("{}\n")
            git("add", ".repo-template.json", cwd=destination)
            git("commit", "-q", "-m", "build: land the record", cwd=destination)
            git("push", "-q", "origin", "main", cwd=destination)
            result = self._hooks(destination, self._env(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["outcome"], "not-applicable")
            self.assertEqual(
                report["reason"],
                "the default branch carries no .pre-commit-config.yaml",
            )
            record = json.loads((destination.parent / "records.hooks.json").read_text())
            self.assertEqual(record, report)


if __name__ == "__main__":
    unittest.main()


class HookOutcomeTests(unittest.TestCase):
    """The refusals prove something only once a well-formed commit has landed."""

    def test_no_refusal_counts_when_every_commit_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory) / "tree"
            git("init", "-q", "-b", "main", str(tree), cwd=Path(directory))
            (tree / "docs").mkdir()
            git("commit", "-q", "--allow-empty", "-m", "chore: start", cwd=tree)
            refuse = tree / ".git/hooks/pre-commit"
            refuse.write_text("#!/bin/sh\nexit 1\n")
            refuse.chmod(0o755)
            script = (
                "import json, sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(MODULE_PATH.parent)!r}); import retrofit; "
                "print(json.dumps(retrofit.hook_outcomes(Path(sys.argv[1]), 'main')))"
            )

            result = subprocess.run(
                ["python3", "-c", script, str(tree)],
                text=True,
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    # This machine's own global hooks would run instead.
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "Repo Builder Test",
                    "GIT_AUTHOR_EMAIL": "repo-builder-test@example.invalid",
                    "GIT_COMMITTER_NAME": "Repo Builder Test",
                    "GIT_COMMITTER_EMAIL": "repo-builder-test@example.invalid",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "default_branch_refused": False,
                    "malformed_subject_refused": False,
                    "trailer_rewritten": False,
                },
            )


GH_STUB = """#!/usr/bin/env python3
import json, os, sys

arguments = sys.argv[1:]
with open(os.environ["GH_STUB_LOG"], "a") as log:
    log.write(json.dumps(arguments) + "\\n")
matches = [
    response
    for response in json.loads(os.environ["GH_STUB_RESPONSES"])
    if arguments[: len(response["args"])] == response["args"]
]
if not matches:
    sys.stderr.write("gh stub: no recorded response\\n")
    sys.exit(1)
response = max(matches, key=lambda response: len(response["args"]))
sys.stdout.write(response.get("stdout", ""))
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("status", 0))
"""


def stub_gh(directory: str, responses: list[dict[str, object]]) -> dict[str, str]:
    """An environment whose `gh` replays recorded responses and logs each call.

    The longest recorded argument prefix wins, and a call matching none exits
    1, so a request the subcommand was not expected to make fails the run.
    """
    bin_dir = Path(directory) / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_RESPONSES": json.dumps(responses),
        "GH_STUB_LOG": str(Path(directory) / "gh.log"),
    }


def gh_calls(directory: str) -> list[list[str]]:
    log = Path(directory) / "gh.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


class SyncTests(unittest.TestCase):
    """The operator's clone, brought onto a taken merge and cleared of residue."""

    def _merged(self, directory: str) -> Path:
        """A clone whose origin took a merge moving `src/` and `tests/` away.

        `src/` keeps ignored and untracked residue in the clone, which is what
        holds a directory open after the pull removes every tracked file.
        """
        clone = Path(retrofit_fixture(directory)["destination"])
        merge = Path(directory) / "merge"
        git("worktree", "add", "-q", "-b", "retrofit/abc1234", str(merge), cwd=clone)
        git("mv", "src", "apps-ledger-src", cwd=merge)
        git("rm", "-rq", "tests", cwd=merge)
        (merge / ".repo-template.json").write_text("{}\n")
        (merge / ".gitignore").write_text("__pycache__/\n")
        git("add", "-A", cwd=merge)
        git("commit", "-q", "-m", "chore: retrofit", cwd=merge)
        git("push", "-q", "origin", "retrofit/abc1234:main", cwd=merge)
        git("worktree", "remove", str(merge), cwd=clone)
        (clone / "src/ledger/__pycache__").mkdir()
        (clone / "src/ledger/__pycache__/rates.pyc").write_text("cached\n")
        (clone / "src/notes.txt").write_text("scratch\n")
        proofs = {
            "emptied": [
                {
                    "path": "src",
                    "residue": ["src/ledger/__pycache__/", "src/notes.txt"],
                },
                {"path": "tests", "residue": []},
            ]
        }
        Path(directory, "records.proofs.json").write_text(json.dumps(proofs))
        return clone

    def _sync(self, directory: str, clone: Path) -> dict:
        result = run(
            "sync",
            "--clone",
            str(clone),
            "--default-branch",
            "main",
            "--records",
            str(Path(directory) / "records"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_fast_forwards_and_removes_each_emptied_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._merged(directory)

            report = self._sync(directory, clone)

            self.assertTrue(report["pulled"])
            self.assertEqual(
                report["head"], git_output("rev-parse", "origin/main", cwd=clone)
            )
            self.assertEqual(
                report["removed"],
                [
                    {
                        "path": "src",
                        "residue": [
                            "src/ledger/__pycache__/rates.pyc",
                            "src/notes.txt",
                        ],
                    }
                ],
            )
            self.assertEqual(report["findings"], [])
            self.assertFalse((clone / "src").exists())
            self.assertTrue((clone / "apps-ledger-src/ledger/rates.py").is_file())

    def test_leaves_a_clone_with_another_branch_out_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._merged(directory)
            git("switch", "-q", "-c", "work", cwd=clone)

            report = self._sync(directory, clone)

            self.assertFalse(report["pulled"])
            self.assertEqual(report["removed"], [])
            self.assertEqual(
                report["findings"], ["the clone has work out, not main; not pulled"]
            )
            self.assertTrue((clone / "src/notes.txt").is_file())

    def test_leaves_a_clone_with_uncommitted_changes_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._merged(directory)
            with (clone / "README.md").open("a") as readme:
                readme.write("edited\n")

            report = self._sync(directory, clone)

            self.assertFalse(report["pulled"])
            self.assertEqual(
                report["findings"], ["the clone has uncommitted changes; not pulled"]
            )
            self.assertTrue((clone / "src/notes.txt").is_file())

    def test_keeps_a_directory_holding_a_file_the_plan_did_not_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._merged(directory)
            (clone / "src/save.dat").write_text("live\n")

            report = self._sync(directory, clone)

            self.assertTrue(report["pulled"])
            self.assertEqual(report["removed"], [])
            self.assertEqual(
                report["findings"],
                [
                    (
                        "src: not removed, since it holds src/save.dat, "
                        "which the plan did not name"
                    )
                ],
            )
            self.assertEqual(report["kept"], ["src"])
            self.assertTrue((clone / "src/save.dat").is_file())

    def test_a_rerun_records_a_removed_directory_as_gone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._merged(directory)
            self._sync(directory, clone)

            report = self._sync(directory, clone)

            self.assertEqual(report["removed"], [])
            self.assertEqual(report["gone"], ["src", "tests"])

    def test_refuses_before_the_merge_has_landed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(retrofit_fixture(directory)["destination"])
            Path(directory, "records.proofs.json").write_text('{"emptied": []}')

            result = run(
                "sync",
                "--clone",
                str(clone),
                "--default-branch",
                "main",
                "--records",
                str(Path(directory) / "records"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("after the merge has landed", result.stderr)


class SweepTests(unittest.TestCase):
    """The flow's own residue, taken down after the pull request is decided."""

    BRANCH = "retrofit/abc1234"

    def _candidate(self, directory: str) -> tuple[Path, Path]:
        """A retrofit worktree with one commit, its hooks dir and resume record."""
        fixture = retrofit_fixture(directory)
        clone = Path(fixture["destination"])
        candidate = Path(directory) / "candidate"
        git("worktree", "add", "-q", "-b", self.BRANCH, str(candidate), cwd=clone)
        (candidate / "scripts").mkdir(exist_ok=True)
        # The destination's own clean, which removes ignored build output the
        # worktree removal would otherwise trip over were it not ignored.
        clean = candidate / "scripts/clean"
        clean.write_text("#!/bin/sh\nrm -rf build\n")
        clean.chmod(0o755)
        (candidate / ".gitignore").write_text("build/\n")
        git("add", "-A", cwd=candidate)
        git("commit", "-q", "-m", "chore: retrofit", cwd=candidate)
        # Step 9's publish, which sets the upstream `branch -d` then reads.
        git("push", "-q", "-u", "origin", self.BRANCH, cwd=candidate)
        (candidate / "build").mkdir()
        (candidate / "build/output").write_text("built\n")
        (Path(directory) / "candidate-hooks").mkdir()
        (Path(directory) / "candidate.resume.json").write_text("{}\n")
        (Path(directory) / "candidate.writes.json").write_text("[]\n")
        return clone, candidate

    def _merge(self, clone: Path) -> None:
        """GitHub's merge; the clone's own main is never moved."""
        git("push", "-q", "origin", f"{self.BRANCH}:main", cwd=clone)

    def _sweep(
        self,
        directory: str,
        clone: Path,
        candidate: Path,
        repository: str = "owner/ledger",
    ) -> subprocess.CompletedProcess[str]:
        env = stub_gh(
            directory,
            [
                {
                    "args": [
                        "api",
                        f"repos/owner/ledger/pulls?head=owner:{self.BRANCH}&state=all",
                    ],
                    "stdout": json.dumps(
                        [
                            {
                                "number": 7,
                                "state": "closed",
                                "merged": False,
                                "url": "https://github.com/owner/ledger/pull/7",
                            }
                        ]
                    ),
                },
            ],
        )
        return run(
            "sweep",
            "--clone",
            str(clone),
            "--candidate",
            str(candidate),
            "--branch",
            self.BRANCH,
            "--default-branch",
            "main",
            "--repository",
            repository,
            "--hooks-dir",
            str(Path(directory) / "candidate-hooks"),
            "--resume-record",
            str(Path(directory) / "candidate.resume.json"),
            "--records",
            str(Path(directory) / "candidate"),
            env=env,
        )

    def test_deletes_a_merged_branch_after_its_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)
            self._merge(clone)

            result = self._sweep(directory, clone, candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(
                report["stages"],
                {
                    "fetch": "done",
                    "clean": "done",
                    "worktree": "done",
                    "prune": "done",
                    "hooks_dir": "removed",
                    "resume_record": "removed",
                    "write_log": "removed",
                    "branch": "deleted",
                },
            )
            self.assertEqual(report["left_for_the_operator"], [])
            self.assertEqual(report["findings"], [])
            self.assertFalse(candidate.exists())
            self.assertFalse((Path(directory) / "candidate-hooks").exists())
            self.assertEqual(
                git_output("branch", "--list", "retrofit/*", cwd=clone), ""
            )

    def test_keeps_a_declined_branch_and_names_its_pull_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)

            result = self._sweep(directory, clone, candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["stages"]["worktree"], "done")
            self.assertEqual(report["stages"]["branch"], "kept")
            self.assertEqual(
                report["left_for_the_operator"],
                [
                    {
                        "branch": self.BRANCH,
                        "reason": "not contained in origin/main, so its merge "
                        "was declined",
                        "pull_requests": [
                            {
                                "number": 7,
                                "state": "closed",
                                "merged": False,
                                "url": "https://github.com/owner/ledger/pull/7",
                            }
                        ],
                    }
                ],
            )
            self.assertIn(
                self.BRANCH, git_output("branch", "--list", "retrofit/*", cwd=clone)
            )

    def test_refuses_a_dirty_worktree_and_leaves_what_depends_on_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)
            self._merge(clone)
            (candidate / "uncommitted").write_text("a step wrote this\n")

            result = self._sweep(directory, clone, candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["stages"]["worktree"], "refused")
            self.assertNotIn("prune", report["stages"])
            self.assertEqual(report["stages"]["hooks_dir"], "skipped")
            self.assertEqual(report["stages"]["resume_record"], "skipped")
            self.assertEqual(report["stages"]["write_log"], "skipped")
            self.assertEqual(report["stages"]["branch"], "skipped")
            self.assertTrue(
                any("worktree refused" in finding for finding in report["findings"])
            )
            self.assertTrue((candidate / "uncommitted").exists())
            self.assertTrue((Path(directory) / "candidate-hooks").exists())
            self.assertEqual(
                report["left_for_the_operator"][0]["reason"],
                "left standing with its worktree, which can still be resumed",
            )

    def test_names_a_contained_branch_whose_deletion_was_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)
            self._merge(clone)
            # A second checkout of the branch is what `branch -d` refuses on.
            git(
                "worktree",
                "add",
                "-q",
                "--force",
                str(Path(directory) / "other"),
                self.BRANCH,
                cwd=clone,
            )

            result = self._sweep(directory, clone, candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["stages"]["branch"], "refused")
            self.assertEqual(
                report["left_for_the_operator"][0]["reason"],
                "contained in origin/main, but `branch -d` refused it",
            )

    def test_makes_no_github_call_for_an_origin_that_is_a_path(self) -> None:
        for origin in ("/srv/ledger", "../origin", "./origin", "remote/x"):
            with self.subTest(origin=origin):
                self._sweeps_a_path_origin_without_github(origin)

    def _sweeps_a_path_origin_without_github(self, origin: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)
            git("branch", "retrofit/old0000", cwd=clone)
            self._merge(clone)
            if origin == "remote/x":
                (clone / "remote" / "x").mkdir(parents=True)

            result = self._sweep(directory, clone, candidate, origin)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["stages"]["branch"], "deleted")
            self.assertEqual(
                report["pull_requests"],
                {
                    "outcome": "not-applicable",
                    "reason": "origin is a local path, not a GitHub repository",
                },
            )
            self.assertEqual(report["findings"], [])
            self.assertEqual(gh_calls(directory), [])

    def test_names_a_pull_request_lookup_it_could_not_make(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone, candidate = self._candidate(directory)
            git("branch", "retrofit/old0000", cwd=clone)
            self._merge(clone)

            result = self._sweep(directory, clone, candidate)

            report = json.loads(result.stdout)
            self.assertEqual(report["stages"]["branch"], "deleted")
            self.assertEqual(
                report["left_for_the_operator"],
                [
                    {
                        "branch": "retrofit/old0000",
                        "reason": "an earlier run at another payload commit",
                        "pull_requests": None,
                    }
                ],
            )
            self.assertEqual(
                report["findings"],
                ["could not read the pull requests for retrofit/old0000"],
            )
            self.assertIn(
                [
                    "api",
                    "repos/owner/ledger/pulls?head=owner:retrofit/old0000&state=all",
                ],
                [call[:2] for call in gh_calls(directory)],
            )


UPGRADE = {
    "stdout": json.dumps(
        {
            "message": "Upgrade to GitHub Pro or make this repository public to "
            "enable this feature.",
            "status": "403",
        }
    ),
    "status": 1,
}
FORBIDDEN = {
    "stdout": json.dumps({"message": "Resource not accessible", "status": "403"}),
    "status": 1,
}
NOT_FOUND = {
    "stdout": json.dumps({"message": "Not Found", "status": "404"}),
    "status": 1,
}
REPO = "repos/owner/ledger"


class HostedTests(unittest.TestCase):
    """The hosted-write gate's snapshot, and the writes it approved."""

    def _responses(self) -> list[dict[str, object]]:
        repo = {
            "visibility": "private",
            "default_branch": "main",
            "permissions": {"admin": True},
            "allow_merge_commit": False,
            "allow_squash_merge": True,
            "allow_rebase_merge": True,
            "delete_branch_on_merge": False,
            "security_and_analysis": {},
        }
        return [
            {"args": ["api", REPO], "stdout": json.dumps(repo)},
            {
                "args": ["api", "--paginate", f"{REPO}/labels"],
                "stdout": json.dumps([{"name": "bug"}, {"name": "Needs-Triage"}]),
            },
            {"args": ["api", f"{REPO}/vulnerability-alerts"], **NOT_FOUND},
            {
                "args": ["api", f"{REPO}/automated-security-fixes"],
                "stdout": json.dumps({"enabled": False, "paused": False}),
            },
            {"args": ["api", f"{REPO}/rulesets"], **UPGRADE},
            {"args": ["api", f"{REPO}/actions/runners"], **FORBIDDEN},
            {"args": ["api", "-X", "PATCH"], "stdout": "{}"},
            {"args": ["api", "-X", "POST"], "stdout": "{}"},
            {"args": ["api", "-X", "PUT", f"{REPO}/vulnerability-alerts"], **FORBIDDEN},
            {
                "args": ["api", "-X", "PUT", f"{REPO}/automated-security-fixes"],
                **UPGRADE,
            },
        ]

    def _apply(
        self, directory: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return run(
            "hosted",
            "apply",
            "--repository",
            "owner/ledger",
            "--records",
            str(Path(directory) / "candidate"),
            *arguments,
            env=stub_gh(directory, self._responses()),
        )

    def test_reads_the_gate_snapshot_and_classifies_each_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "hosted",
                "read",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                env=stub_gh(directory, self._responses()),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["visibility"], "private")
            self.assertEqual(
                report["merge_settings"],
                {
                    "allow_merge_commit": False,
                    "allow_squash_merge": True,
                    "allow_rebase_merge": True,
                    "delete_branch_on_merge": False,
                },
            )
            self.assertEqual(report["labels"], ["bug", "Needs-Triage"])
            self.assertEqual(
                report["dependabot"],
                {
                    "alerts": False,
                    "security_updates": {"enabled": False, "paused": False},
                },
            )
            self.assertEqual(report["push_protection"], "not offered")
            self.assertEqual(report["rulesets"]["refused"], "not offered")
            self.assertEqual(report["runner"]["refused"], "permissions gap")
            self.assertFalse(any("-X" in call for call in gh_calls(directory)))

    def test_performs_only_the_approved_writes_and_logs_each_reverse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._apply(
                directory,
                "--approve",
                "merge-settings",
                "--approve",
                "labels",
                "--label",
                "bug",
                "--label",
                "needs-triage",
                "--label",
                "wayfinder:map",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["writes"]["merge-settings"], "done")
            self.assertEqual(
                report["writes"]["labels"],
                {
                    "created": ["wayfinder:map"],
                    "renamed": [{"from": "Needs-Triage", "to": "needs-triage"}],
                    "skipped": [{"label": "bug", "reason": "exists"}],
                    "refused": [],
                },
            )
            self.assertEqual(report["findings"], [])
            writes = [call for call in gh_calls(directory) if "-X" in call]
            self.assertEqual(
                [call[3] for call in writes],
                [REPO, f"{REPO}/labels/Needs-Triage", f"{REPO}/labels"],
            )
            self.assertFalse(
                any("default_branch" in " ".join(call) for call in gh_calls(directory))
            )
            log = json.loads((Path(directory) / "candidate.writes.json").read_text())
            self.assertEqual(
                [entry["write"] for entry in log],
                ["merge-settings", "label:needs-triage", "label:wayfinder:map"],
            )
            self.assertEqual(
                log[2]["reverse_command"],
                ["gh", "api", "-X", "DELETE", f"{REPO}/labels/wayfinder%3Amap"],
            )

    def _reverse(
        self, directory: str, responses: list[dict[str, object]]
    ) -> tuple[dict[str, object], list[str]]:
        """The one logged write, and the call its reverse command sends."""
        log = json.loads((Path(directory) / "candidate.writes.json").read_text())
        self.assertEqual(len(log), 1)
        reverse_dir = Path(directory) / "reverse"
        reverse_dir.mkdir()
        subprocess.run(
            log[0]["reverse_command"],
            check=True,
            capture_output=True,
            env=stub_gh(str(reverse_dir), responses),
        )
        return log[0], gh_calls(str(reverse_dir))[0]

    def test_a_logged_reverse_command_sends_the_recorded_before_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._apply(directory, "--approve", "merge-settings")
            entry, sent = self._reverse(directory, self._responses())

            self.assertEqual(sent[:4], ["api", "-X", "PATCH", REPO])
            self.assertEqual(
                {
                    field: json.loads(value)
                    for field, value in (flag.split("=", 1) for flag in sent[5::2])
                },
                entry["before"],
            )

    def test_push_protection_reverses_to_its_recorded_before_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = {
                "visibility": "public",
                "permissions": {"admin": True},
                "security_and_analysis": {
                    "secret_scanning_push_protection": {"status": "disabled"}
                },
            }
            responses: list[dict[str, object]] = [
                {"args": ["api", REPO], "stdout": json.dumps(repo)},
                *self._responses(),
            ]
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "push-protection",
                env=stub_gh(directory, responses),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entry, sent = self._reverse(directory, responses)
            self.assertEqual(entry["before"], "disabled")
            self.assertEqual(
                sent,
                [
                    "api",
                    "-X",
                    "PATCH",
                    REPO,
                    "-f",
                    (
                        "security_and_analysis[secret_scanning_push_protection]"
                        "[status]=disabled"
                    ),
                ],
            )

    def test_the_runner_variable_reverses_to_its_recorded_before_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runners = {"runners": [{"name": "dev-ledger", "status": "online"}]}
            responses: list[dict[str, object]] = [
                {
                    "args": ["api", f"{REPO}/actions/runners"],
                    "stdout": json.dumps(runners),
                },
                {
                    "args": ["api", f"{REPO}/actions/variables/RUNNER"],
                    "stdout": json.dumps({"name": "RUNNER", "value": "ubuntu-latest"}),
                },
                {"args": ["variable", "set"]},
                *self._responses(),
            ]
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "runner-variable",
                env=stub_gh(directory, responses),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["writes"], {"runner-variable": "done"}
            )
            entry, sent = self._reverse(directory, responses)
            self.assertEqual(entry["before"], "ubuntu-latest")
            self.assertEqual(
                sent,
                [
                    "variable",
                    "set",
                    "RUNNER",
                    "--body",
                    "ubuntu-latest",
                    "-R",
                    "owner/ledger",
                ],
            )

    def test_names_an_upgrade_refusal_not_offered_and_a_403_a_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._apply(
                directory,
                "--approve",
                "dependabot-alerts",
                "--approve",
                "security-updates",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(
                report["writes"],
                {
                    "dependabot-alerts": "permissions gap",
                    "security-updates": "not offered",
                },
            )
            self.assertEqual(len(report["findings"]), 1)
            self.assertTrue(report["findings"][0].startswith("dependabot-alerts:"))
            self.assertFalse((Path(directory) / "candidate.writes.json").exists())

    def test_a_resumed_apply_never_repeats_a_logged_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._apply(directory, "--approve", "merge-settings")
            first = json.loads((Path(directory) / "candidate.writes.json").read_text())
            (Path(directory) / "gh.log").unlink()
            shutil.rmtree(Path(directory) / "bin")

            result = self._apply(directory, "--approve", "merge-settings")

            self.assertEqual(
                json.loads(result.stdout)["writes"], {"merge-settings": "logged"}
            )
            self.assertEqual(gh_calls(directory), [])
            self.assertEqual(
                json.loads((Path(directory) / "candidate.writes.json").read_text()),
                first,
            )

    def test_a_later_apply_keeps_the_writes_an_earlier_one_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._apply(directory, "--approve", "runner-variable")
            shutil.rmtree(Path(directory) / "bin")

            result = self._apply(directory, "--approve", "merge-settings")

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(
                (Path(directory) / "candidate.hosted-apply.json").read_text()
            )
            self.assertEqual(
                record["writes"],
                {"merge-settings": "done", "runner-variable": "not offered"},
            )
            self.assertIn("runner-variable", record["reasons"])
            self.assertEqual(
                [entry["write"] for entry in record["write_log"]["entries"]],
                ["merge-settings"],
            )

    def test_an_apply_after_the_sweep_does_not_build_on_the_last_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._apply(directory, "--approve", "runner-variable")
            shutil.rmtree(Path(directory) / "bin")
            (Path(directory) / "candidate.sweep.json").write_text("{}\n")

            result = self._apply(directory, "--approve", "merge-settings")

            self.assertEqual(
                json.loads(result.stdout)["writes"], {"merge-settings": "done"}
            )

    def test_a_sweep_from_an_earlier_run_does_not_stop_the_carry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sweep = Path(directory) / "candidate.sweep.json"
            sweep.write_text("{}\n")
            os.utime(sweep, (0, 0))
            self._apply(directory, "--approve", "runner-variable")
            shutil.rmtree(Path(directory) / "bin")

            result = self._apply(directory, "--approve", "merge-settings")

            self.assertEqual(
                json.loads(result.stdout)["writes"],
                {"merge-settings": "done", "runner-variable": "not offered"},
            )

    def test_an_unreadable_earlier_apply_record_counts_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "candidate.hosted-apply.json").write_text('{"wri')

            result = self._apply(directory, "--approve", "merge-settings")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["writes"], {"merge-settings": "done"}
            )

    def test_a_created_ruleset_is_reversed_by_deleting_its_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "ruleset.json"
            body.write_text('{"name": "main"}\n')
            responses: list[dict[str, object]] = [
                *self._responses(),
                {
                    "args": ["api", "-X", "POST", f"{REPO}/rulesets"],
                    "stdout": '{"id": 42}',
                },
            ]
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "ruleset",
                "--ruleset",
                str(body),
                env=stub_gh(directory, responses),
            )

            self.assertEqual(json.loads(result.stdout)["writes"], {"ruleset": "done"})
            log = json.loads((Path(directory) / "candidate.writes.json").read_text())
            self.assertEqual(
                log[0]["reverse_command"],
                ["gh", "api", "-X", "DELETE", f"{REPO}/rulesets/42"],
            )

    def test_push_protection_hidden_from_a_non_admin_is_a_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = {"visibility": "public", "permissions": {"admin": False}}
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "push-protection",
                env=stub_gh(
                    directory, [{"args": ["api", REPO], "stdout": json.dumps(repo)}]
                ),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["writes"], {"push-protection": "permissions gap"})
            self.assertEqual(len(report["findings"]), 1)
            self.assertTrue(report["findings"][0].startswith("push-protection:"))

    def test_a_replaced_ruleset_is_saved_without_its_read_only_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "ruleset.json"
            body.write_text('{"name": "main"}\n')
            current = {
                "id": 7,
                "node_id": "RRS_7",
                "_links": {"self": {"href": "x"}},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "source": "owner/ledger",
                "source_type": "Repository",
                "current_user_can_bypass": "never",
                "name": "protect",
                "target": "branch",
                "enforcement": "active",
                "rules": [{"type": "deletion"}],
            }
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "ruleset",
                "--ruleset",
                str(body),
                "--replace-ruleset",
                "7",
                env=stub_gh(
                    directory,
                    [
                        {
                            "args": ["api", f"{REPO}/rulesets/7"],
                            "stdout": json.dumps(current),
                        },
                        {"args": ["api", "-X", "PUT"], "stdout": "{}"},
                    ],
                ),
            )

            self.assertEqual(json.loads(result.stdout)["writes"], {"ruleset": "done"})
            log = json.loads((Path(directory) / "candidate.writes.json").read_text())
            saved = json.loads(Path(log[0]["before"]).read_text())
            self.assertEqual(
                saved,
                {
                    "name": "protect",
                    "target": "branch",
                    "enforcement": "active",
                    "rules": [{"type": "deletion"}],
                },
            )

    def test_labels_created_before_a_refusal_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "hosted",
                "apply",
                "--repository",
                "owner/ledger",
                "--records",
                str(Path(directory) / "candidate"),
                "--approve",
                "labels",
                "--label",
                "first",
                "--label",
                "second",
                "--label",
                "third",
                env=stub_gh(
                    directory,
                    [
                        *self._responses(),
                        {
                            "args": [
                                "api",
                                "-X",
                                "POST",
                                f"{REPO}/labels",
                                "-f",
                                "name=second",
                            ],
                            **FORBIDDEN,
                        },
                    ],
                ),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            labels = report["writes"]["labels"]
            self.assertEqual(labels["created"], ["first"])
            self.assertEqual(
                [(item["label"], item["outcome"]) for item in labels["refused"]],
                [("second", "permissions gap")],
            )
            self.assertEqual(len(report["findings"]), 1)
            self.assertTrue(report["findings"][0].startswith("labels:"))
            log = json.loads((Path(directory) / "candidate.writes.json").read_text())
            self.assertEqual([entry["write"] for entry in log], ["label:first"])


PROOFS = {
    "operation": "proofs",
    "template": {"commit": "a" * 40, "subtree": "base-repo"},
    "candidate": {"path": "/r/tmp/ledger", "base": "b" * 40, "pre_commit_config": True},
    "copy": {
        "identical": 61,
        "total": 63,
        "differing": [
            {"path": "CLAUDE.md", "class": "merged", "ignored": False},
            {"path": "scripts/check", "class": "extended", "ignored": False},
        ],
        "missing": [],
    },
    "rename_purity": {
        "identical": 1,
        "total": 2,
        "moves": [
            {
                "from": "src/rates.py",
                "to": "apps/ledger/src/rates.py",
                "similarity": 100,
                "identical": True,
                "added": 0,
                "removed": 0,
            },
            {
                "from": "tests/test_rates.py",
                "to": "apps/ledger/tests/test_rates.py",
                "similarity": 96,
                "identical": False,
                "added": 1,
                "removed": 0,
            },
        ],
    },
    "authored": [".repo-template.json", "docs/adrs/0001-one-ledger.md"],
    "deleted": ["docs/adr/0001-one-ledger.md"],
    "payload_total": 66,
    "applied": 58,
    "unchanged": 1,
    "preserved": [".gitignore"],
    "replaced": ["README.md"],
    "overridden": [{"path": "README.md", "reason": "the product's own front page"}],
    "emptied": [
        {"path": "docs/adr", "residue": []},
        {"path": "src", "residue": []},
    ],
    "workflows_without_pull_request": [".github/workflows/release.yml"],
}
HOOKS = {
    "operation": "hooks",
    "hooks_path": "/home/op/ledger/.git/hooks",
    "prior_hooks": {"scope": "global", "path": "/home/op/.config/git/hooks"},
    "moved_aside": [{"from": "pre-commit", "to": "pre-commit.dormant"}],
    "chained": [{"hook": "commit-msg", "disposition": "duplicate"}],
    "checks": {
        "default_branch_refused": True,
        "malformed_subject_refused": True,
        "trailer_rewritten": True,
    },
    "worktree_removed": True,
    "findings": [],
}
SWEEP_STAGES = {
    "fetch": "done",
    "clean": "done",
    "worktree": "done",
    "prune": "done",
    "hooks_dir": "removed",
    "write_log": "removed",
    "branch": "deleted",
}
SWEEP = {
    "operation": "sweep",
    "clone": {"path": "/home/op/ledger", "default_branch": "main"},
    "candidate": {"path": "/r/tmp/ledger", "branch": "retrofit/aaaaaaaaaaaa"},
    "scratch": {
        "hooks_dir": "/r/tmp/ledger-hooks",
        "write_log": "/r/tmp/ledger.writes.json",
    },
    "stages": SWEEP_STAGES,
    "left_for_the_operator": [
        {
            "branch": "retrofit/000000000000",
            "reason": "an earlier run at another payload commit",
            "pull_requests": [
                {
                    "number": 3,
                    "state": "open",
                    "merged": False,
                    "url": "https://github.com/o/ledger/pull/3",
                }
            ],
        }
    ],
    "findings": [],
}
HOSTED_READ = {"operation": "hosted read", "visibility": "private"}
HOSTED_APPLY = {
    "operation": "hosted apply",
    "writes": {
        "merge-settings": "done",
        "labels": {
            "created": ["wayfinder:map"],
            "renamed": [{"from": "Bug", "to": "bug"}],
            "skipped": [{"label": "enhancement", "reason": "exists"}],
        },
        "dependabot-alerts": "already set",
        "push-protection": "not offered",
        "ruleset": "permissions gap",
    },
    "write_log": {
        "path": "/r/tmp/ledger.writes.json",
        "entries": [
            {
                "write": "merge-settings",
                "before": {"allow_squash_merge": True},
                "after": {"allow_squash_merge": False},
                "reverse_command": [
                    "gh",
                    "api",
                    "-X",
                    "PATCH",
                    "repos/o/ledger",
                    "-F",
                    "allow_squash_merge=true",
                ],
            }
        ],
    },
    "reasons": {"ruleset": "Resource not accessible (HTTP 403)"},
    "findings": ["ruleset: Resource not accessible (HTTP 403)"],
}
SUMMARY_PASS = "lint               pass             ruff\ntest               pass             pytest\n"
SUMMARY_FAIL = (
    "lint               FAIL             ruff\n"
    "                     apps/ledger/src/rates.py:3 F401\n"
    "test               unavailable      no test runner found\n"
)


def render_report(
    case: unittest.TestCase, directory: str, summary: str, **inputs: object
) -> tuple[list[str], list[str]]:
    """Render the report from `inputs`: a dict is a record, anything else a flag."""
    # A fresh prefix per render, so one render's records never reach the next.
    prefix = Path(tempfile.mkdtemp(dir=directory)) / "ledger.aaaaaaaaaaaa"
    arguments = ["report", "--repository", "o/ledger", "--records", str(prefix)]
    for name, value in inputs.items():
        if isinstance(value, dict):
            record = name.replace("_", "-")
            Path(f"{prefix}.{record}.json").write_text(json.dumps(value))
        elif value is True:
            arguments.append("--" + name.replace("_", "-"))
        else:
            arguments += ["--" + name.replace("_", "-"), str(value)]
    Path(f"{prefix}.check.txt").write_text(summary)
    result = run(*arguments)
    case.assertEqual(result.returncode, 0, result.stderr)
    output = Path(json.loads(result.stdout)["path"])
    case.assertEqual(output, Path(f"{prefix}.report.md"))
    return output.read_text().splitlines(), json.loads(result.stdout)["slots"]


class ReportTests(unittest.TestCase):
    """The final report's deterministic lines, rendered from recorded JSON."""

    def test_renders_a_finished_run_from_every_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hooks=HOOKS,
                sweep=SWEEP,
                hosted_read=HOSTED_READ,
                hosted_apply=HOSTED_APPLY,
                pull_request="https://github.com/o/ledger/pull/9",
            )

            for line in (
                "- Status: finished",
                "- Pull request: https://github.com/o/ledger/pull/9",
                f"- Template: not previously generated -> {'a' * 40}",
                "- Layout plan: src/rates.py -> apps/ledger/src/rates.py: moved",
                (
                    "- Renamed/deleted: src/rates.py -> apps/ledger/src/rates.py, "
                    "tests/test_rates.py -> apps/ledger/tests/test_rates.py, "
                    "docs/adr/0001-one-ledger.md deleted"
                ),
                (
                    "- Authored surface: CLAUDE.md (merged), scripts/check (extended), "
                    ".repo-template.json, docs/adrs/0001-one-ledger.md, "
                    "apps/ledger/tests/test_rates.py "
                    "(moved from tests/test_rates.py, +1/-0)"
                ),
                "- Destination visibility: private",
                "- Merge settings (merge commit only, head branches deleted): enabled",
                "- Push protection: unavailable (not offered for the plan)",
                "- Branch ruleset: unavailable (permissions gap)",
                "- Runner variable: not requested",
                (
                    '- merge-settings: was {"allow_squash_merge": true} -> '
                    '{"allow_squash_merge": false}; reverse with '
                    "`gh api -X PATCH repos/o/ledger -F allow_squash_merge=true`"
                ),
                "- Permissions gap: ruleset: Resource not accessible (HTTP 403)",
                "- `scripts/check`: pass",
                (
                    "- Copied paths byte-identical to their source: 61/63; the rest are "
                    "the authored surface, under File list. An overridden path is in "
                    "neither count, under Reconciliation instead"
                ),
                "- Moved paths byte-identical to their pre-move blob: 1/2",
                "- Bar: met",
                "- Candidate: removed from /r/tmp/ledger, branch retrofit/aaaaaaaaaaaa deleted",
                (
                    "- Scratch outside the candidate: /r/tmp/ledger-hooks: removed, "
                    "/r/tmp/ledger.writes.json: removed"
                ),
            ):
                self.assertIn(line, lines)
            self.assertTrue(
                any(
                    line.startswith(
                        "- Left for the operator: retrofit/000000000000: an earlier "
                        "run at another payload commit; pull request "
                        "https://github.com/o/ledger/pull/3 (open); [[FILL: "
                    )
                    for line in lines
                )
            )
            self.assertTrue(
                any(
                    line.startswith("- Issue tracker: [[FILL: ")
                    and line.endswith(
                        "labels: created (wayfinder:map); renamed to the payload's "
                        "spelling (Bug -> bug; label search is case-sensitive, so "
                        "anything pinned to the old string stops matching); already "
                        "present (enhancement)"
                    )
                    for line in lines
                )
            )
            self.assertIn(
                "- Destination hooks after merge: shims in /home/op/ledger/.git/hooks, "
                "`core.hooksPath` pinned local to it, prior hooks: "
                "/home/op/.config/git/hooks (global), moved aside: pre-commit -> "
                "pre-commit.dormant, chained: commit-msg duplicate, verified by "
                "default_branch_refused, malformed_subject_refused, trailer_rewritten",
                lines,
            )
            self.assertEqual(lines[-1], "none")
            self.assertNotIn("### Resumption", lines)
            filled = sum(line.count("[[FILL: ") for line in lines)
            self.assertEqual(filled, len(slots))
            self.assertIn("default-branch: check-suite result", slots)

    def test_names_a_destination_whose_origin_is_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, repository="/srv/ledger"
            )

            self.assertIn("- Destination: /srv/ledger", lines)
            self.assertTrue(
                any(
                    line.startswith("- ADR fields defaulted: [[FILL: ")
                    for line in lines
                )
            )

    def test_renders_a_sweep_without_pull_requests_as_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sweep = {
                **SWEEP,
                "pull_requests": {
                    "outcome": "not-applicable",
                    "reason": "origin is a local path, not a GitHub repository",
                },
                "left_for_the_operator": [],
            }
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                sweep=sweep,
                repository="/srv/ledger",
            )

            left = next(
                line for line in lines if line.startswith("- Left for the operator")
            )
            self.assertIn(
                "pull requests: n/a (origin is a local path, not a GitHub repository)",
                left,
            )

    def test_renders_a_run_stopped_at_the_gate_as_reaching_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read=HOSTED_READ,
                stopped="the operator declined every hosted write",
            )

            self.assertIn("- Runner variable: not requested", lines)
            self.assertNotIn("not reached", "\n".join(lines))

    def test_renders_settings_nothing_was_written_for_from_the_hosted_read(
        self,
    ) -> None:
        hosted_read = {
            "operation": "hosted read",
            "visibility": "private",
            "merge_settings": {
                "allow_merge_commit": True,
                "allow_squash_merge": True,
                "allow_rebase_merge": True,
                "delete_branch_on_merge": False,
            },
            "dependabot": {
                "alerts": True,
                "security_updates": {"enabled": True, "paused": False},
            },
            "push_protection": "not offered",
            "rulesets": {"refused": "not offered", "detail": "Upgrade (HTTP 403)"},
            "runner": "absent",
        }
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read=hosted_read,
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            for line in (
                "- Merge settings (merge commit only, head branches deleted): not requested",
                "- Dependabot alerts: enabled (already set before the retrofit)",
                "- Dependabot security updates: enabled (already set before the retrofit)",
                "- Push protection: unavailable (not offered for the plan)",
                "- Branch ruleset: unavailable (not offered for the plan)",
                "- Runner variable: not offered (the dev runner is absent)",
            ):
                self.assertIn(line, lines)

    def test_a_refused_runner_reading_is_not_a_decline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read={
                    "operation": "hosted read",
                    "visibility": "private",
                    "runner": {"refused": "permissions gap", "detail": "403"},
                },
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            self.assertIn("- Runner variable: unavailable (permissions gap)", lines)

    def test_an_active_ruleset_is_already_on(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read={
                    "operation": "hosted read",
                    "visibility": "private",
                    "rulesets": [
                        {
                            "id": 1,
                            "name": "main",
                            "target": "branch",
                            "enforcement": "active",
                        }
                    ],
                },
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            self.assertIn(
                "- Branch ruleset: enabled (already set before the retrofit)", lines
            )

    def test_a_tag_ruleset_is_not_a_branch_ruleset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read={
                    "operation": "hosted read",
                    "visibility": "private",
                    "rulesets": [
                        {
                            "id": 1,
                            "name": "releases",
                            "target": "tag",
                            "enforcement": "active",
                        }
                    ],
                },
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            self.assertIn("- Branch ruleset: not requested", lines)

    def test_a_disabled_ruleset_is_not_on(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read={
                    "operation": "hosted read",
                    "visibility": "private",
                    "rulesets": [
                        {
                            "id": 1,
                            "name": "main",
                            "target": "branch",
                            "enforcement": "disabled",
                        }
                    ],
                },
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            self.assertIn("- Branch ruleset: not requested", lines)

    def test_renders_a_runner_variable_on_a_public_destination_as_not_offered(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read={
                    "operation": "hosted read",
                    "visibility": "public",
                    "runner": "online",
                },
            )

            self.assertIn(
                "- Runner variable: not offered (the repository is public)", lines
            )

    def test_names_the_records_a_lookup_line_needed_and_did_not_find(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, hooks=HOOKS
            )

            for line in (
                "- Destination visibility: unknown (hosted read did not run)",
                "- Dependabot alerts: unknown (hosted read did not run)",
                "- Runner variable: unknown (hosted read did not run)",
                "- Already held: unknown (preflight did not run)",
            ):
                self.assertIn(line, lines)
            self.assertTrue(
                any(
                    line.startswith("- Issue tracker: [[FILL: ")
                    and line.endswith("labels: none created (hosted apply did not run)")
                    for line in lines
                )
            )
            self.assertIn(
                "- Hooks: installed at worktree scope into a directory the sweep "
                "records (sweep did not run); `extensions.worktreeConfig` set on "
                "the clone (preflight did not run) and left set",
                lines,
            )
            self.assertNotIn("public or private, read from the API", slots)
            self.assertNotIn("candidate path", slots)

    def test_reads_the_clone_from_preflight_where_the_sweep_did_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                preflight={
                    "operation": "retrofit",
                    "addons_present": ["CHANGELOG.md"],
                    "destination": {"path": "/home/op/ledger"},
                },
            )

            self.assertIn("- Already held: CHANGELOG.md", lines)
            self.assertIn(
                "- Hooks: installed at worktree scope into a directory the sweep "
                "records (sweep did not run); `extensions.worktreeConfig` set on "
                "/home/op/ledger and left set",
                lines,
            )

    def test_names_a_hosted_apply_that_ran_without_labels_as_a_judgement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_apply={"operation": "hosted apply", "writes": {}},
            )

            self.assertIn("labels-reason: reason no labels were created", slots)
            self.assertIn("- Runner variable: unknown (hosted read did not run)", lines)

    def test_renders_a_stopped_unmet_bar_with_nothing_hosted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_FAIL,
                proofs=PROOFS,
                stopped="the bar is unmet",
            )

            for line in (
                "- Status: stopped (the bar is unmet)",
                "- Pull request: not created",
                "- `scripts/check`: fail (lint)",
                "  - lint: apps/ledger/src/rates.py:3 F401",
                (
                    "- Bar: UNMET: lint: fail; test: unavailable (no test runner found); "
                    "stopped before the pull request, zero hosted writes performed"
                ),
                "- Default branch after merge: n/a (nothing merged)",
                "- Destination hooks after merge: n/a (stopped before the merge was offered)",
                (
                    "- Merge settings (merge commit only, head branches deleted): "
                    "not reached (stopped before the gate)"
                ),
                "- Runner variable: not reached (stopped before the gate)",
                "- none performed",
                "- Permissions gap: none",
            ):
                self.assertIn(line, lines)
            self.assertNotIn("not requested", "\n".join(lines))
            left = [
                line for line in lines if line.startswith("- Left for the operator:")
            ]
            self.assertEqual(
                left,
                [
                    (
                        "- Left for the operator: [[FILL: left-for-the-operator: "
                        "each other path left in place and why, or none]]"
                    )
                ],
            )
            self.assertIn(
                "- Candidate: left standing at /r/tmp/ledger, because the flow "
                "stopped and resumes from it",
                lines,
            )
            self.assertTrue(lines[-1].startswith("[[FILL: "))
            self.assertIn(
                "fix-prepared: the unmet-bar outcome, in the Report additions shape",
                slots,
            )

    def test_reports_destination_hooks_not_applicable_where_the_payload_ships_none(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hooks={
                    "operation": "hooks",
                    "outcome": "not-applicable",
                    "reason": "the default branch carries no .pre-commit-config.yaml",
                },
            )

            self.assertIn(
                "- Destination hooks after merge: n/a (no hooks config on the "
                "default branch)",
                lines,
            )

    def test_reports_no_hooks_where_the_candidate_carries_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {
                **PROOFS,
                "candidate": {
                    "path": "/r/tmp/ledger",
                    "base": "b" * 40,
                    "pre_commit_config": False,
                },
            }
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=proofs,
                stopped="awaiting the gate",
            )

            self.assertIn(
                "- Hooks: none installed, because the candidate carries no "
                "`.pre-commit-config.yaml` to read hook types from",
                lines,
            )
            self.assertNotIn("the candidate hooks directory", slots)

    def test_a_nonzero_exit_outside_the_result_table_fails_the_bar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS
                + "\nscripts/check exited 1 with no failing result line: the "
                "failure is outside the\nResult table.\n",
                proofs=PROOFS,
                stopped="the bar is unmet",
            )

            self.assertIn("- `scripts/check`: fail (exit-status)", lines)
            self.assertIn(
                "  - exit-status: scripts/check exited 1 outside the Result table",
                lines,
            )
            self.assertNotIn("- Bar: met", lines)
            self.assertTrue(
                any(
                    line.startswith("- Bar: UNMET: exit-status: fail") for line in lines
                )
            )

    def test_reads_ruleset_enforcement_and_the_branch_from_their_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apply = {
                **HOSTED_APPLY,
                "writes": {"ruleset": "done"},
                "findings": [],
            }
            stages = {**SWEEP_STAGES, "branch": "refused"}
            sweep = {**SWEEP, "stages": stages}
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hooks=HOOKS,
                sweep=sweep,
                hosted_apply=apply,
                pull_request="https://github.com/o/ledger/pull/9",
            )

            self.assertIn(
                "ruleset-enforcement: step 9's mergeable/mergeStateStatus reading "
                "of the pull request",
                slots,
            )
            self.assertIn(
                "- Candidate: worktree removed from /r/tmp/ledger, branch "
                "retrofit/aaaaaaaaaaaa standing, because `branch -d` refused it",
                lines,
            )

            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, hosted_apply=HOSTED_APPLY
            )
            self.assertIn("- Ruleset enforcement: n/a (no ruleset written)", lines)

    def test_adds_resumption_naming_the_writes_read_from_the_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apply = {
                **HOSTED_APPLY,
                "writes": {"merge-settings": "logged"},
                "findings": [],
            }
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_apply=apply,
                resumed=True,
            )

            self.assertIn("### Resumption", lines)
            self.assertTrue(
                any(
                    line.startswith(
                        "- Taken from the resume record: hosted writes merge-settings; "
                    )
                    for line in lines
                )
            )


FACTS = {
    "operation": "facts",
    "shipped": True,
    "units": [
        {
            "unit": "ledger",
            "package": {"exit": 0, "tail": "packaged", "no_manifest": False},
            "run": {
                "exit": 0,
                "tail": "No project manifest found here",
                "no_manifest": True,
            },
        }
    ],
}
AUTOFIX = {
    "operation": "autofix",
    "shipped": True,
    "passes": 1,
    "exit_status": 0,
    "rewritten": ["apps/ledger/src/rates.py"],
    "reverted": ["docs/agents/domain.md"],
}


class RecordedLinesTests(unittest.TestCase):
    """Report lines the records settle that the session used to fill."""

    def test_reads_an_autofix_that_rewrote_nothing_and_left_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            autofix = {**AUTOFIX, "passes": 2, "exit_status": 1, "rewritten": []}
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, autofix=autofix
            )

            self.assertIn(
                "- Autofix: nothing rewritten outside the payload (2 passes); "
                "findings it could not fix remained for the bar",
                lines,
            )

    def test_renders_what_the_records_settle_in_place_of_slots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {
                **PROOFS,
                "manifests": [
                    {
                        "path": "apps/ledger/pyproject.toml",
                        "status": "edited",
                        "added": ["tool.ruff"],
                        "changed": [],
                        "removed": [],
                    }
                ],
                "configuration": {
                    ".": ["pyproject.toml [tool.ruff]"],
                    "apps/ledger": [],
                },
                "issue_tracker": {"tracker": "GitHub", "payload": True},
            }
            facts = {
                **FACTS,
                "units": [
                    {
                        "unit": "ledger",
                        "package": {
                            "exit": 0,
                            "tail": "packaged",
                            "no_manifest": False,
                        },
                        "run": {"exit": 0, "tail": "ran", "no_manifest": False},
                        "adapterless": "python",
                    }
                ],
                "autofix_commit": "b" * 40,
            }
            lines, slots = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=proofs,
                facts=facts,
                autofix=AUTOFIX,
            )

            for line in (
                (
                    "- Tool declaration: apps/ledger/pyproject.toml: added tool.ruff; "
                    "changed none; removed none"
                ),
                (
                    "- Configuration boundary: the root carries pyproject.toml "
                    "[tool.ruff]; apps/ledger: none"
                ),
                "- Ships nothing for want of an adapter: ledger: python",
                (
                    "- Autofix: `scripts/fix` rewrote apps/ledger/src/rates.py in 1 "
                    f"pass, committed by itself in {'b' * 12}"
                ),
            ):
                self.assertIn(line, lines)
            self.assertTrue(
                any(
                    line.startswith(
                        "- Issue tracker: GitHub, recorded in "
                        "docs/agents/issue-tracker.md, shipped by the payload; "
                    )
                    for line in lines
                )
            )
            self.assertFalse(
                [slot for slot in slots if slot.startswith(("tool-", "autofix-commit"))]
            )

    def test_a_decision_fills_its_slot_and_none_drops_an_optional_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            decisions = {
                "decisions": {
                    "unit-map": "ledger: apps/ledger, oneshot, ships none",
                    "layout-corrections": "none",
                    "declined-writes": "none",
                }
            }
            lines, slots = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, decisions=decisions
            )

            self.assertIn("- Unit map: ledger: apps/ledger, oneshot, ships none", lines)
            self.assertFalse([line for line in lines if "layout-corrections" in line])
            self.assertFalse([line for line in lines if "declined-writes" in line])
            self.assertNotIn(
                "unit-map: one line per unit, in the Report additions shape", slots
            )

    def test_reads_reconciliation_facts_and_autofix_from_their_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {
                **PROOFS,
                "emptied": [{"path": "src", "residue": ["src/__pycache__/"]}],
            }
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=proofs,
                preflight={"addons_present": ["CHANGELOG.md"]},
                facts=FACTS,
                autofix=AUTOFIX,
                stopped="awaiting the gate",
            )

            for line in (
                "- Applied: 58 payload paths, written because the destination lacked them",
                "- Preserved: .gitignore",
                (
                    "- Merged: CLAUDE.md; [[FILL: merged: the payload change and the "
                    "destination text each carries]]"
                ),
                "- Conflicted: none",
                "- Overridden: README.md (the product's own front page)",
                "- ADRs written: docs/adrs/0001-one-ledger.md",
                (
                    "- Payload paths: 66, the placeholder unit left out: 61 byte-identical "
                    "copies, 1 already identical in the destination, 2 authored, "
                    "1 preserved, 1 overridden; missing: none"
                ),
                "- Already held: CHANGELOG.md",
                "- Workflows the pull-request event never ran: .github/workflows/release.yml",
                (
                    "- Directories emptied by a move: src: held open by src/__pycache__/, "
                    "which is the destination's own and is left in place, named under "
                    "Left for the operator"
                ),
                (
                    "- Declared facts executed: ledger: `scripts/package` pass, "
                    "`scripts/run` does nothing (No project manifest found here)"
                ),
                (
                    "- Autofix: `scripts/fix` rewrote apps/ledger/src/rates.py in 1 pass, "
                    "committed by itself in [[FILL: autofix-commit: the commit sha]]"
                ),
            ):
                self.assertIn(line, lines)
            self.assertTrue(
                any(
                    line.startswith(
                        "- Payload paths the autofix rewrote: docs/agents/domain.md, "
                        "reverted in the candidate"
                    )
                    for line in lines
                )
            )
            self.assertTrue(
                any(
                    line.startswith("- Left for the operator: src: src/__pycache__/")
                    for line in lines
                )
            )

    def test_reads_a_synced_clone_into_the_emptied_and_cleanup_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {
                **PROOFS,
                "emptied": [{"path": "src", "residue": ["src/__pycache__/"]}],
            }
            synced = {
                "pulled": True,
                "head": "1234567890ab" + "0" * 28,
                "removed": [{"path": "src", "residue": ["src/__pycache__/x.pyc"]}],
                "findings": [],
            }
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=proofs, hooks=HOOKS, sync=synced
            )

            self.assertIn(
                "- Directories emptied by a move: src: removed from the clone after "
                "the pull, with src/__pycache__/x.pyc inside",
                lines,
            )
            self.assertIn("- Operator's clone: fast-forwarded to 1234567890ab", lines)
            self.assertFalse(
                any("untracked residue a move left" in line for line in lines)
            )

    def test_reads_a_kept_directory_as_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {**PROOFS, "emptied": [{"path": "src", "residue": []}]}
            synced = {
                "pulled": True,
                "head": "1234567890ab" + "0" * 28,
                "removed": [],
                "gone": [],
                "kept": ["src"],
                "findings": ["src: not removed, since it is a symlink"],
            }
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=proofs, hooks=HOOKS, sync=synced
            )

            self.assertIn(
                "- Directories emptied by a move: src: kept after the pull, "
                "named under Left for the operator",
                lines,
            )

    def test_reads_a_directory_already_gone_after_the_pull(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proofs = {
                **PROOFS,
                "emptied": [{"path": "src", "residue": ["src/__pycache__/"]}],
            }
            synced = {
                "pulled": True,
                "head": "1234567890ab" + "0" * 28,
                "removed": [],
                "gone": ["src"],
                "findings": [],
            }
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=proofs, hooks=HOOKS, sync=synced
            )

            self.assertIn(
                "- Directories emptied by a move: src: gone after the pull", lines
            )
            self.assertFalse(
                any("untracked residue a move left" in line for line in lines)
            )


class PullRequestBodyTests(unittest.TestCase):
    """The pull-request body, in the payload template's shape."""

    def _render(self, directory: str, **records: dict) -> str:
        prefix = Path(directory) / "ledger.aaaaaaaaaaaa"
        Path(f"{prefix}.check.txt").write_text(SUMMARY_PASS)
        for name, value in {"proofs": PROOFS, **records}.items():
            Path(f"{prefix}.{name.replace('_', '-')}.json").write_text(
                json.dumps(value)
            )
        result = run("pr-body", "--repository", "o/ledger", "--records", str(prefix))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], f"{prefix}.pr-body.md")
        return Path(f"{prefix}.pr-body.md").read_text()

    def test_follows_the_payload_templates_headings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = self._render(directory)
            template = (PAYLOAD / ".github/PULL_REQUEST_TEMPLATE.md").read_text()

            def headings(text: str) -> list[str]:
                return [line for line in text.splitlines() if line.startswith("## ")]

            self.assertEqual(headings(body), headings(template))
            self.assertIn("lint               pass             ruff", body)
            self.assertIn(
                "- Deletes or overwrites existing data: yes — deleted: "
                "docs/adr/0001-one-ledger.md; merged over: CLAUDE.md; "
                "replaced by the payload: README.md",
                body,
            )
            self.assertIn(
                "Revert the merge commit. No hosted setting was written.", body
            )

    def test_shares_decisions_with_the_report_and_answers_untouched_risks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = self._render(
                directory,
                decisions={"decisions": {"unit-map": "ledger: apps/ledger"}},
            )

            for line in (
                "- Unit map: ledger: apps/ledger",
                "- Conflicted: none",
                "- Overridden: README.md (the product's own front page)",
                "- Database migration or schema change: no",
                "- Authentication, authorization, or permission logic touched: no",
            ):
                self.assertIn(line, body)

    def test_rollback_lists_each_logged_reverse_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = self._render(directory, hosted_apply=HOSTED_APPLY)

            self.assertIn(
                "gh api -X PATCH repos/o/ledger -F allow_squash_merge=true", body
            )


class ReferencesTests(unittest.TestCase):
    """Tracked mentions of a moved path or an old invocation, outside ADRs and plans."""

    FILES: ClassVar[dict[str, str]] = {
        "README.md": "Results are in REPORT.md.\nSee docs/report.md for the new place.\n",
        "docs/adrs/0001-layout.md": "The tree held REPORT.md at its root.\n",
        "docs/plans/layout.md": "Move REPORT.md under docs/.\n",
        "apps/ledger/pyproject.toml": (
            '[project]\nname = "ledger"\n\n'
            '[project.scripts]\nledger-rates = "ledger.rates:main"\n'
        ),
        "apps/ledger/src/ledger/rates.py": (
            '"""Print rates.\n\nUsage: ./rates.py --all\n       python3 rates.py --all\n"""\n'
        ),
        "docs/report.md": "# Report\n",
    }

    def _candidate(self, directory: str) -> list[str]:
        candidate = Path(directory) / "candidate"
        for name, text in self.FILES.items():
            (candidate / name).parent.mkdir(parents=True, exist_ok=True)
            (candidate / name).write_text(text)
        git("init", "-q", "-b", "main", cwd=candidate)
        git("add", "-A", cwd=candidate)
        prefix = Path(directory) / "records"
        moves = [{"from": "REPORT.md", "to": "docs/report.md"}]
        Path(f"{prefix}.proofs.json").write_text(
            json.dumps({"rename_purity": {"moves": moves}})
        )
        return ["references", "--records", str(prefix), "--candidate", str(candidate)]

    def _hits(self, directory: str) -> list[dict[str, object]]:
        result = run(*self._candidate(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hits"]

    def test_a_moved_file_named_in_a_doc_is_a_hit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hits = [h for h in self._hits(directory) if h["path"] == "README.md"]

            self.assertEqual(
                [(h["line"], h["kind"], h["matched"], h["replacement"]) for h in hits],
                [(1, "moved-path", "REPORT.md", "docs/report.md")],
            )

    def test_an_old_invocation_suggests_the_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hits = [h for h in self._hits(directory) if h["kind"] == "invocation"]

            self.assertEqual(
                [(h["path"], h["line"], h["matched"]) for h in hits],
                [
                    ("apps/ledger/src/ledger/rates.py", 3, "./rates.py"),
                    ("apps/ledger/src/ledger/rates.py", 4, "python3 rates.py"),
                ],
            )
            self.assertEqual(
                {h["replacement"] for h in hits},
                {"scripts/run ledger --entry ledger-rates"},
            )

    def test_a_mention_resolving_to_a_tracked_file_is_not_a_hit(self) -> None:
        files = {
            "apps/ledger/src/main.py": "from . import rates\nopen('src/rates.py')\n",
            "apps/ledger/src/rates.py": "x = 1\n",
            "apps/ledger/README.md": "Edit src/rates.py.\n",
            "README.md": "Edit src/rates.py.\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_references(
                directory, files, [("src/rates.py", "apps/ledger/src/rates.py")]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [h["path"] for h in json.loads(result.stdout)["hits"]], ["README.md"]
            )

    def test_adrs_and_plans_are_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = {str(h["path"]) for h in self._hits(directory)}

            self.assertFalse({p for p in paths if p.startswith("docs/adrs/")})
            self.assertFalse({p for p in paths if p.startswith("docs/plans/")})

    def _run_references(
        self,
        directory: str,
        files: dict[str, str],
        moves: list[tuple[str, str]],
        proofs: Mapping[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run `references` over `files`, tracked, with `moves` as the proofs record."""
        candidate = Path(directory) / "candidate"
        for name, text in files.items():
            (candidate / name).parent.mkdir(parents=True, exist_ok=True)
            (candidate / name).write_text(text)
        if not (candidate / ".git").exists():
            git("init", "-q", "-b", "main", cwd=candidate)
        git("add", "-A", cwd=candidate)
        prefix = Path(directory) / "records"
        Path(f"{prefix}.proofs.json").write_text(
            json.dumps(
                proofs
                or {
                    "rename_purity": {"moves": [{"from": a, "to": b} for a, b in moves]}
                }
            )
        )
        return run(
            "references", "--records", str(prefix), "--candidate", str(candidate)
        )

    def test_a_move_a_later_proofs_lost_is_still_searched(self) -> None:
        files = {"README.md": "Run tools/gen.py first.\n", "docs/gen.md": "x\n"}
        with tempfile.TemporaryDirectory() as directory:
            first = self._run_references(
                directory, files, [("tools/gen.py", "docs/gen.md")]
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(
                json.loads(first.stdout)["moves"],
                [{"from": "tools/gen.py", "to": "docs/gen.md"}],
            )

            # Repairs pushed the move under git's rename threshold.
            second = self._run_references(directory, files, [])
            hits = json.loads(second.stdout)["hits"]
            self.assertEqual([h["matched"] for h in hits], ["tools/gen.py"])
            self.assertEqual(
                json.loads(second.stdout)["moves"],
                [{"from": "tools/gen.py", "to": "docs/gen.md"}],
            )

    def test_a_move_the_operator_dropped_is_not_carried_over(self) -> None:
        files = {"README.md": "Run tools/gen.py first.\n", "docs/gen.md": "x\n"}
        with tempfile.TemporaryDirectory() as directory:
            self._run_references(directory, files, [("tools/gen.py", "docs/gen.md")])

            # The old path is tracked again: the move was undone.
            second = self._run_references(
                directory, {**files, "tools/gen.py": "y\n"}, []
            )
            self.assertEqual(json.loads(second.stdout)["moves"], [])
            self.assertEqual(json.loads(second.stdout)["hits"], [])

    def test_a_finished_runs_references_record_is_not_carried_over(self) -> None:
        files = {"README.md": "Run tools/gen.py first.\n", "docs/gen.md": "x\n"}
        with tempfile.TemporaryDirectory() as directory:
            self._run_references(directory, files, [("tools/gen.py", "docs/gen.md")])
            prefix = Path(directory) / "records"
            Path(f"{prefix}.sweep.json").write_text("{}")
            future = Path(f"{prefix}.references.json").stat().st_mtime + 10
            os.utime(f"{prefix}.sweep.json", (future, future))

            second = self._run_references(directory, files, [])
            self.assertEqual(json.loads(second.stdout)["hits"], [])

    def test_a_basename_two_moves_share_is_one_ambiguous_hit(self) -> None:
        files = {
            "README.md": "Edit util.py, or lib/util.py.\n",
            "apps/a/src/util.py": "",
            "apps/b/src/util.py": "",
        }
        moves = [
            ("lib/util.py", "apps/a/src/util.py"),
            ("x/util.py", "apps/b/src/util.py"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_references(directory, files, moves)
            hits = json.loads(result.stdout)["hits"]

            self.assertEqual(
                [(h["matched"], h["replacement"], h.get("ambiguous")) for h in hits],
                [
                    ("lib/util.py", "apps/a/src/util.py", None),
                    ("util.py", None, True),
                ],
            )
            self.assertEqual(
                hits[1]["candidates"], ["apps/a/src/util.py", "apps/b/src/util.py"]
            )

    def test_a_console_script_stem_shared_across_units_is_ambiguous(self) -> None:
        files = {
            "README.md": "Run ./main.py now.\n",
            "apps/a/pyproject.toml": '[project.scripts]\na-cli = "a.main:main"\n',
            "apps/b/pyproject.toml": '[project.scripts]\nb-cli = "b.main:main"\n',
        }
        with tempfile.TemporaryDirectory() as directory:
            hits = json.loads(self._run_references(directory, files, []).stdout)["hits"]

            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["kind"], "invocation")
            self.assertIsNone(hits[0]["replacement"])
            self.assertTrue(hits[0]["ambiguous"])
            self.assertEqual(
                hits[0]["candidates"],
                ["scripts/run a --entry a-cli", "scripts/run b --entry b-cli"],
            )

    def test_a_name_followed_by_an_extension_is_not_a_mention(self) -> None:
        files = {
            "README.md": (
                "Keep tools/main.py.bak and ./main.py.bak.\n"
                "See tools/main.py.\n"
                "Then main.py, and python main.py.\n"
            ),
            "apps/t/pyproject.toml": '[project.scripts]\nmain = "t.main:main"\n',
        }
        with tempfile.TemporaryDirectory() as directory:
            hits = json.loads(
                self._run_references(
                    directory, files, [("tools/main.py", "apps/t/src/main.py")]
                ).stdout
            )["hits"]

            self.assertEqual(
                [(h["line"], h["matched"]) for h in hits],
                [(2, "tools/main.py"), (3, "python main.py"), (3, "main.py")],
            )

    def test_payload_copies_and_changelogs_are_not_searched(self) -> None:
        files = {
            "README.md": "See REPORT.md.\n",
            "docs/copy.md": "See REPORT.md.\n",
            "CHANGELOG.md": "Moved REPORT.md.\n",
            "apps/t/CHANGELOG.md": "Moved REPORT.md.\n",
            "docs/report.md": "x\n",
        }
        proofs = {
            "rename_purity": {"moves": [{"from": "REPORT.md", "to": "docs/report.md"}]},
            "copy": {"identical_paths": ["docs/copy.md"]},
        }
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_references(directory, files, [], proofs)
            hits = json.loads(result.stdout)["hits"]

            self.assertEqual({h["path"] for h in hits}, {"README.md"})

    def test_report_renders_an_ambiguous_hit_with_its_candidates(self) -> None:
        hit = {
            "path": "README.md",
            "line": 1,
            "text": "Edit util.py",
            "kind": "moved-path",
            "matched": "util.py",
            "replacement": None,
            "ambiguous": True,
            "candidates": ["apps/a/src/util.py", "apps/b/src/util.py"],
        }
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, references={"hits": [hit]}
            )

            self.assertIn(
                "- References reported, not rewritten: README.md:1: `util.py`, "
                "ambiguous between `apps/a/src/util.py`, `apps/b/src/util.py`",
                lines,
            )

    def test_report_renders_the_remaining_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hits = self._hits(directory)
            lines, _ = render_report(
                self,
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                references={"hits": hits},
            )

            line = next(
                x
                for x in lines
                if x.startswith("- References reported, not rewritten:")
            )
            self.assertIn("README.md:1: `REPORT.md`, suggested `docs/report.md`", line)

    def test_report_says_when_no_hit_remains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(
                self, directory, SUMMARY_PASS, proofs=PROOFS, references={"hits": []}
            )

            self.assertIn("- References reported, not rewritten: none", lines)

    def test_report_says_when_references_did_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = render_report(self, directory, SUMMARY_PASS, proofs=PROOFS)

            self.assertIn(
                "- References reported, not rewritten: unknown (references did not run)",
                lines,
            )


class DecideTests(unittest.TestCase):
    """Judgements recorded once, for both renderers."""

    def test_each_decision_joins_the_earlier_ones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prefix = str(Path(directory) / "records")
            for key, value in (("summary", "first"), ("scope", "x"), ("summary", "s")):
                result = run(
                    "decide", "--records", prefix, "--key", key, "--value", value
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(
                json.loads(Path(f"{prefix}.decisions.json").read_text())["decisions"],
                {"summary": "s", "scope": "x"},
            )

    def test_refuses_a_key_no_renderer_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "decide",
                "--records",
                str(Path(directory) / "records"),
                "--key",
                "nonsense",
                "--value",
                "x",
            )

            self.assertNotEqual(result.returncode, 0)


class ResumeTests(unittest.TestCase):
    """The default branch's movement, merged into a standing candidate."""

    def _candidate(self, directory: str, upstream: dict[str, str | None]) -> Path:
        candidate = candidate_repository(
            directory, {"uv.lock": b"base\n", "notes.md": b"base\n"}
        )
        origin = Path(directory) / "origin.git"
        git("clone", "-q", "--bare", str(candidate), str(origin))
        git("remote", "add", "origin", str(origin), cwd=candidate)
        branch = git_output("branch", "--show-current", cwd=candidate)
        upstream_clone = Path(directory) / "upstream"
        git("clone", "-q", str(origin), str(upstream_clone))
        for name, text in upstream.items():
            if text is None:
                (upstream_clone / name).unlink()
            else:
                (upstream_clone / name).write_text(text)
        git("add", "-A", cwd=upstream_clone)
        git("commit", "-qm", "chore: upstream", cwd=upstream_clone)
        git("push", "-q", "origin", branch, cwd=upstream_clone)
        (candidate / "uv.lock").write_text("candidate\n")
        (candidate / "notes.md").write_text("candidate\n")
        git("commit", "-qam", "chore: candidate", cwd=candidate)
        return candidate

    def _resume(self, candidate: Path) -> subprocess.CompletedProcess[str]:
        branch = git_output("branch", "--show-current", cwd=candidate)
        return run(
            "resume",
            "--candidate",
            str(candidate),
            "--default-branch",
            branch,
            *records(candidate),
        )

    def test_merges_a_default_branch_that_moved_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(directory, {"README.md": "upstream\n"})
            decisions = Path(f"{records(candidate)[1]}.decisions.json")
            decisions.write_text('{"decisions": {"summary": "stale"}}\n')
            result = self._resume(candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["conflicts"], [])
            self.assertEqual(
                report["merged"], git_output("rev-parse", "HEAD", cwd=candidate)
            )
            self.assertFalse(decisions.exists())

    def test_takes_the_default_branchs_lockfile_and_leaves_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(
                directory, {"uv.lock": "upstream\n", "notes.md": "upstream\n"}
            )
            result = self._resume(candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["lockfiles_taken"], ["uv.lock"])
            self.assertEqual(report["conflicts"], ["notes.md"])
            self.assertIsNone(report["merged"])
            self.assertEqual((candidate / "uv.lock").read_text(), "upstream\n")

    def test_takes_the_default_branchs_deletion_of_a_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = self._candidate(directory, {"uv.lock": None})
            result = self._resume(candidate)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["lockfiles_taken"], ["uv.lock"])
            self.assertEqual(report["conflicts"], [])
            self.assertFalse((candidate / "uv.lock").exists())
