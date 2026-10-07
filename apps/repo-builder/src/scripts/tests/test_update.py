from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

from test_preflight import git, git_output

MODULE_PATH = Path(__file__).parents[1] / "update.py"
SUBTREE = "base-repo"
OLD = "old\n"
NEW = "new\n"
OWNERSHIP = [
    {"path": ".repo-template.json", "mode": "managed"},
    {"path": "scripts/**", "mode": "managed"},
    {"path": ".github/**", "mode": "managed"},
    {"path": "docs/**", "mode": "managed"},
    {"path": "apps/**", "mode": "product"},
]


def load_module() -> Any:
    sys.path.insert(0, str(MODULE_PATH.parent))
    try:
        import update

        return update
    finally:
        sys.path.remove(str(MODULE_PATH.parent))


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MODULE_PATH), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def write(root: Path, path: str, content: str, executable: bool = False) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)
    file.chmod(0o755 if executable else 0o644)


class Fixture:
    """A template with two payload commits and a destination generated from the first.

    `old` and `new` map a payload path to its content; a path in `new` as
    `None` is deleted there, and `moves` renames old to new before `new` is
    written. `held` maps destination-only edits, committed on top of the old
    payload, and `executable` names the payload paths shipped at 100755 in
    the new commit.
    """

    def __init__(
        self,
        directory: str,
        old: dict[str, str],
        new: dict[str, str | None],
        *,
        moves: dict[str, str] | None = None,
        held: dict[str, str | None] | None = None,
        executable: frozenset[str] = frozenset(),
        features: dict[str, str] | None = None,
        overrides: list[dict[str, str]] | None = None,
        ignore: str = "",
    ) -> None:
        root = Path(directory)
        self.template = root / "template"
        self.destination = root / "destination"
        self.template.mkdir()
        git("init", "-q", "-b", "main", cwd=self.template)
        for path, content in old.items():
            write(self.template, f"{SUBTREE}/{path}", content)
        git("add", "-A", cwd=self.template)
        git("commit", "-q", "-m", "old", cwd=self.template)
        self.old_commit = git_output("rev-parse", "HEAD", cwd=self.template)

        for source, target in (moves or {}).items():
            (self.template / SUBTREE / target).parent.mkdir(parents=True, exist_ok=True)
            git("mv", f"{SUBTREE}/{source}", f"{SUBTREE}/{target}", cwd=self.template)
        for path, content in new.items():
            if content is None:
                git("rm", "-q", f"{SUBTREE}/{path}", cwd=self.template)
            else:
                write(
                    self.template,
                    f"{SUBTREE}/{path}",
                    content,
                    executable=path in executable,
                )
        git("add", "-A", cwd=self.template)
        git("commit", "-q", "-m", "new", cwd=self.template)
        self.target = git_output("rev-parse", "HEAD", cwd=self.template)

        self.destination.mkdir()
        git("init", "-q", "-b", "main", cwd=self.destination)
        git(
            "remote",
            "add",
            "origin",
            "https://github.com/owner/destination.git",
            cwd=self.destination,
        )
        for path, content in old.items():
            write(self.destination, path, content)
        write(self.destination, ".gitignore", ignore)
        record = {
            "schema_version": 1,
            "template": {
                "repository": str(self.template.resolve()),
                "subtree": SUBTREE,
                "commit": self.old_commit,
            },
            "destination": {
                "repository": "owner/destination",
                "default_branch": "main",
            },
            "generation": {"features": features or {}, "overrides": overrides or []},
            "ownership": OWNERSHIP,
        }
        (self.destination / ".repo-template.json").write_text(
            json.dumps(record, indent=4) + "\n"
        )
        git("add", "-A", cwd=self.destination)
        git("commit", "-q", "-m", "generated", cwd=self.destination)
        for path, content in (held or {}).items():
            if content is None:
                git("rm", "-q", path, cwd=self.destination)
            else:
                write(self.destination, path, content)
        git("add", "-A", cwd=self.destination)
        if held:
            git("commit", "-q", "-m", "destination edits", cwd=self.destination)

    def arguments(self, *, target: str | None = None) -> list[str]:
        return [
            "--template-repo",
            str(self.template),
            "--target",
            target or self.target,
            "--destination",
            str(self.destination),
        ]

    def command(self, name: str) -> dict[str, Any]:
        result = run(name, *self.arguments())
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def staged(self) -> dict[str, str]:
        """Staged name-status, `path` to `A`/`M`/`D`."""
        lines = git_output("diff", "--cached", "--name-status", cwd=self.destination)
        return {
            line.split("\t")[-1]: line.split("\t")[0] for line in lines.splitlines()
        }

    def mode(self, path: str) -> int:
        return (self.destination / path).stat().st_mode & 0o111


