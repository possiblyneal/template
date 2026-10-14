from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

from test_preflight import git, git_output
from test_retrofit import COMMIT_IDENTITY, gh_calls, stub_gh

MODULE_PATH = Path(__file__).parents[1] / "update.py"
PAYLOAD = Path(__file__).parents[5] / "apps/github-repository-template/src/base-repo"
LIBRARY_PATH = "scripts/libs/dependabot.sh"
LIBRARY = (PAYLOAD / LIBRARY_PATH).read_text()
DEPENDABOT_PAYLOAD = (PAYLOAD / ".github/dependabot.yml").read_text()
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
                ".github/PULL_REQUEST_TEMPLATE.md",
            )
        } | {
            LIBRARY_PATH: LIBRARY,
            ".github/dependabot.yml": DEPENDABOT_PAYLOAD,
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
                ".github/dependabot.yml": DEPENDABOT_PAYLOAD + "# v2\n",
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

    def test_dependabot_is_landed_rather_than_left(self) -> None:
        self.assertNotIn(".github/dependabot.yml", self.left())
        self.assertTrue(
            self.read(".github/dependabot.yml").startswith(DEPENDABOT_PAYLOAD)
        )
        self.assertEqual(self.fixture.staged()[".github/dependabot.yml"], "M")

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
            {"already-absent": 1, "delete": 2, "move": 1, "write": 7},
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


DESTINATION_DEPENDABOT = (
    DEPENDABOT_PAYLOAD
    + """
  - package-ecosystem: terraform
    directory: /infra
    schedule:
      interval: weekly

  - package-ecosystem: gomod
    directory: /apps/old
    schedule:
      interval: weekly
"""
)
CARGO_WORKSPACE = '[workspace]\nmembers = ["crates/*"]\n'


def derivation_fixture(directory: str, tracked: dict[str, str]) -> Fixture:
    """The real library and payload file, a destination tracking `tracked`.

    The destination already holds its own `dependabot.yml` with a terraform
    entry and a gomod entry for a directory that no longer has a module.
    """
    return Fixture(
        directory,
        {LIBRARY_PATH: LIBRARY, ".github/dependabot.yml": DEPENDABOT_PAYLOAD},
        {
            LIBRARY_PATH: LIBRARY,
            ".github/dependabot.yml": DEPENDABOT_PAYLOAD + "# v2\n",
        },
        held={**tracked, ".github/dependabot.yml": DESTINATION_DEPENDABOT},
    )


def gomod_entry(directory: str) -> str:
    return f"""  - package-ecosystem: gomod
    directory: {directory}
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      gomod:
        patterns:
          - "*"
"""


class DependabotDerivationTests(unittest.TestCase):
    """`apply` derives the ecosystem entries from the destination's tracked manifests."""

    result: ClassVar[dict[str, Any]]
    fixture: ClassVar[Fixture]
    written: ClassVar[str]
    directory: ClassVar[tempfile.TemporaryDirectory[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.fixture = derivation_fixture(
            cls.directory.name,
            {
                "apps/glydr/go.mod": "module glydr\n",
                "apps/glydr/Dockerfile": "FROM scratch\n",
                "apps/glydr/Dockerfile.dev": "FROM scratch\n",
                "apps/glydr/notes.md": "not a manifest\n",
                "deploy/containerfile/Containerfile": "FROM scratch\n",
                "package.json": '{"workspaces": ["apps/web"]}\n',
                "apps/web/package.json": "{}\n",
                "apps/admin/package.json": "{}\n",
                "pyproject.toml": "[project]\nname = 'root'\n",
                "uv.lock": "",
                "apps/tool/pyproject.toml": "[project]\nname = 'tool'\n",
                "Cargo.toml": CARGO_WORKSPACE,
                "crates/a/Cargo.toml": "[package]\nname = 'a'\n",
                "crates/b/Cargo.toml": "[package]\nname = 'b'\n",
                "apps/other/Cargo.toml": "[package]\nname = 'other'\n",
                f"{SUBTREE}/package.json": "{}\n",
                f"{SUBTREE}/.pre-commit-config.yaml": "repos: []\n",
            },
        )
        cls.result = cls.fixture.command("apply")
        cls.written = (cls.fixture.destination / ".github/dependabot.yml").read_text()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def watched(self, ecosystem: str) -> list[str]:
        return [
            directory
            for name, directory in self.result["dependabot"]["watched"]
            if name == ecosystem
        ]

    def test_the_payload_file_is_kept_and_the_entries_follow_it(self) -> None:
        self.assertTrue(
            self.written.startswith(
                DEPENDABOT_PAYLOAD.split("  - package-ecosystem: pre-commit")[0]
            )
        )
        self.assertIn("\n\n" + gomod_entry("/apps/glydr"), self.written)
        self.assertTrue(self.written.endswith('          - "*"\n'))

    def test_the_written_file_is_staged(self) -> None:
        self.assertEqual(self.fixture.staged()[".github/dependabot.yml"], "M")
        self.assertEqual(
            git_output("diff", ".github/dependabot.yml", cwd=self.fixture.destination),
            "",
        )

    def test_ecosystems_are_ordered_and_a_docker_directory_is_listed_once(self) -> None:
        self.assertEqual(
            self.watched("docker"), ["/apps/glydr", "/deploy/containerfile"]
        )
        names = [name for name, _ in self.result["dependabot"]["watched"]]
        self.assertEqual(
            list(dict.fromkeys(names)),
            [
                "github-actions",
                "pre-commit",
                "cargo",
                "docker",
                "gomod",
                "npm",
                "pip",
                "uv",
            ],
        )

    def test_a_pyproject_beside_a_uv_lock_earns_uv_and_the_rest_earn_pip(self) -> None:
        self.assertEqual(self.watched("uv"), ["/"])
        self.assertEqual(self.watched("pip"), ["/apps/tool"])

    def test_several_directories_are_one_entry_with_a_directories_list(self) -> None:
        self.assertEqual(self.watched("npm"), ["/", "/apps/admin"])
        self.assertIn(
            "  - package-ecosystem: npm\n    directories:\n      - /\n      - /apps/admin\n",
            self.written,
        )
        self.assertEqual(self.written.count("package-ecosystem: npm"), 1)

    def test_a_workspace_member_earns_no_entry(self) -> None:
        self.assertEqual(self.watched("cargo"), ["/", "/apps/other"])
        self.assertNotIn("/apps/web", self.watched("npm"))

    def test_the_payload_subtree_earns_no_entry_and_adds_its_pre_commit_directory(
        self,
    ) -> None:
        self.assertNotIn(f"/{SUBTREE}", self.watched("npm"))
        self.assertEqual(self.watched("pre-commit"), ["/", f"/{SUBTREE}"])
        self.assertIn(
            f"    directories:\n      - /\n      - /{SUBTREE}\n    schedule:",
            self.written,
        )
        self.assertIn(
            "      pre-commit:\n        group-by: dependency-name\n        patterns:",
            self.written,
        )

    def test_an_old_entry_the_file_lacks_is_dropped_by_pair(self) -> None:
        self.assertEqual(
            self.result["dependabot"]["dropped"],
            [["gomod", "/apps/old"], ["terraform", "/infra"]],
        )

    def test_dependabot_is_no_longer_left_for_derivation(self) -> None:
        self.assertEqual(self.result["left"], [])

    def test_a_missing_library_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/dependabot.yml": DEPENDABOT_PAYLOAD},
                {".github/dependabot.yml": DEPENDABOT_PAYLOAD + "# v2\n"},
            )

            result = run("apply", *fixture.arguments())

            self.assertEqual(result.returncode, 2)
            self.assertIn(LIBRARY_PATH, result.stderr)

    def test_dependabot_is_null_when_the_delta_does_not_hold_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory, {"scripts/a": OLD}, {"scripts/a": NEW})

            self.assertIsNone(fixture.command("apply")["dependabot"])

    def test_an_unparsable_workspace_manifest_counts_as_no_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = derivation_fixture(
                directory,
                {"Cargo.toml": "[workspace\n", "crates/a/Cargo.toml": "[package]\n"},
            )

            result = fixture.command("apply")

            watched = [p for p in result["dependabot"]["watched"] if p[0] == "cargo"]
            self.assertEqual(watched, [["cargo", "/"], ["cargo", "/crates/a"]])


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
            self.assertEqual(
                result["discarded"],
                [{"path": ".github/workflows/ci.yml", "action": "write"}],
            )

    def test_an_automation_override_on_a_rename_names_the_recorded_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {".github/workflows/old.yml": OLD},
                {},
                moves={".github/workflows/old.yml": ".github/workflows/new.yml"},
                held={".github/workflows/old.yml": "destination edit\n"},
                overrides=[{"path": ".github/workflows/old.yml", "reason": "ours"}],
            )

            result = fixture.command("apply")

            self.assertEqual(
                result["refused_overrides"],
                [{"path": ".github/workflows/old.yml", "reason": "ours"}],
            )

    def test_an_automation_override_outside_the_delta_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/a": OLD, ".github/workflows/ci.yml": OLD},
                {"scripts/a": NEW},
                overrides=[{"path": ".github/workflows/ci.yml", "reason": "ours"}],
            )

            result = fixture.command("apply")

            self.assertEqual(
                result["refused_overrides"],
                [{"path": ".github/workflows/ci.yml", "reason": "ours"}],
            )
            self.assertEqual(result["unmatched_overrides"], [])

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


