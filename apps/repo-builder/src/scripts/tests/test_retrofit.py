from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        return run(
            "proofs",
            "--template-repo",
            fixture["template_repo"],
            "--target",
            fixture["target_commit"],
            "--subtree",
            fixture["subtree"],
            "--candidate",
            fixture["destination"],
            "--base",
            fixture["base"],
        )

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


class HooksTests(unittest.TestCase):
    """The destination clone's hooks, installed after the merge and proved."""

    @classmethod
    def setUpClass(cls) -> None:
        reason = hook_environments_unavailable()
        if reason:
            raise unittest.SkipTest(reason)

    def _merged(self, directory: str) -> Path:
        """The fixture clone once the merge landed the payload, on a feature branch.

        The payload itself stands in for the merged tree, because it is a tree
        its own hooks pass and the retrofit fixture's foreign layout is not.
        """
        fixture = retrofit_fixture(directory)
        destination = Path(fixture["destination"])
        git("rm", "-rq", ".", cwd=destination)
        shutil.copytree(PAYLOAD, destination, dirs_exist_ok=True)
        git("add", "-A", cwd=destination)
        git("commit", "-q", "-m", "build: land the payload", cwd=destination)
        git("push", "-q", "origin", "main", cwd=destination)
        git("checkout", "-q", "-b", "feature", cwd=destination)
        return destination

    def _global(self, directory: str, hooks: dict[str, str]) -> dict[str, str]:
        """An operator's global hooks directory, isolated from this machine's."""
        root = Path(directory) / "global"
        (root / "hooks").mkdir(parents=True)
        for name, body in hooks.items():
            hook = root / "hooks" / name
            hook.write_text(body)
            hook.chmod(0o755)
        (root / "gitconfig").write_text(f"[core]\n\thooksPath = {root / 'hooks'}\n")
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
            "--scratch",
            str(destination.parent / "hook-test"),
            env=env,
        )

    def test_installs_the_hooks_and_proves_all_three_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            fired = Path(directory) / "fired"
            own = destination / ".git/hooks/pre-commit"
            own.write_text(f'#!/bin/sh\ntouch "{fired}"\n')
            own.chmod(0o755)
            env = self._global(
                directory,
                {
                    "prepare-commit-msg": (
                        PAYLOAD / "scripts/attribute-commit"
                    ).read_text(),
                    "post-rewrite": "#!/bin/sh\nexit 0\n",
                },
            )
            result = self._hooks(destination, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["findings"], [])
            self.assertEqual(
                report["checks"],
                {
                    "default_branch_refused": True,
                    "malformed_subject_refused": True,
                    "trailer_rewritten": True,
                },
            )
            hooks = destination / ".git/hooks"
            self.assertEqual(
                git_output("config", "--local", "core.hooksPath", cwd=destination),
                str(hooks),
            )
            # The clone's own hook is chained, not destroyed: it fired.
            self.assertEqual(
                report["moved_aside"][0]["to"], str(hooks / "pre-commit.legacy")
            )
            self.assertTrue(fired.exists())
            self.assertEqual(
                sorted(
                    (Path(h["hook"]).name, h["disposition"])
                    for h in report["global_hooks"]
                ),
                [("post-rewrite", "linked"), ("prepare-commit-msg", "duplicate")],
            )
            self.assertTrue((hooks / "post-rewrite").is_symlink())
            self.assertTrue(report["worktree_removed"])
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

    def test_reports_a_worktree_it_could_not_remove_and_forces_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = self._merged(directory)
            # A chained hook that leaves a file no step commits.
            own = destination / ".git/hooks/pre-commit"
            own.write_text("#!/bin/sh\ntouch stray\n")
            own.chmod(0o755)
            result = self._hooks(destination, self._global(directory, {}))

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["worktree_removed"])
            self.assertIn("not removed", report["findings"][0])
            self.assertTrue((destination.parent / "hook-test/stray").exists())

    def test_refuses_before_the_merge_has_landed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = retrofit_fixture(directory)
            destination = Path(fixture["destination"])
            result = self._hooks(destination, self._global(directory, {}))

            self.assertEqual(result.returncode, 2)
            self.assertIn("no .pre-commit-config.yaml", result.stderr)


if __name__ == "__main__":
    unittest.main()


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
        return clone, candidate

    def _merge(self, clone: Path) -> None:
        """GitHub's merge; the clone's own main is never moved."""
        git("push", "-q", "origin", f"{self.BRANCH}:main", cwd=clone)

    def _sweep(
        self, directory: str, clone: Path, candidate: Path
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
            "owner/ledger",
            "--hooks-dir",
            str(Path(directory) / "candidate-hooks"),
            "--resume-record",
            str(Path(directory) / "candidate.resume.json"),
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