class ApplyTests(unittest.TestCase):
    """Each state a delta path can arrive in, decided once by a single run."""

    result: ClassVar[dict[str, object]]
    fixture: ClassVar[Fixture]
    directory: ClassVar[tempfile.TemporaryDirectory[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        old = {
            path: f"{path} v1\n"
            for path in (
                "scripts/unmodified",
                "scripts/modified",
                "scripts/deleted",
                "scripts/deleted-modified",
                "scripts/legacy",
                "scripts/mode",
                "scripts/absent",
                "scripts/overridden",
                "scripts/expired",
                "scripts/gone-already",
                "apps/product",
                "apps/pmove",
                ".github/workflows/ci.yml",
                ".github/dependabot.yml",
                ".github/PULL_REQUEST_TEMPLATE.md",
            )
        }
        cls.fixture = Fixture(
            cls.directory.name,
            old,
            {
                "scripts/unmodified": NEW,
                "scripts/modified": NEW,
                "scripts/deleted": None,
                "scripts/deleted-modified": None,
                "scripts/mode": NEW,
                "scripts/absent": NEW,
                "scripts/overridden": NEW,
                "scripts/expired": NEW,
                "scripts/gone-already": None,
                ".github/PULL_REQUEST_TEMPLATE.md": None,
                "scripts/added": NEW,
                "scripts/added-script": NEW,
                "apps/product": NEW,
                ".github/workflows/ci.yml": NEW,
                ".github/dependabot.yml": NEW,
            },
            moves={
                "scripts/legacy": "scripts/renamed",
                "apps/pmove": "scripts/from-product",
            },
            held={
                "scripts/modified": "destination edit\n",
                "scripts/deleted-modified": "destination edit\n",
                "scripts/absent": None,
                "scripts/overridden": "destination edit\n",
                "scripts/expired": None,
                "scripts/gone-already": None,
                ".github/workflows/ci.yml": "destination edit\n",
                ".github/PULL_REQUEST_TEMPLATE.md": "destination edit\n",
            },
            executable=frozenset({"scripts/mode", "scripts/added-script"}),
            overrides=[
                {"path": "scripts/overridden", "reason": "ours"},
                {"path": "scripts/expired", "reason": "gone since"},
            ],
        )
        cls.result = cls.fixture.command("apply")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def left(self) -> dict[str, dict[str, str]]:
        entries = self.result["left"]
        assert isinstance(entries, list)
        return {entry["path"]: entry for entry in entries}

    def read(self, path: str) -> str:
        return (self.fixture.destination / path).read_text()

    def test_an_unmodified_path_takes_the_payload(self) -> None:
        self.assertEqual(self.read("scripts/unmodified"), NEW)

    def test_an_unmodified_deletion_is_deleted_and_staged(self) -> None:
        self.assertFalse((self.fixture.destination / "scripts/deleted").exists())
        self.assertEqual(self.fixture.staged()["scripts/deleted"], "D")

    def test_an_unmodified_rename_moves_the_file(self) -> None:
        self.assertFalse((self.fixture.destination / "scripts/legacy").exists())
        self.assertEqual(self.read("scripts/renamed"), "scripts/legacy v1\n")

    def test_an_absent_add_writes_the_payload(self) -> None:
        self.assertEqual(self.read("scripts/added"), NEW)
        self.assertEqual(self.fixture.staged()["scripts/added"], "A")

    def test_a_modified_path_is_left_untouched_and_named(self) -> None:
        self.assertEqual(
            self.left()["scripts/modified"],
            {
                "path": "scripts/modified",
                "status": "M",
                "destination_state": "modified",
                "reason": "modified",
            },
        )
        self.assertEqual(self.read("scripts/modified"), "destination edit\n")

    def test_a_modified_deletion_is_left(self) -> None:
        self.assertEqual(self.left()["scripts/deleted-modified"]["reason"], "modified")
        self.assertTrue(
            (self.fixture.destination / "scripts/deleted-modified").exists()
        )

    def test_a_change_to_an_absent_path_is_left_as_a_deletion_conflict(self) -> None:
        entry = self.left()["scripts/absent"]
        self.assertEqual(entry["destination_state"], "absent")
        self.assertEqual(entry["reason"], "absent")
        self.assertFalse((self.fixture.destination / "scripts/absent").exists())

    def test_a_product_owned_path_is_left(self) -> None:
        self.assertEqual(self.left()["apps/product"]["reason"], "product-owned")
        self.assertEqual(self.read("apps/product"), "apps/product v1\n")

    def test_an_overridden_path_is_reported_and_skipped(self) -> None:
        self.assertEqual(
            self.result["overridden"],
            [{"path": "scripts/overridden", "reason": "ours"}],
        )
        self.assertNotIn("scripts/overridden", self.left())
        self.assertEqual(self.read("scripts/overridden"), "destination edit\n")

    def test_the_automation_directory_is_replaced_even_when_modified(self) -> None:
        self.assertEqual(self.read(".github/workflows/ci.yml"), NEW)

    def test_destination_edits_the_automation_replacement_discards_are_named(
        self,
    ) -> None:
        self.assertEqual(
            self.result["discarded"],
            [
                {"path": ".github/PULL_REQUEST_TEMPLATE.md", "action": "delete"},
                {"path": ".github/workflows/ci.yml", "action": "write"},
            ],
        )
        self.assertFalse(
            (self.fixture.destination / ".github/PULL_REQUEST_TEMPLATE.md").exists()
        )

    def test_an_expired_override_takes_the_payload(self) -> None:
        self.assertEqual(self.read("scripts/expired"), NEW)
        self.assertEqual(self.fixture.staged()["scripts/expired"], "A")
        self.assertNotIn("scripts/expired", self.left())

    def test_a_deletion_the_destination_already_made_is_applied_as_a_no_op(
        self,
    ) -> None:
        self.assertNotIn("scripts/gone-already", self.left())
        self.assertFalse((self.fixture.destination / "scripts/gone-already").exists())

    def test_a_rename_from_a_product_owned_path_keeps_its_old_path(self) -> None:
        self.assertEqual(self.left()["scripts/from-product"]["reason"], "product-owned")
        self.assertEqual(self.read("apps/pmove"), "apps/pmove v1\n")
        self.assertFalse((self.fixture.destination / "scripts/from-product").exists())

    def test_dependabot_is_left_for_derivation(self) -> None:
        self.assertEqual(self.left()[".github/dependabot.yml"]["reason"], "derive")
        self.assertEqual(
            self.read(".github/dependabot.yml"), ".github/dependabot.yml v1\n"
        )

    def test_the_payload_mode_travels_with_the_write(self) -> None:
        self.assertTrue(self.fixture.mode("scripts/mode"))
        self.assertTrue(self.fixture.mode("scripts/added-script"))
        self.assertFalse(self.fixture.mode("scripts/unmodified"))
        modes = git_output(
            "ls-files", "-s", "scripts/mode", cwd=self.fixture.destination
        )
        self.assertTrue(modes.startswith("100755"))

    def test_applied_is_counted_by_action(self) -> None:
        self.assertEqual(
            self.result["applied"],
            {"already-absent": 1, "delete": 2, "move": 1, "write": 6},
        )

    def test_every_removal_is_named_for_the_reference_grep(self) -> None:
        self.assertEqual(
            self.result["removed"],
            [
                {"path": ".github/PULL_REQUEST_TEMPLATE.md", "action": "delete"},
                {"path": "scripts/deleted", "action": "delete"},
                {"path": "scripts/gone-already", "action": "already-absent"},
                {
                    "path": "scripts/renamed",
                    "action": "move",
                    "old_path": "scripts/legacy",
                },
            ],
        )

    def test_the_output_carries_the_preflight_blocks(self) -> None:
        template = self.result["template"]
        assert isinstance(template, dict)
        self.assertEqual(template["target_commit"], self.fixture.target)
        self.assertIn("unmatched_overrides", self.result)
        self.assertIn("destination", self.result)


class ApplyEdgeTests(unittest.TestCase):
    def test_codeql_is_left_where_the_destination_omitted_it_by_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/workflows/codeql.yml": OLD, ".github/workflows/ci.yml": OLD},
                {".github/workflows/codeql.yml": NEW, ".github/workflows/ci.yml": NEW},
                features={"codeql": "omitted-by-choice"},
            )

            result = fixture.command("apply")

            self.assertEqual(
                [(entry["path"], entry["reason"]) for entry in result["left"]],
                [(".github/workflows/codeql.yml", "codeql-omitted-by-choice")],
            )
            self.assertEqual(
                (fixture.destination / ".github/workflows/codeql.yml").read_text(), OLD
            )
            self.assertEqual(
                (fixture.destination / ".github/workflows/ci.yml").read_text(), NEW
            )

    def test_a_replaced_automation_rename_lands_whatever_the_destination_holds(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/workflows/old.yml": OLD},
                {},
                moves={".github/workflows/old.yml": ".github/workflows/new.yml"},
                held={".github/workflows/old.yml": "destination edit\n"},
            )

            fixture.command("apply")

            self.assertFalse(
                (fixture.destination / ".github/workflows/old.yml").exists()
            )
            self.assertEqual(
                (fixture.destination / ".github/workflows/new.yml").read_text(), OLD
            )

    def test_a_discarded_automation_move_names_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/workflows/old.yml": OLD},
                {},
                moves={".github/workflows/old.yml": ".github/workflows/new.yml"},
                held={".github/workflows/old.yml": "destination edit\n"},
            )

            result = fixture.command("apply")

            self.assertEqual(
                result["discarded"],
                [
                    {
                        "path": ".github/workflows/new.yml",
                        "action": "move",
                        "old_path": ".github/workflows/old.yml",
                    }
                ],
            )

    def test_an_override_on_the_automation_directory_is_refused_and_landed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/workflows/ci.yml": OLD},
                {".github/workflows/ci.yml": NEW},
                held={".github/workflows/ci.yml": "destination edit\n"},
                overrides=[{"path": ".github/workflows/ci.yml", "reason": "ours"}],
            )

            result = fixture.command("apply")

            self.assertEqual(
                result["refused_overrides"],
                [{"path": ".github/workflows/ci.yml", "reason": "ours"}],
            )
            self.assertEqual(result["overridden"], [])
            self.assertEqual(
                (fixture.destination / ".github/workflows/ci.yml").read_text(), NEW
            )

    def test_an_ignored_path_is_written_to_disk_and_not_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/keep": OLD},
                {"scripts/keep": NEW, "docs/local.md": NEW},
                ignore="docs/local.md\n",
            )

            fixture.command("apply")

            self.assertEqual((fixture.destination / "docs/local.md").read_text(), NEW)
            self.assertEqual(fixture.staged(), {"scripts/keep": "M"})

    def test_an_expired_rename_writes_the_new_path_and_removes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/old": OLD},
                {},
                moves={"scripts/old": "scripts/new"},
                held={"scripts/old": None},
                overrides=[{"path": "scripts/old", "reason": "gone"}],
            )

            result = fixture.command("apply")

            self.assertEqual(result["applied"], {"move": 1})
            self.assertEqual((fixture.destination / "scripts/new").read_text(), OLD)

    def test_a_git_failure_reading_the_ignore_rules_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            module = load_module()

            with self.assertRaises(module.PreflightError):
                module.is_ignored(Path(directory), "scripts/a")

    def test_preflight_failures_are_failures_of_the_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})
            write(fixture.destination, "scripts/dirty", "x")

            result = run("apply", *fixture.arguments())

            self.assertEqual(result.returncode, 2)
            self.assertIn("must be clean", result.stderr)