CHECK_TABLE = "| lint | pass |\n| test | pass |\n"
SETTINGS_OUTPUT = "ruleset: ok\noptional missing: secret scanning\n"


def headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("## ")]


class PrBodyTests(unittest.TestCase):
    """The body is rendered from records the flow writes beside the clone."""

    def sibling(self, fixture: Fixture, suffix: str) -> Path:
        return Path(f"{fixture.destination}{suffix}")

    def records(self, fixture: Fixture, *, skip: str = "") -> None:
        """Write the four records the way the flow would."""
        for name in ("apply", "proof"):
            result = run(name, *fixture.arguments())
            assert result.returncode == 0, result.stderr
            self.sibling(fixture, f".{name}.json").write_text(result.stdout)
        write(
            fixture.destination,
            ".github/PULL_REQUEST_TEMPLATE.md",
            (PAYLOAD / ".github/PULL_REQUEST_TEMPLATE.md").read_text(),
        )
        self.sibling(fixture, ".check.txt").write_text(CHECK_TABLE)
        self.sibling(fixture, ".settings.txt").write_text(SETTINGS_OUTPUT)
        if skip:
            self.sibling(fixture, skip).unlink()

    def render(self, fixture: Fixture) -> tuple[dict[str, Any], str]:
        result = fixture.command("pr-body")
        body = Path(str(result["path"])).read_text()
        return result, body

    def test_the_body_follows_the_templates_headings_and_the_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/copy": OLD, "scripts/other": OLD},
                {"scripts/copy": NEW, "scripts/other": NEW},
            )
            self.records(fixture)

            result, body = self.render(fixture)

            self.assertEqual(result["operation"], "update-pr-body")
            self.assertEqual(result["path"], f"{fixture.destination}.pr-body.md")
            self.assertEqual(result["slots"], [])
            template = fixture.destination / ".github/PULL_REQUEST_TEMPLATE.md"
            self.assertEqual(headings(body), headings(template.read_text()))
            self.assertIn(f"`{fixture.old_commit}` to `{fixture.target}`", body)
            self.assertIn(f"- {fixture.target[:7]}", body)
            self.assertIn("```\n" + CHECK_TABLE.rstrip() + "\n```", body)
            self.assertIn("```\n" + SETTINGS_OUTPUT.rstrip() + "\n```", body)
            self.assertIn("2/3 copied paths byte-identical to the payload", body)
            self.assertIn("authored: .repo-template.json", body)
            self.assertIn("None. Every delta path landed without a hand merge.", body)
            self.assertIn("**Door:** two-way: a revert restores everything", body)
            self.assertIn("- `scripts/copy`", body)
            self.assertIn("- `scripts/other`", body)

    def test_a_non_empty_left_turns_decisions_into_a_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(
                directory,
                {"scripts/merged": OLD},
                {"scripts/merged": NEW},
                held={"scripts/merged": "destination edit\n"},
            )
            self.records(fixture)

            result, body = self.render(fixture)

            self.assertEqual(result["slots"], ["decisions"])
            self.assertIn("[[FILL: decisions]]", body)
            self.assertNotIn("None. Every delta path landed", body)

    def test_a_missing_record_fails_naming_it(self) -> None:
        for suffix in (".apply.json", ".proof.json", ".check.txt", ".settings.txt"):
            with (
                self.subTest(record=suffix),
                tempfile.TemporaryDirectory() as directory,
            ):
                fixture = Fixture(
                    directory, {"scripts/copy": OLD}, {"scripts/copy": NEW}
                )
                self.records(fixture, skip=suffix)

                result = run("pr-body", *fixture.arguments())

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    f"{fixture.destination}{suffix}", result.stderr + result.stdout
                )


