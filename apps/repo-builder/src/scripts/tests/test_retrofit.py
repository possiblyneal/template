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
            self.assertIn("no .pre-commit-config.yaml", result.stderr)


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
            "--write-log",
            str(Path(directory) / "candidate.writes.json"),
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
            "--write-log",
            str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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
                "--write-log",
                str(Path(directory) / "candidate.writes.json"),
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


class ReportTests(unittest.TestCase):
    """The final report's deterministic lines, rendered from recorded JSON."""

    def _render(
        self, directory: str, summary: str, **inputs: object
    ) -> tuple[list[str], list[str]]:
        arguments = ["report", "--repository", "o/ledger"]
        for name, value in inputs.items():
            flag = "--" + name.replace("_", "-")
            if isinstance(value, dict):
                path = Path(directory) / f"{name}.json"
                path.write_text(json.dumps(value))
                arguments += [flag, str(path)]
            elif value is True:
                arguments.append(flag)
            else:
                arguments += [flag, str(value)]
        (Path(directory) / "summary.txt").write_text(summary)
        output = Path(directory) / "report.md"
        result = run(
            *arguments,
            "--summary",
            "scripts/check",
            str(Path(directory) / "summary.txt"),
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return output.read_text().splitlines(), json.loads(result.stdout)["slots"]

    def test_renders_a_finished_run_from_every_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = self._render(
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
            self.assertIn("check-suite result", slots)

    def test_renders_a_run_stopped_at_the_gate_as_reaching_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = self._render(
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hosted_read=HOSTED_READ,
                stopped="the operator declined every hosted write",
            )

            self.assertIn("- Runner variable: not requested", lines)
            self.assertNotIn("not reached", "\n".join(lines))

    def test_renders_a_stopped_unmet_bar_with_nothing_hosted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, slots = self._render(
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
                    "- Left for the operator: [[FILL: each path left in place and why, or none]]"
                ],
            )
            self.assertTrue(
                any(
                    line.startswith("- Candidate: left standing at [[FILL: ")
                    for line in lines
                )
            )
            self.assertTrue(lines[-1].startswith("[[FILL: "))
            self.assertIn("the unmet-bar outcome, in the Report additions shape", slots)

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
            lines, slots = self._render(
                directory, SUMMARY_PASS, proofs=proofs, stopped="awaiting the gate"
            )

            self.assertIn(
                "- Hooks: none installed, because the candidate carries no "
                "`.pre-commit-config.yaml` to read hook types from",
                lines,
            )
            self.assertNotIn("the candidate hooks directory", slots)

    def test_a_nonzero_exit_outside_the_result_table_fails_the_bar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines, _ = self._render(
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
            lines, slots = self._render(
                directory,
                SUMMARY_PASS,
                proofs=PROOFS,
                hooks=HOOKS,
                sweep=sweep,
                hosted_apply=apply,
                pull_request="https://github.com/o/ledger/pull/9",
            )

            self.assertIn(
                "step 9's mergeable/mergeStateStatus reading of the pull request",
                slots,
            )
            self.assertIn(
                "- Candidate: worktree removed from /r/tmp/ledger, branch "
                "retrofit/aaaaaaaaaaaa standing, because `branch -d` refused it",
                lines,
            )

            lines, _ = self._render(
                directory, SUMMARY_PASS, proofs=PROOFS, hosted_apply=HOSTED_APPLY
            )
            self.assertIn("- Ruleset enforcement: n/a (no ruleset written)", lines)

    def test_adds_resumption_naming_the_writes_read_from_the_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apply = {
                **HOSTED_APPLY,
                "writes": {"merge-settings": "logged"},
                "findings": [],
            }
            lines, _ = self._render(
                directory, SUMMARY_PASS, proofs=PROOFS, hosted_apply=apply, resumed=True
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