class ProofTests(unittest.TestCase):
    def test_copies_are_identical_and_the_rest_is_authored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/copy": OLD, "scripts/merged": OLD, "docs/local.md": OLD},
                {"scripts/copy": NEW, "scripts/merged": NEW},
                held={"scripts/merged": "destination edit\n"},
            )
            fixture.command("apply")
            write(fixture.destination, "scripts/merged", NEW + "hand merged\n")
            write(fixture.destination, "scripts/own", "ours\n")
            git("add", "-A", cwd=fixture.destination)

            result = fixture.command("proof")

            self.assertEqual(
                result["authored"],
                [".repo-template.json", "scripts/merged", "scripts/own"],
            )
            self.assertEqual(result["total"], 4)
            self.assertEqual(result["identical"], 1)

    def test_an_ignored_payload_path_is_proved_against_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/keep": OLD, "scripts/local": OLD, "docs/edited": OLD},
                {"scripts/keep": NEW, "scripts/local": NEW, "docs/edited": NEW},
                ignore="scripts/local\ndocs/edited\n",
            )
            fixture.command("apply")
            (fixture.destination / "docs/edited").write_text("edited after\n")

            result = fixture.command("proof")

            self.assertEqual(result["authored"], [".repo-template.json", "docs/edited"])
            # scripts/keep, scripts/local, docs/edited, and the record.
            self.assertEqual(result["total"], 4)
            self.assertEqual(result["identical"], 2)

    def test_an_ignored_path_the_update_never_touched_is_not_proved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/keep": OLD, "docs/standing": OLD},
                {"scripts/keep": NEW},
                ignore="docs/standing\n",
            )
            fixture.command("apply")
            (fixture.destination / "docs/standing").write_text("local edit\n")

            result = fixture.command("proof")

            self.assertEqual(result["authored"], [".repo-template.json"])
            self.assertEqual(result["total"], 2)

    def test_a_deleted_path_is_not_compared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/gone": OLD, "scripts/a": OLD},
                {"scripts/gone": None},
            )
            fixture.command("apply")

            result = fixture.command("proof")

            self.assertEqual(result["authored"], [".repo-template.json"])
            self.assertEqual(result["total"], 1)


