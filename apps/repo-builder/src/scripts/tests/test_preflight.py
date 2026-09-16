from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "preflight.py"
SPEC = importlib.util.spec_from_file_location("repo_builder_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)

# The two adopt tests below commit by hand, standing in for the repository
# owner taking an addon months after the first. They are the only commits here
# not made through evals/setup_fixture.py, which carries its own GIT_ENV, so
# they are also the only ones that would fall back to ambient git config. A CI
# runner has none and cannot derive one -- its gecos field is empty, so git
# fails with "empty ident name" where a developer machine silently succeeds.
GIT_IDENTITY = (
    "-c",
    "user.name=Repo Builder Test",
    "-c",
    "user.email=repo-builder-test@example.invalid",
)


class PreflightUnitTests(unittest.TestCase):
    def test_longest_ownership_path_wins(self) -> None:
        rules = [
            preflight.OwnershipRule(".claude/**", "managed", 0),
            preflight.OwnershipRule(".claude/skills/**", "product", 1),
        ]

        self.assertEqual(
            preflight.classify_path(".claude/skills/my-skill/SKILL.md", rules),
            ("product", ".claude/skills/**"),
        )

    def test_unmatched_path_is_product_owned(self) -> None:
        self.assertEqual(
            preflight.classify_path("apps/api/main.py", []), ("product", None)
        )

    def test_parse_rename_classifies_destination_path(self) -> None:
        rules = [preflight.OwnershipRule("scripts/**", "managed", 0)]
        output = "R100\0base-repo/scripts/old\0base-repo/scripts/new\0"

        self.assertEqual(
            preflight.parse_name_status(output, "base-repo", rules),
            [
                {
                    "status": "R100",
                    "path": "scripts/new",
                    "ownership": "managed",
                    "ownership_rule": "scripts/**",
                    "old_path": "scripts/old",
                    "new_path": "scripts/new",
                }
            ],
        )

    def test_validate_manifest_requires_full_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".repo-template.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "template": {
                            "repository": "owner/template",
                            "subtree": "base-repo",
                            "commit": "main",
                        },
                        "destination": {
                            "repository": "owner/product",
                            "default_branch": "main",
                        },
                        "generation": {},
                        "ownership": [{"path": "scripts/**", "mode": "managed"}],
                    }
                )
            )

            with self.assertRaisesRegex(
                preflight.PreflightError, "full lowercase 40-character"
            ):
                preflight.validate_manifest(path)

    def test_update_rejects_unrelated_history_before_diff(self) -> None:
        fixture_setup = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "fixture"
            subprocess.run(
                ["python3", str(fixture_setup), "unrelated", str(fixture_root)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            fixture = json.loads((fixture_root / "fixture.json").read_text())
            result = subprocess.run(
                [
                    "python3",
                    str(MODULE_PATH),
                    "update",
                    "--template-repo",
                    fixture["template_repo"],
                    "--target",
                    fixture["target_commit"],
                    "--destination",
                    fixture["destination"],
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("is not an ancestor", result.stderr)
            destination = Path(fixture["destination"])
            self.assertFalse(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=destination,
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                ).stdout
            )


class GenerateTests(unittest.TestCase):
    """The source commit a generate pins is the base every update diffs from."""

    @staticmethod
    def _generation_fixture(directory: str) -> dict[str, str]:
        fixture_setup = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
        fixture_root = Path(directory) / "fixture"
        subprocess.run(
            ["python3", str(fixture_setup), "generation", str(fixture_root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return json.loads((fixture_root / "fixture.json").read_text())

    @staticmethod
    def _commit_onto_main(template: Path, name: str) -> str:
        (template / "base-repo" / name).write_text(f"{name}\n")
        subprocess.run(["git", "add", "-A"], cwd=template, check=True)
        subprocess.run(
            [*("git", *GIT_IDENTITY), "commit", "-q", "-m", f"chore: {name}"],
            cwd=template,
            check=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=template,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

    @staticmethod
    def _preflight(fixture: dict[str, str], target: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "python3",
                str(MODULE_PATH),
                "generate",
                "--template-repo",
                fixture["template_repo"],
                "--target",
                target,
                "--subtree",
                fixture["subtree"],
                "--destination-repository",
                fixture["destination_repository"],
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generate_accepts_a_commit_on_the_template_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._generation_fixture(directory)
            result = self._preflight(fixture, fixture["target_commit"])

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["template"]["branch"], "main")
            self.assertEqual(report["template"]["branch_tip"], fixture["target_commit"])

    def test_generate_rejects_a_commit_off_the_template_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._generation_fixture(directory)
            template = Path(fixture["template_repo"])
            subprocess.run(
                ["git", "checkout", "-q", "-b", "experiment"],
                cwd=template,
                check=True,
            )
            (template / "base-repo" / "SCRATCH.md").write_text("not on main\n")
            subprocess.run(["git", "add", "-A"], cwd=template, check=True)
            subprocess.run(
                [*("git", *GIT_IDENTITY), "commit", "-q", "-m", "chore: experiment"],
                cwd=template,
                check=True,
            )
            off_branch = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=template,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()

            result = self._preflight(fixture, off_branch)

            self.assertEqual(result.returncode, 2)
            self.assertIn("is not on main", result.stdout + result.stderr)

    def test_generate_accepts_a_commit_ahead_of_a_stale_local_branch(self) -> None:
        """A clone whose local main trails origin/main is stale, not off-branch.

        The operator's clone is fetched far more often than it is checked out,
        so a local `main` behind `origin/main` is the ordinary state rather than
        a broken one. Reading the branch as the local ref refuses a commit that
        is on the template's branch, for a reason that has nothing to do with
        the mainline the check exists to enforce.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._generation_fixture(directory)
            upstream = Path(fixture["template_repo"])
            clone = Path(directory) / "clone"
            subprocess.run(
                ["git", "clone", "-q", str(upstream), str(clone)], check=True
            )
            ahead = self._commit_onto_main(upstream, "AHEAD.md")
            subprocess.run(["git", "fetch", "-q", "origin"], cwd=clone, check=True)

            result = self._preflight({**fixture, "template_repo": str(clone)}, ahead)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["template"]["branch_tip"], ahead)

    def test_generate_resolves_a_branch_the_clone_never_checked_out(self) -> None:
        """A fetched branch with no local ref is resolvable, not absent.

        A clone made for the generate alone has every remote ref and only the
        one local branch it checked out. Refusing because `main` does not
        resolve reports the clone's shape as a pinning mistake.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._generation_fixture(directory)
            upstream = Path(fixture["template_repo"])
            clone = Path(directory) / "fetched"
            clone.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
            subprocess.run(
                ["git", "remote", "add", "origin", str(upstream)], cwd=clone, check=True
            )
            subprocess.run(["git", "fetch", "-q", "origin"], cwd=clone, check=True)
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "--verify", "--quiet", "refs/heads/main"],
                    cwd=clone,
                    check=False,
                    stdout=subprocess.DEVNULL,
                ).returncode,
                1,
                "the fixture must hold no local main for this test to mean anything",
            )

            result = self._preflight(
                {**fixture, "template_repo": str(clone)}, fixture["target_commit"]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["template"]["branch_tip"],
                fixture["target_commit"],
            )

    def test_generate_reports_git_failing_apart_from_a_refusal(self) -> None:
        """Git unable to answer is a repository fault, not a commit off-branch.

        `merge-base --is-ancestor` exits 1 for a genuine negative and 128 when
        it cannot read what it was given. Collapsing the two sends the operator
        to re-pin a commit when the repository is what needs attention.
        """
        tip = "b" * 40

        def stubbed_git(target: Path, *arguments: str, check: bool = True):
            """A clone that resolves the branch and then cannot read the object."""
            if arguments[:2] == ("merge-base", "--is-ancestor"):
                return subprocess.CompletedProcess(
                    ["git", *arguments], 128, "", "fatal: bad object\n"
                )
            return subprocess.CompletedProcess(["git", *arguments], 0, tip, "")

        # patch.object names the attribute as a string, which is what keeps the
        # type checker from reading it off the importlib-loaded module above.
        with (
            unittest.mock.patch.object(preflight, "run_git", stubbed_git),
            self.assertRaisesRegex(preflight.PreflightError, "bad object"),
        ):
            preflight.require_on_branch(Path("/unread-clone"), "a" * 40, "main")

    def test_generate_tries_every_ref_before_reporting_git_declined(self) -> None:
        """One ref git cannot read is no reason to ignore another that answers."""
        remote_tip = "b" * 40
        local_tip = "c" * 40

        def stubbed_git(target: Path, *arguments: str, check: bool = True):
            """A clone whose remote ref is unreadable and whose local ref is not."""
            if arguments[:2] == ("merge-base", "--is-ancestor"):
                if arguments[3] == remote_tip:
                    return subprocess.CompletedProcess(
                        ["git", *arguments], 128, "", "fatal: bad object\n"
                    )
                return subprocess.CompletedProcess(["git", *arguments], 0, "", "")
            tip = remote_tip if "remotes" in arguments[2] else local_tip
            return subprocess.CompletedProcess(["git", *arguments], 0, tip, "")

        with unittest.mock.patch.object(preflight, "run_git", stubbed_git):
            resolved = preflight.require_on_branch(
                Path("/half-read-clone"), "a" * 40, "main"
            )

        self.assertEqual(resolved, local_tip)

    def test_generate_refuses_a_branch_argument_that_is_not_a_branch_name(self) -> None:
        """The input narrowed to a plain branch name, and the refusal says so.

        An update targets a branch and diffs back to the recorded commit, so a
        tag or a detached `HEAD` names no lineage an update could follow.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._generation_fixture(directory)
            subprocess.run(
                ["git", "tag", "v1"], cwd=fixture["template_repo"], check=True
            )

            result = subprocess.run(
                [
                    "python3",
                    str(MODULE_PATH),
                    "generate",
                    "--template-repo",
                    fixture["template_repo"],
                    "--target",
                    fixture["target_commit"],
                    "--subtree",
                    fixture["subtree"],
                    "--destination-repository",
                    fixture["destination_repository"],
                    "--template-branch",
                    "v1",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("resolves to no ref", result.stderr)


class AdoptTests(unittest.TestCase):
    # The values are all `str` because the scenario below is the literal
    # "adopt", and setup_fixture.build_adopt returns six flat strings. The
    # nested path-to-digest map belongs to build_update, which no caller here
    # can reach. Parameterising the scenario would make this annotation a lie.
    def _build_fixture(self, directory: str) -> dict[str, str]:
        fixture_setup = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
        fixture_root = Path(directory) / "fixture"
        subprocess.run(
            ["python3", str(fixture_setup), "adopt", str(fixture_root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return json.loads((fixture_root / "fixture.json").read_text())

    def _run_adopt(
        self, fixture: dict[str, str], *addons: str
    ) -> subprocess.CompletedProcess[str]:
        addon_args: list[str] = []
        for addon in addons:
            addon_args.extend(["--addon", addon])
        return subprocess.run(
            [
                "python3",
                str(MODULE_PATH),
                "adopt",
                "--template-repo",
                fixture["template_repo"],
                "--destination",
                fixture["destination"],
                *addon_args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_adopt_reports_addon_entry_and_leaves_destination_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            result = self._run_adopt(fixture, "README.md")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["operation"], "adopt")
            self.assertEqual(
                report["template"]["recorded_commit"], fixture["recorded_commit"]
            )
            self.assertEqual(len(report["addons"]), 1)
            addon = report["addons"][0]
            self.assertEqual(addon["path"], "README.md")
            self.assertEqual(
                addon["adoption"]["slots"][0]["value_key"], "project-title"
            )

            destination = Path(fixture["destination"])
            self.assertFalse(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=destination,
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                ).stdout
            )
            self.assertFalse((destination / "README.md").exists())

    def test_adopt_rejects_half_a_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            result = self._run_adopt(fixture, "CONTRIBUTORS.md")

            self.assertEqual(result.returncode, 2)
            self.assertIn("must be adopted with its pair", result.stderr)

    def test_adopt_rejects_both_halves_of_an_exclusive_choice(self) -> None:
        """_config.yml and .nojekyll cancel each other, and nothing downstream
        would say so: both files copy, both are valid, and the site builds with
        its configuration never read."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            result = self._run_adopt(fixture, "_config.yml", ".nojekyll")

            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot be adopted with", result.stderr)

    def _commit(self, destination: Path, path: str, message: str) -> None:
        subprocess.run(["git", "add", path], cwd=destination, check=True)
        subprocess.run(
            ["git", *GIT_IDENTITY, "commit", "--no-verify", "-m", message],
            cwd=destination,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_adopt_rejects_the_second_half_adopted_later(self) -> None:
        """One at a time is how a repository really ends up holding both: the
        occasion for the second addon arrives months after the first."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            destination = Path(fixture["destination"])
            (destination / "_config.yml").write_text(
                "theme: minima\n", encoding="utf-8"
            )
            self._commit(destination, "_config.yml", "chore: adopt _config.yml")

            result = self._run_adopt(fixture, ".nojekyll")

            self.assertEqual(result.returncode, 2)
            self.assertIn("destination holding _config.yml", result.stderr)

    def test_adopt_rejects_a_one_directional_pair_with_neither_half_present(
        self,
    ) -> None:
        """AUTHORS names the copyright holders that the notices in the source
        tree point at, and those notices grant nothing without a license."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            result = self._run_adopt(fixture, "AUTHORS")

            self.assertEqual(result.returncode, 2)
            self.assertIn("must be adopted with its pair LICENSE", result.stderr)

    def test_adopt_accepts_a_one_directional_pair_already_in_the_destination(
        self,
    ) -> None:
        """The realistic sequence, and the one a seen-only check makes
        impossible: LICENSE was adopted long ago, so it can be neither
        requested again -- that is rejected as already present -- nor found."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            destination = Path(fixture["destination"])
            (destination / "LICENSE").write_text(
                "License text, verbatim.\n", encoding="utf-8"
            )
            self._commit(destination, "LICENSE", "chore: adopt LICENSE")

            result = self._run_adopt(fixture, "AUTHORS")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["addons"][0]["path"], "AUTHORS")


class RetrofitTests(unittest.TestCase):
    """A repository that was never generated, proved retrofittable without a network."""

    NAMED = "https://github.com/acme/legacy-service.git"

    def _fixture(self, directory: str) -> dict[str, str]:
        """A template beside a destination developed on its own for years.

        The destination collides with the payload three ways on purpose: a
        tracked file git could restore, an untracked file it could not, and an
        ignored file that is equally unrecoverable while staying out of the
        untracked finding.
        """
        setup = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
        root = Path(directory) / "fixture"
        subprocess.run(
            ["python3", str(setup), "generation", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        fixture = json.loads((root / "fixture.json").read_text())

        destination = Path(directory) / "legacy-service"
        (destination / "scripts").mkdir(parents=True)
        (destination / "data").mkdir()
        (destination / "docs").mkdir()
        (destination / "CLAUDE.md").write_text("the destination's own contract\n")
        (destination / "README.md").write_text("legacy service\n")
        (destination / ".gitignore").write_text("docs/LESSONS.md\n")
        (destination / "scripts" / "check").write_text("#!/bin/sh\nexit 0\n")
        (destination / "data" / "notes.txt").write_text("kept deliberately\n")
        (destination / "docs" / "LESSONS.md").write_text("ignored, still present\n")

        subprocess.run(
            ["git", "init", "-q", "--initial-branch=master", str(destination)],
            check=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", self.NAMED], cwd=destination, check=True
        )
        subprocess.run(
            ["git", "add", "CLAUDE.md", "README.md", ".gitignore"],
            cwd=destination,
            check=True,
        )
        subprocess.run(
            [*("git", *GIT_IDENTITY), "commit", "-q", "-m", "chore: years of work"],
            cwd=destination,
            check=True,
        )
        fixture["destination"] = str(destination)
        return fixture

    def _preflight(
        self, fixture: dict[str, str], /, **overrides: str
    ) -> subprocess.CompletedProcess:
        arguments = {
            "--template-repo": fixture["template_repo"],
            "--target": fixture["target_commit"],
            "--subtree": fixture["subtree"],
            "--destination": fixture["destination"],
            "--destination-repository": "acme/legacy-service",
            **overrides,
        }
        return subprocess.run(
            ["python3", str(MODULE_PATH), "retrofit", *sum(arguments.items(), ())],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_retrofit_reports_collisions_without_deciding_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            result = self._preflight(fixture)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["operation"], "retrofit")
            self.assertEqual(
                report["collisions"],
                [
                    {"path": "CLAUDE.md", "tracked": True},
                    {"path": "docs/LESSONS.md", "tracked": False},
                    {"path": "scripts/check", "tracked": False},
                ],
            )
            for collision in report["collisions"]:
                self.assertNotIn("ownership", collision)

    def test_retrofit_carries_the_full_payload_list_and_a_destination_count(
        self,
    ) -> None:
        """Absence has no runner, so the list is what the delivery check reads."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            report = json.loads(self._preflight(fixture).stdout)

            self.assertEqual(
                report["payload_paths"],
                [
                    "CLAUDE.md",
                    "apps/app-name/.unit.json",
                    "apps/app-name/src/.gitkeep",
                    "docs/LESSONS.md",
                    "docs/adrs/0000-template.md",
                    "scripts/check",
                    "scripts/legacy",
                ],
            )
            self.assertEqual(report["destination"]["path_count"], 3)
            self.assertNotIn("paths", report["destination"])

    def test_retrofit_reports_untracked_work_and_does_not_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            result = self._preflight(fixture)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["untracked"], ["data/", "scripts/"])
            self.assertNotIn("docs/LESSONS.md", report["untracked"])

    def test_retrofit_reports_a_foreign_default_branch_as_a_rename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            report = json.loads(self._preflight(fixture).stdout)

            self.assertEqual(report["destination"]["default_branch"], "master")
            self.assertIs(report["destination"]["rename_required"], True)

    def test_retrofit_needs_no_hosted_client_on_path(self) -> None:
        """The discipline the three existing subcommands keep, asserted rather than trusted."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            only_git = Path(directory) / "bin"
            only_git.mkdir()
            git = shutil.which("git")
            assert git, "git is required to run this suite"
            (only_git / "git").symlink_to(git)
            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "retrofit",
                    "--template-repo",
                    fixture["template_repo"],
                    "--target",
                    fixture["target_commit"],
                    "--subtree",
                    fixture["subtree"],
                    "--destination",
                    fixture["destination"],
                    "--destination-repository",
                    "acme/legacy-service",
                ],
                text=True,
                capture_output=True,
                check=False,
                env={"PATH": str(only_git), "HOME": directory},
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_retrofit_reads_the_default_branch_not_the_checked_out_one(self) -> None:
        """A retrofit runs on a checkout the operator already had.

        Sitting on a feature branch is the ordinary case, so reading HEAD
        reports a rename is required for a repository whose default branch is
        already the wanted one.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            destination = fixture["destination"]
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=destination,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            for arguments in (
                ("update-ref", "refs/remotes/origin/main", head),
                (
                    "symbolic-ref",
                    "refs/remotes/origin/HEAD",
                    "refs/remotes/origin/main",
                ),
                ("checkout", "-q", "-b", "feature/work"),
            ):
                subprocess.run(["git", *arguments], cwd=destination, check=True)

            report = json.loads(self._preflight(fixture).stdout)

            self.assertEqual(report["destination"]["default_branch"], "main")
            self.assertIs(report["destination"]["rename_required"], False)

    def test_retrofit_reports_a_payload_path_held_as_a_directory(self) -> None:
        """`ls-files` names no directory, so a membership test alone misses this.

        The payload ships `scripts/legacy` as a file. A destination holding a
        directory there fails the write outright, and a preflight that called
        it safe sends the operator into a retrofit that cannot finish.
        """
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            destination = Path(fixture["destination"])
            (destination / "scripts" / "legacy").mkdir()
            (destination / "scripts" / "legacy" / "run.sh").write_text("exit 0\n")
            subprocess.run(
                ["git", "add", "scripts/legacy/run.sh"], cwd=destination, check=True
            )
            subprocess.run(
                [
                    *("git", *GIT_IDENTITY),
                    "commit",
                    "-q",
                    "-m",
                    "chore: legacy scripts",
                ],
                cwd=destination,
                check=True,
            )

            report = json.loads(self._preflight(fixture).stdout)

            self.assertIn(
                {"path": "scripts/legacy", "tracked": True}, report["collisions"]
            )

    def test_retrofit_keeps_a_path_whose_name_begins_with_a_space(self) -> None:
        """Stripping a `-z` listing eats the first path's leading whitespace.

        A path git itself cannot name unquoted is exactly the one a collision
        check must still see, so the listing is read without being trimmed.
        """
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "spaced"
            destination.mkdir()
            subprocess.run(["git", "init", "-q", str(destination)], check=True)
            (destination / " lead.txt").write_text("first when sorted\n")
            subprocess.run(["git", "add", "-A"], cwd=destination, check=True)

            self.assertEqual(preflight.listed_paths(destination), [" lead.txt"])

    def test_retrofit_refuses_a_destination_that_is_not_a_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            plain = Path(directory) / "plain"
            plain.mkdir()

            result = self._preflight(fixture, **{"--destination": str(plain)})

            self.assertEqual(result.returncode, 2)
            self.assertIn("not a Git repository", result.stderr)

    def test_retrofit_refuses_a_destination_with_no_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            subprocess.run(
                ["git", "remote", "remove", "origin"],
                cwd=fixture["destination"],
                check=True,
            )

            result = self._preflight(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("origin remote", result.stderr)

    def test_retrofit_refuses_an_origin_that_is_not_the_named_repository(self) -> None:
        """The cross-check that settles a clone whose directory name is its own."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)

            result = self._preflight(
                fixture, **{"--destination-repository": "acme/some-other-service"}
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("differs from the named repository", result.stderr)

    def test_retrofit_refuses_uncommitted_edits_to_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            (Path(fixture["destination"]) / "README.md").write_text("edited\n")

            result = self._preflight(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("uncommitted changes to tracked files", result.stderr)

    def test_retrofit_refuses_a_destination_that_already_has_a_record(self) -> None:
        """A repository carrying a record is updated, not retrofitted."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            (Path(fixture["destination"]) / ".repo-template.json").write_text("{}\n")

            result = self._preflight(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("already carries a template record", result.stderr)


if __name__ == "__main__":
    unittest.main()
