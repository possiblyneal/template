from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_preflight import git

SETUP = Path(__file__).parents[2] / "evals" / "setup_fixture.py"
VERIFY = Path(__file__).parents[2] / "evals" / "verify_fixture.py"


def build_fixture(directory: str, scenario: str) -> tuple[Path, dict[str, str]]:
    root = Path(directory) / "fixture"
    subprocess.run(
        ["python3", str(SETUP), scenario, str(root)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return root / "fixture.json", json.loads((root / "fixture.json").read_text())


def stage_candidate(fixture: dict[str, str]) -> Path:
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
    unit = candidate / "apps/ledger"
    (unit / "scripts").mkdir(parents=True)
    git("mv", "src", "apps/ledger/src", cwd=candidate)
    git("mv", "tests", "apps/ledger/tests", cwd=candidate)
    git("mv", "scripts/build.py", "apps/ledger/scripts/build.py", cwd=candidate)
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


def verify(fixture_path: Path) -> tuple[int, dict[str, object]]:
    result = subprocess.run(
        ["python3", str(VERIFY), str(fixture_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, json.loads(result.stdout) if result.stdout else {}


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
            (candidate / "apps/ledger/src/ledger/rates.py").write_text("# edited\n")

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


if __name__ == "__main__":
    unittest.main()
