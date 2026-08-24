from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).parents[1] / "preflight.py"
SPEC = importlib.util.spec_from_file_location("repo_builder_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


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
        self.assertEqual(preflight.classify_path("apps/api/main.py", []), ("product", None))

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
                        "template": {"repository": "owner/template", "subtree": "base-repo", "commit": "main"},
                        "destination": {"repository": "owner/product", "default_branch": "main"},
                        "generation": {},
                        "ownership": [{"path": "scripts/**", "mode": "managed"}],
                    }
                )
            )

            with self.assertRaisesRegex(preflight.PreflightError, "full lowercase 40-character"):
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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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


class AdoptTests(unittest.TestCase):
    def _build_fixture(self, directory: str) -> dict[str, object]:
        fixture_setup = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
        fixture_root = Path(directory) / "fixture"
        subprocess.run(
            ["python3", str(fixture_setup), "adopt", str(fixture_root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return json.loads((fixture_root / "fixture.json").read_text())

    def _run_adopt(self, fixture: dict[str, object], *addons: str) -> subprocess.CompletedProcess[str]:
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_adopt_reports_addon_entry_and_leaves_destination_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            result = self._run_adopt(fixture, "README.md")

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["operation"], "adopt")
            self.assertEqual(report["template"]["recorded_commit"], fixture["recorded_commit"])
            self.assertEqual(len(report["addons"]), 1)
            addon = report["addons"][0]
            self.assertEqual(addon["path"], "README.md")
            self.assertEqual(addon["adoption"]["slots"][0]["value_key"], "project-title")

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

    def test_adopt_rejects_the_second_half_adopted_later(self) -> None:
        """One at a time is how a repository really ends up holding both: the
        occasion for the second addon arrives months after the first."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._build_fixture(directory)
            destination = Path(fixture["destination"])
            (destination / "_config.yml").write_text("theme: minima\n", encoding="utf-8")
            subprocess.run(["git", "add", "_config.yml"], cwd=destination, check=True)
            subprocess.run(
                ["git", "commit", "--no-verify", "-m", "chore: adopt _config.yml"],
                cwd=destination,
                check=True,
                stdout=subprocess.DEVNULL,
            )

            result = self._run_adopt(fixture, ".nojekyll")

            self.assertEqual(result.returncode, 2)
            self.assertIn("destination holding _config.yml", result.stderr)


if __name__ == "__main__":
    unittest.main()