CHECK_STUB = '#!/bin/sh\nprintf "%s\\n" "$CHECK_OUTPUT"\nexit "${CHECK_STATUS:-0}"\n'
SETTINGS_STUB = '#!/bin/sh\nprintf "%s\\n" "$SETTINGS_OUTPUT"\n'
RUN_ENV = {
    **COMMIT_IDENTITY,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "CHECK_OUTPUT": CHECK_TABLE.rstrip(),
    "SETTINGS_OUTPUT": "ruleset: ok",
}


def run_with(
    *arguments: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MODULE_PATH), *arguments],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **(RUN_ENV if env is None else env)},
    )


def run_fixture(directory: str, **options: Any) -> Fixture:
    """A destination a `run` can finish: PR template, stub check and settings."""
    template = (PAYLOAD / ".github/PULL_REQUEST_TEMPLATE.md").read_text()
    fixture = Fixture(
        directory,
        {"scripts/copy": OLD, ".github/PULL_REQUEST_TEMPLATE.md": template},
        {"scripts/copy": NEW},
        **options,
    )
    write(fixture.destination, "scripts/check", CHECK_STUB, executable=True)
    write(fixture.destination, "scripts/repo-settings", SETTINGS_STUB, executable=True)
    git("add", "-A", cwd=fixture.destination)
    git("commit", "-q", "-m", "stubs", cwd=fixture.destination)
    return fixture


