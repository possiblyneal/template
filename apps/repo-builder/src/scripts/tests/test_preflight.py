from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
