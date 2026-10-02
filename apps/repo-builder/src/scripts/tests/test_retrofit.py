from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_preflight import git, git_output

MODULE_PATH = Path(__file__).parents[1] / "retrofit.py"
SETUP = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"


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


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MODULE_PATH), *arguments],
        text=True,
        capture_output=True,
        check=False,
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


if __name__ == "__main__":
    unittest.main()