def run_command(
    fixture: Fixture,
    *destinations: Path,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    result = run_with(
        "run",
        "--template-repo",
        str(fixture.template),
        "--target",
        fixture.target,
        "--destination",
        *map(str, destinations or (fixture.destination,)),
        "--generated-by",
        "claude-test",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["operation"] == "update-run"
    return parsed["destinations"]


class RunTests(unittest.TestCase):
    """The mechanical steps over clones, one short result each."""

    def test_nothing_left_ends_committed_on_the_branch_and_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            destination = fixture.destination

            [entry] = run_command(fixture)

            self.assertEqual(
                entry,
                {
                    "destination": str(destination),
                    "status": "ready",
                    "detail": "",
                    "drift": [],
                },
            )
            branch = f"repo-builder/{fixture.target[:12]}"
            self.assertEqual(
                git_output("branch", "--show-current", cwd=destination), branch
            )
            self.assertEqual(
                git_output("log", "-1", "--format=%s", cwd=destination),
                f"chore(template): update to template {fixture.target[:12]}",
            )
            message = git_output("log", "-1", "--format=%B", cwd=destination)
            self.assertIn(
                f"Carries the template payload from {fixture.old_commit} "
                f"to {fixture.target}.",
                message,
            )
            self.assertIn("Generated-By: claude-test", message)
            manifest = git_output("show", "HEAD:.repo-template.json", cwd=destination)
            self.assertIn(f'"commit": "{fixture.target}"', manifest)
            self.assertEqual((destination / "scripts/copy").read_text(), NEW)
            self.assertEqual(git_output("status", "--short", cwd=destination), "")
            body = Path(f"{destination}.pr-body.md").read_text()
            self.assertIn("```\n" + CHECK_TABLE.rstrip() + "\n```", body)
            for suffix in (".apply.json", ".proof.json", ".check.txt", ".settings.txt"):
                self.assertTrue(Path(f"{destination}{suffix}").is_file(), suffix)

    def test_paths_left_stop_the_destination_as_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            destination = fixture.destination
            write(destination, "scripts/copy", "edited\n")
            git("commit", "-q", "-am", "destination edit", cwd=destination)

            [entry] = run_command(fixture)

            self.assertEqual(entry["status"], "reconcile")
            self.assertEqual(entry["detail"], "scripts/copy")
            self.assertEqual(
                git_output("branch", "--show-current", cwd=destination), "main"
            )
            record = json.loads(Path(f"{destination}.apply.json").read_text())
            self.assertEqual(record["operation"], "update-apply")
            self.assertEqual(
                [left["path"] for left in record["left"]], ["scripts/copy"]
            )
            self.assertFalse(Path(f"{destination}.proof.json").exists())
            self.assertFalse(Path(f"{destination}.check.txt").exists())

    def test_a_failed_check_restores_the_manifest_and_names_the_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            destination = fixture.destination

            [entry] = run_command(fixture, env={**RUN_ENV, "CHECK_STATUS": "1"})

            self.assertEqual(entry["status"], "check-failed")
            self.assertEqual(entry["detail"], f"{destination}/tmp/check.log")
            staged = git_output("show", ":.repo-template.json", cwd=destination)
            self.assertIn(f'"commit": "{fixture.old_commit}"', staged)
            self.assertIn(
                f'"commit": "{fixture.old_commit}"',
                (destination / ".repo-template.json").read_text(),
            )
            self.assertEqual(
                git_output("branch", "--show-current", cwd=destination), "main"
            )
            self.assertEqual(
                git_output("rev-list", "--count", "HEAD", cwd=destination), "2"
            )
            self.assertTrue(Path(f"{destination}.check.txt").is_file())

    def test_settings_drift_is_reported_without_stopping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            output = (
                "ruleset: ok\n"
                "optional missing: secret scanning\n"
                "optional missing: rulesets"
            )

            [entry] = run_command(fixture, env={**RUN_ENV, "SETTINGS_OUTPUT": output})

            self.assertEqual(entry["status"], "ready")
            self.assertEqual(
                entry["drift"],
                ["optional missing: secret scanning", "optional missing: rulesets"],
            )

    def test_one_destination_stopping_does_not_stop_the_others(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            missing = Path(directory) / "missing"

            entries = run_command(fixture, missing, fixture.destination)

            self.assertEqual(
                [entry["status"] for entry in entries], ["stopped", "ready"]
            )
            self.assertIn(str(missing), entries[0]["detail"])

    def test_a_refused_commit_stops_with_the_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = run_fixture(directory)
            hook = fixture.destination / ".git/hooks/commit-msg"
            hook.write_text("#!/bin/sh\necho refused by test hook >&2\nexit 1\n")
            hook.chmod(0o755)

            [entry] = run_command(fixture)

            self.assertEqual(entry["status"], "stopped")
            self.assertIn("refused by test hook", entry["detail"])


class PublishTests(unittest.TestCase):
    """Pushing and opening the pull request, after the parent's remote gate."""

    def ready(self, directory: str) -> tuple[Fixture, Path]:
        fixture = run_fixture(directory)
        run_command(fixture)
        destination = fixture.destination
        origin = Path(directory) / "origin.git"
        git("init", "-q", "--bare", "-b", "main", str(origin))
        git("remote", "set-url", "origin", str(origin), cwd=destination)
        git("push", "-q", "origin", "main", cwd=destination)
        git("remote", "set-head", "origin", "main", cwd=destination)
        return fixture, origin

    def publish(self, directory: str, *destinations: Path) -> list[dict[str, Any]]:
        gh = Path(directory) / "gh"
        gh.mkdir()
        env = stub_gh(
            str(gh),
            [
                {
                    "args": ["pr", "create"],
                    "stdout": "https://github.com/owner/destination/pull/7\n",
                }
            ],
        )
        result = run_with("publish", "--destination", *map(str, destinations), env=env)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["destinations"]

    def test_it_pushes_the_branch_and_opens_the_pull_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, origin = self.ready(directory)
            destination = fixture.destination

            [entry] = self.publish(directory, destination)

            branch = f"repo-builder/{fixture.target[:12]}"
            self.assertEqual(entry["status"], "published")
            self.assertEqual(
                entry["detail"], "https://github.com/owner/destination/pull/7"
            )
            self.assertEqual(
                git_output("rev-parse", branch, cwd=origin),
                git_output("rev-parse", "HEAD", cwd=destination),
            )
            self.assertEqual(
                gh_calls(str(Path(directory) / "gh")),
                [
                    [
                        "pr",
                        "create",
                        "--base",
                        "main",
                        "--head",
                        branch,
                        "--title",
                        f"chore(template): update to template {fixture.target[:12]}",
                        "--body-file",
                        f"{destination}.pr-body.md",
                    ]
                ],
            )

    def test_a_destination_off_a_repo_builder_branch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, origin = self.ready(directory)
            git("switch", "-q", "main", cwd=fixture.destination)

            [entry] = self.publish(directory, fixture.destination)

            self.assertEqual(entry["status"], "refused")
            self.assertIn("repo-builder/", entry["detail"])
            self.assertEqual(git_output("branch", "--list", cwd=origin), "* main")

    def test_a_body_with_an_open_slot_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, origin = self.ready(directory)
            body = Path(f"{fixture.destination}.pr-body.md")
            body.write_text(body.read_text() + "[[FILL: decisions]]\n")

            [entry] = self.publish(directory, fixture.destination)

            self.assertEqual(entry["status"], "refused")
            self.assertIn("[[FILL:", entry["detail"])
            self.assertEqual(git_output("branch", "--list", cwd=origin), "* main")
