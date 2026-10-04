from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from test_preflight import git

SETUP = Path(__file__).parents[2] / "evals" / "setup_fixture.py"
VERIFY = Path(__file__).parents[2] / "evals" / "verify_fixture.py"


def build_fixture(directory: str, scenario: str) -> tuple[Path, dict[str, Any]]:
    root = Path(directory) / "fixture"
    subprocess.run(
        ["python3", str(SETUP), scenario, str(root)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return root / "fixture.json", json.loads((root / "fixture.json").read_text())


def stage_candidate(fixture: dict[str, Any]) -> Path:
    """The worktree step 2 adds, holding what steps 3 to 7 leave in it."""
    destination = Path(fixture["destination"])
    candidate = destination.parent / "candidate"
    git(
        "worktree",
        "add",
        "-b",
        f"retrofit/{fixture['target_commit'][:12]}",
        str(candidate),
        "main",
        cwd=destination,
    )
    shutil.copytree(
        Path(fixture["template_repo"]) / fixture["subtree"],
        candidate,
        dirs_exist_ok=True,
    )
    shutil.rmtree(candidate / "apps/app-name")
    unit_path = fixture["unit"]
    unit = candidate / unit_path
    (unit / "scripts").mkdir(parents=True)
    git("mv", "src", f"{unit_path}/src", cwd=candidate)
    git("mv", "tests", f"{unit_path}/tests", cwd=candidate)
    git("mv", "scripts/build.py", f"{unit_path}/scripts/build.py", cwd=candidate)
    git(
        "mv",
        "docs/adr/0001-one-ledger-per-currency.md",
        "docs/adrs/0001-one-ledger-per-currency.md",
        cwd=candidate,
    )
    git("mv", "notes/architecture.md", "docs/repository-layout.md", cwd=candidate)
    (unit / ".unit.json").write_text(
        '{"schema_version": 1, "run": "none", "ships": {"kind": "none"}}\n'
    )
    with (candidate / "pyproject.toml").open("a") as manifest:
        manifest.write('\n[tool.checks]\ntest = "unittest"\n')
    (candidate / ".repo-template.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "template": {
                    "repository": fixture["template_repo"],
                    "subtree": fixture["subtree"],
                    "commit": fixture["target_commit"],
                },
                "ownership": [
                    {"path": ".repo-template.json", "mode": "managed"},
                    {"path": "CLAUDE.md", "mode": "managed"},
                    {"path": "scripts/**", "mode": "managed"},
                    {"path": "apps/**", "mode": "product"},
                ],
            }
        )
    )
    git("add", "-A", cwd=candidate)
    return candidate


def run_verify(fixture_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VERIFY), str(fixture_path)],
        text=True,
        capture_output=True,
        check=False,
    )


def verify(fixture_path: Path) -> tuple[int, dict[str, object]]:
    result = run_verify(fixture_path)
    return result.returncode, json.loads(result.stdout) if result.stdout else {}


def rewrite_ownership(candidate: Path, extra: dict[str, str]) -> None:
    path = candidate / ".repo-template.json"
    manifest = json.loads(path.read_text())
    manifest["ownership"].append(extra)
    path.write_text(json.dumps(manifest))


def outcomes(report: dict[str, object]) -> dict[str, bool]:
    checks = report["checks"]
    assert isinstance(checks, list)
    return {check["text"]: check["passed"] for check in checks}


class VerifyRetrofitTests(unittest.TestCase):
    def test_a_finished_retrofit_candidate_passes_every_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            stage_candidate(fixture)

            status, report = verify(path)

            self.assertEqual(outcomes(report).get("candidate exists"), True, report)
            self.assertEqual(report["failed"], 0, report)
            self.assertEqual(status, 0)

    def test_a_moved_file_that_was_rewritten_fails_the_hash_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            candidate = stage_candidate(fixture)
            (candidate / fixture["unit"] / "src/ledger/rates.py").write_text(
                "# edited\n"
            )

            status, report = verify(path)

            self.assertFalse(outcomes(report)["moved files byte-identical"])
            self.assertEqual(status, 1)

    def test_an_unmet_bar_candidate_passes_the_red_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit-red")
            stage_candidate(fixture)

            status, report = verify(path)

            self.assertEqual(outcomes(report).get("candidate exists"), True, report)
            self.assertEqual(report["failed"], 0, report)
            self.assertEqual(status, 0)

    def test_a_missing_candidate_is_a_failed_check_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, _ = build_fixture(directory, "retrofit")

            status, report = verify(path)

            self.assertFalse(outcomes(report)["candidate exists"])
            self.assertEqual(status, 1)

    def test_a_pushed_retrofit_branch_fails_no_push(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            stage_candidate(fixture)
            branch = f"retrofit/{fixture['target_commit'][:12]}"
            git("push", "origin", branch, cwd=Path(fixture["destination"]))

            status, report = verify(path)

            self.assertFalse(outcomes(report)["no push"])
            self.assertEqual(status, 1)

    def test_a_candidate_without_scripts_check_does_not_meet_the_red_bar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit-red")
            candidate = stage_candidate(fixture)
            (candidate / "scripts/check").unlink()

            status, report = verify(path)

            self.assertFalse(outcomes(report)["scripts/check exists"])
            self.assertFalse(outcomes(report)["bar unmet"])
            self.assertEqual(status, 1)

    def test_an_ownership_entry_naming_a_moved_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            candidate = stage_candidate(fixture)
            rewrite_ownership(candidate, {"path": "notes/", "mode": "product"})

            status, report = verify(path)

            self.assertFalse(
                outcomes(report)[
                    "ownership names no destination path; CLAUDE.md managed"
                ]
            )
            self.assertEqual(status, 1)

    def test_a_listed_but_missing_candidate_directory_is_a_failed_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            candidate = stage_candidate(fixture)
            shutil.rmtree(candidate)

            result = run_verify(path)

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertFalse(outcomes(json.loads(result.stdout))["candidate exists"])

    def test_a_malformed_record_is_a_failed_check_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, fixture = build_fixture(directory, "retrofit")
            candidate = stage_candidate(fixture)
            (candidate / ".repo-template.json").write_text("{not json")
            (candidate / fixture["unit"] / ".unit.json").write_text("[1]")

            result = run_verify(path)

            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