class AdvanceTests(unittest.TestCase):
    def test_the_commit_is_rewritten_in_place_and_formatting_survives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})
            record = fixture.destination / ".repo-template.json"
            before = record.read_text()

            result = fixture.command("advance")

            self.assertEqual(result["old_commit"], fixture.old_commit)
            self.assertEqual(result["new_commit"], fixture.target)
            self.assertEqual(
                record.read_text(), before.replace(fixture.old_commit, fixture.target)
            )
            self.assertEqual(fixture.staged(), {".repo-template.json": "M"})

    def test_a_target_ref_resolves_to_the_full_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})

            result = run("advance", *fixture.arguments(target="main"))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["new_commit"], fixture.target)

    def test_the_old_commit_in_another_field_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})
            record = fixture.destination / ".repo-template.json"
            manifest = json.loads(record.read_text())
            manifest["generation"]["overrides"] = [
                {"path": "scripts/a", "reason": f"kept since {fixture.old_commit}"}
            ]
            record.write_text(json.dumps(manifest, indent=4) + "\n")
            git("commit", "-q", "-am", "note", cwd=fixture.destination)

            result = fixture.command("advance")

            self.assertEqual(result["new_commit"], fixture.target)
            written = json.loads(record.read_text())
            self.assertEqual(written["template"]["commit"], fixture.target)
            self.assertIn(
                fixture.old_commit, written["generation"]["overrides"][0]["reason"]
            )

    def test_a_commit_pair_that_occurs_twice_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})
            record = fixture.destination / ".repo-template.json"
            manifest = json.loads(record.read_text())
            manifest["generation"]["twin"] = {"commit": fixture.old_commit}
            record.write_text(json.dumps(manifest, indent=4) + "\n")
            before = record.read_text()

            result = run("advance", *fixture.arguments())

            self.assertEqual(result.returncode, 2)
            self.assertIn("holds 2", result.stderr)
            self.assertEqual(record.read_text(), before)

    def test_a_missing_manifest_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})
            shutil.rmtree(
                fixture.destination / ".repo-template.json", ignore_errors=True
            )
            (fixture.destination / ".repo-template.json").unlink()

            result = run("advance", *fixture.arguments())

            self.assertEqual(result.returncode, 2)
            self.assertIn("manifest does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
