from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from test_preflight import git, git_output, preflight
from test_retrofit import (
    COMMIT_IDENTITY,
    FORBIDDEN,
    NOT_FOUND,
    PAYLOAD,
    UPGRADE,
    gh_calls,
    hook_environments_unavailable,
    stub_gh,
)

MODULE_PATH = Path(__file__).parents[1] / "generate.py"

OWNERSHIP = (
    MODULE_PATH.parents[3] / "github-repository-template" / "src" / "ownership.json"
)
SETUP = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
TEMPLATE_SOURCE = MODULE_PATH.parents[3] / "github-repository-template" / "src"
RULESET = TEMPLATE_SOURCE / "ruleset.json"
WORKFLOWS = TEMPLATE_SOURCE / "base-repo" / ".github" / "workflows"


def generation_fixture(directory: str) -> dict[str, str]:
    root = Path(directory) / "fixture"
    subprocess.run(
        ["python3", str(SETUP), "generation", str(root)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads((root / "fixture.json").read_text())


def isolated_git_config(directory: str) -> dict[str, str]:
    """A global config naming another initial branch, so `-b` has to take."""
    config = Path(directory) / "gitconfig"
    config.write_text("[init]\n\tdefaultBranch = master\n")
    return {**os.environ, "GIT_CONFIG_GLOBAL": str(config)}


def tree_entries(directory: Path) -> dict[str, tuple[str, str]]:
    """Every file under a tree, as git would record it: mode and blob hash."""
    entries: dict[str, tuple[str, str]] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if relative.parts[0] == ".git" or path.is_dir() and not path.is_symlink():
            continue
        if path.is_symlink():
            # A link's blob is its target, hashed as-is.
            mode = "120000"
            blob = subprocess.run(
                ["git", "hash-object", "--stdin"],
                input=os.readlink(path),
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
        else:
            mode = "100755" if os.access(path, os.X_OK) else "100644"
            blob = git_output("hash-object", "--no-filters", str(path), cwd=directory)
        entries[relative.as_posix()] = (mode, blob)
    return entries


def payload_entries(
    template: str, commit: str, subtree: str
) -> dict[str, tuple[str, str]]:
    listing = git_output("ls-tree", "-r", "-z", f"{commit}:{subtree}", cwd=template)
    entries: dict[str, tuple[str, str]] = {}
    for line in filter(None, listing.split("\0")):
        meta, path = line.split("\t", 1)
        mode, _, blob = meta.split()
        entries[path] = (mode, blob)
    return entries


class MaterializeTests(unittest.TestCase):
    """Step 3: the payload at the source commit, as a fresh repository in tmp/."""

    def _materialize(
        self, fixture: dict[str, str], env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        # No --template-repo: the skill runs from the template checkout.
        return subprocess.run(
            [
                "python3",
                str(MODULE_PATH),
                "materialize",
                "--records",
                self._records(fixture),
                "--target",
                fixture["target_commit"],
                "--subtree",
                fixture["subtree"],
                "--destination-repository",
                fixture["destination_repository"],
            ],
            cwd=fixture["template_repo"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def _records(fixture: dict[str, str]) -> str:
        template = Path(fixture["template_repo"])
        return str(
            template / "tmp" / f"billing-service.{fixture['target_commit'][:12]}"
        )

    def test_the_candidate_is_the_payload_on_an_unborn_default_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = generation_fixture(directory)
            # A fixture symlink, which a copy that follows links would flatten.
            template = Path(fixture["template_repo"])
            (template / fixture["subtree"] / "docs" / "link.md").symlink_to(
                "adrs/0000-template.md"
            )
            git("add", "-A", cwd=template)
            git("commit", "-q", "-m", "chore: link", cwd=template)
            fixture["target_commit"] = git_output("rev-parse", "HEAD", cwd=template)
            # A later commit the candidate must not see.
            (template / fixture["subtree"] / "LATER.md").write_text("later\n")
            git("add", "-A", cwd=template)
            git("commit", "-q", "-m", "chore: later", cwd=template)

            result = self._materialize(fixture, isolated_git_config(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            candidate = template / "tmp" / "billing-service"
            expected = payload_entries(
                fixture["template_repo"], fixture["target_commit"], fixture["subtree"]
            )
            self.assertEqual(tree_entries(candidate), expected)
            self.assertNotIn("LATER.md", tree_entries(candidate))
            self.assertEqual(
                git_output("symbolic-ref", "HEAD", cwd=candidate), "refs/heads/main"
            )
            self.assertEqual(
                git(
                    "rev-parse", "--verify", "-q", "HEAD", cwd=candidate, check=False
                ).returncode,
                1,
            )
            self.assertEqual(git_output("remote", cwd=candidate), "")
            record = json.loads(
                Path(f"{self._records(fixture)}.materialize.json").read_text()
            )
            self.assertEqual(record["candidate"], str(candidate))
            self.assertEqual(record["commit"], fixture["target_commit"])
            self.assertEqual(record["head"], "refs/heads/main")
            self.assertEqual(record["payload_paths"], len(expected))
            self.assertEqual(json.loads(result.stdout), record)

    def test_a_candidate_that_already_holds_files_is_refused_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = generation_fixture(directory)
            env = isolated_git_config(directory)
            first = self._materialize(fixture, env)
            self.assertEqual(first.returncode, 0, first.stderr)
            candidate = Path(fixture["template_repo"]) / "tmp" / "billing-service"
            (candidate / "CLAUDE.md").write_text("personalized\n")
            before = tree_entries(candidate)

            second = self._materialize(fixture, env)

            self.assertEqual(second.returncode, 2)
            self.assertIn("not empty", json.loads(second.stderr)["error"])
            self.assertEqual(tree_entries(candidate), before)
            self.assertEqual(
                git_output("symbolic-ref", "HEAD", cwd=candidate), "refs/heads/main"
            )


def run_generate(
    *arguments: str,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MODULE_PATH), *arguments],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def materialized_candidate(directory: str) -> tuple[Path, str]:
    """A fresh candidate on an unborn `main` and the materialize record naming it."""
    candidate = Path(directory) / "tmp" / "billing-service"
    candidate.mkdir(parents=True)
    git("init", "-q", "-b", "main", cwd=candidate)
    records = str(Path(directory) / "tmp" / "billing-service.0123456789ab")
    Path(f"{records}.materialize.json").write_text(
        json.dumps({"candidate": str(candidate), "default_branch": "main"})
    )
    return candidate, records


class BootstrapTests(unittest.TestCase):
    """Step 4: the empty root commit, pushed to the candidate's remote."""

    @staticmethod
    def _candidate_with_origin(directory: str) -> tuple[Path, Path, str]:
        candidate, records = materialized_candidate(directory)
        origin = Path(directory) / "origin.git"
        git("init", "-q", "--bare", "-b", "main", str(origin), cwd=directory)
        git("remote", "add", "origin", str(origin), cwd=candidate)
        return candidate, origin, records

    @staticmethod
    def _bootstrap(directory: str, records: str) -> subprocess.CompletedProcess[str]:
        return run_generate(
            "bootstrap",
            "--records",
            records,
            "--repository",
            "acme/billing-service",
            env={**isolated_git_config(directory), **COMMIT_IDENTITY},
        )

    @staticmethod
    def _unborn(candidate: Path) -> bool:
        verified = git(
            "rev-parse", "--verify", "-q", "main", cwd=candidate, check=False
        )
        return verified.returncode == 1

    def test_the_remote_default_branch_is_a_parentless_empty_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, origin, records = self._candidate_with_origin(directory)

            result = self._bootstrap(directory, records)

            self.assertEqual(result.returncode, 0, result.stderr)
            root = git_output("rev-parse", "refs/heads/main", cwd=origin)
            # A parentless commit lists only itself.
            self.assertEqual(
                git_output("rev-list", "--parents", "-n", "1", root, cwd=origin), root
            )
            empty_tree = git_output(
                "hash-object", "-t", "tree", "/dev/null", cwd=origin
            )
            self.assertEqual(
                git_output("rev-parse", f"{root}^{{tree}}", cwd=origin), empty_tree
            )
            self.assertEqual(git_output("rev-parse", "main", cwd=candidate), root)
            record = json.loads(Path(f"{records}.bootstrap.json").read_text())
            self.assertEqual(record["root"], root)
            self.assertEqual(record["default_branch"], "main")
            self.assertEqual(record["repository"], "acme/billing-service")
            self.assertEqual(json.loads(result.stdout), record)

    def test_a_rerun_once_the_branch_exists_refuses_and_pushes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _candidate, origin, records = self._candidate_with_origin(directory)
            first = self._bootstrap(directory, records)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = git_output("rev-parse", "refs/heads/main", cwd=origin)

            second = self._bootstrap(directory, records)

            self.assertEqual(second.returncode, 2)
            self.assertIn("already", json.loads(second.stderr)["error"])
            self.assertEqual(
                git_output("rev-parse", "refs/heads/main", cwd=origin), before
            )

    def test_a_branch_already_on_the_remote_is_refused_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, origin, records = self._candidate_with_origin(directory)
            # Someone else's history, already on the remote's default branch.
            other = Path(directory) / "other"
            git("clone", "-q", str(origin), str(other), cwd=directory)
            git("commit", "-q", "--allow-empty", "-m", "chore: theirs", cwd=other)
            git("push", "-q", "origin", "HEAD:main", cwd=other)
            before = git_output("rev-parse", "refs/heads/main", cwd=origin)

            result = self._bootstrap(directory, records)

            self.assertEqual(result.returncode, 2)
            self.assertIn("already", json.loads(result.stderr)["error"])
            self.assertEqual(
                git_output("rev-parse", "refs/heads/main", cwd=origin), before
            )
            self.assertTrue(self._unborn(candidate))

    def test_a_rerun_after_a_failed_push_pushes_the_same_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, origin, records = self._candidate_with_origin(directory)
            # The remote answers the read and refuses the push once.
            refusing = origin / "hooks" / "pre-receive"
            refusing.write_text("#!/bin/sh\nexit 1\n")
            refusing.chmod(0o755)
            failed = self._bootstrap(directory, records)
            self.assertEqual(failed.returncode, 2)
            root = git_output("rev-parse", "main", cwd=candidate)
            refusing.unlink()

            result = self._bootstrap(directory, records)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                git_output("rev-parse", "refs/heads/main", cwd=origin), root
            )
            self.assertEqual(json.loads(result.stdout)["root"], root)

    def test_a_candidate_branch_with_content_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, origin, records = self._candidate_with_origin(directory)
            (candidate / "README.md").write_text("content\n")
            git("add", "README.md", cwd=candidate)
            git("commit", "-q", "-m", "docs: readme", cwd=candidate)

            result = self._bootstrap(directory, records)

            self.assertEqual(result.returncode, 2)
            self.assertIn("already", json.loads(result.stderr)["error"])
            self.assertEqual(git_output("for-each-ref", cwd=origin), "")

    def test_a_candidate_with_no_remote_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, records = materialized_candidate(directory)

            result = self._bootstrap(directory, records)

            self.assertEqual(result.returncode, 2)
            self.assertIn("origin", json.loads(result.stderr)["error"])
            self.assertTrue(self._unborn(candidate))


LABELS = "repos/acme/billing-service/labels"
# The sixteen roles, then the map label and the four ticket types.
DEFAULT_LABELS = [
    "bug",
    "enhancement",
    "documentation",
    "perf",
    "refactor",
    "style",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
    "needs-triage",
    "needs-info",
    "ready-for-agent",
    "ready-for-human",
    "wontfix",
    "wayfinder:map",
    "wayfinder:research",
    "wayfinder:prototype",
    "wayfinder:grilling",
    "wayfinder:task",
]
ANSWERED = {"stdout": "{}"}


def listed(*names: str) -> dict[str, object]:
    return {
        "args": ["api", "--paginate", LABELS],
        "stdout": json.dumps([{"name": name} for name in names]),
    }


def sent(directory: str, method: str) -> list[list[str]]:
    return [call for call in gh_calls(directory) if call[1:3] == ["-X", method]]


class LabelsTests(unittest.TestCase):
    """Step 6: the sixteen roles and the wayfinder labels, created where missing."""

    @staticmethod
    def _labels(records: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return run_generate(
            "labels",
            "--records",
            records,
            "--repository",
            "acme/billing-service",
            env=env,
        )

    def test_one_create_per_missing_label_and_none_for_existing_ones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _candidate, records = materialized_candidate(directory)
            # What GitHub ships on a new repository.
            shipped = ("bug", "enhancement", "documentation", "wontfix")
            env = stub_gh(
                directory,
                [listed(*shipped), {"args": ["api", "-X", "POST", LABELS], **ANSWERED}],
            )

            result = self._labels(records, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            missing = [name for name in DEFAULT_LABELS if name not in shipped]
            self.assertEqual(
                sent(directory, "POST"),
                [
                    ["api", "-X", "POST", LABELS, "-f", f"name={name}"]
                    for name in missing
                ],
            )
            self.assertEqual(sent(directory, "PATCH"), [])
            record = json.loads(Path(f"{records}.labels.json").read_text())
            self.assertEqual(record["labels"], DEFAULT_LABELS)
            self.assertEqual(record["created"], missing)
            self.assertEqual(record["existing"], list(shipped))
            self.assertEqual(record["renamed"], [])
            self.assertEqual(json.loads(result.stdout), record)

    def test_a_case_variant_is_renamed_to_the_default_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _candidate, records = materialized_candidate(directory)
            env = stub_gh(
                directory,
                [
                    listed(*DEFAULT_LABELS[:-1], "Wayfinder:Task"),
                    {
                        "args": ["api", "-X", "PATCH", f"{LABELS}/Wayfinder%3ATask"],
                        **ANSWERED,
                    },
                ],
            )

            result = self._labels(records, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sent(directory, "POST"), [])
            self.assertEqual(
                json.loads(result.stdout)["renamed"],
                [{"from": "Wayfinder:Task", "to": "wayfinder:task"}],
            )

    def test_a_triage_label_departure_is_created_and_nothing_renamed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, records = materialized_candidate(directory)
            features = {"triage_labels": {"bug": "kind/bug"}}
            (candidate / ".repo-template.json").write_text(
                json.dumps({"generation": {"features": features}})
            )
            env = stub_gh(
                directory,
                [
                    listed(*DEFAULT_LABELS[1:-1], "Wayfinder:Task"),
                    {"args": ["api", "-X", "POST", LABELS], **ANSWERED},
                ],
            )

            result = self._labels(records, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                sent(directory, "POST"),
                [["api", "-X", "POST", LABELS, "-f", "name=kind/bug"]],
            )
            self.assertEqual(sent(directory, "PATCH"), [])
            labels = json.loads(result.stdout)["labels"]
            self.assertEqual(labels[0], "kind/bug")
            self.assertNotIn("bug", labels)

    def test_a_refused_create_fails_naming_what_landed_before_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _candidate, records = materialized_candidate(directory)
            refused = ["api", "-X", "POST", LABELS, "-f", "name=wayfinder:task"]
            env = stub_gh(
                directory,
                [
                    listed(*DEFAULT_LABELS[:-2]),
                    {"args": ["api", "-X", "POST", LABELS], **ANSWERED},
                    {"args": refused, **FORBIDDEN},
                ],
            )

            result = self._labels(records, env)

            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)["error"]
            self.assertIn("wayfinder:task", error)
            self.assertIn("wayfinder:grilling", error)
            self.assertFalse(Path(f"{records}.labels.json").exists())


class FilelistTests(unittest.TestCase):
    """Step 10: every path accounted for, and the copies proved copies."""

    def _candidate(self, directory: str) -> tuple[dict[str, str], Path, dict[str, str]]:
        """A candidate personalized as step 8 leaves it, staged as step 9 does.

        The payload gains an ignore file and the `.env` it ignores, as the real
        payload ships, so the ignored-on-disk account has something to find.
        """
        fixture = generation_fixture(directory)
        env = {**isolated_git_config(directory), **COMMIT_IDENTITY}
        template = Path(fixture["template_repo"])
        payload = template / fixture["subtree"]
        (payload / ".gitignore").write_text(".env\n")
        (payload / ".env").write_text("TOKEN=\n")
        git("add", "-f", "-A", cwd=template)
        git("commit", "-q", "-m", "chore: ignore", cwd=template)
        fixture["target_commit"] = git_output("rev-parse", "HEAD", cwd=template)
        fixture["records"] = str(
            template / "tmp" / f"billing-service.{fixture['target_commit'][:12]}"
        )
        made = run_generate(
            "materialize",
            "--records",
            fixture["records"],
            "--target",
            fixture["target_commit"],
            "--subtree",
            fixture["subtree"],
            "--destination-repository",
            fixture["destination_repository"],
            cwd=template,
            env=env,
        )
        self.assertEqual(made.returncode, 0, made.stderr)
        candidate = template / "tmp" / "billing-service"
        (candidate / "apps/app-name").rename(candidate / "apps/billing-api")
        shutil.copytree(candidate / "apps/billing-api", candidate / "apps/ledger")
        (candidate / "docs/adrs/0001-split-billing.md").write_text("# Split\n")
        (candidate / "docs/adrs/index.md").write_text("# Index\n")
        (candidate / "CLAUDE.md").write_text("personalized\n")
        manifest = {
            "schema_version": 1,
            "template": {
                "repository": "possiblyneal/template",
                "subtree": fixture["subtree"],
                "commit": fixture["target_commit"],
            },
            "destination": {
                "repository": fixture["destination_repository"],
                "default_branch": "main",
            },
            "generation": {"applications": ["billing-api", "ledger"]},
            "ownership": [{"path": "**", "mode": "managed"}],
        }
        (candidate / ".repo-template.json").write_text(json.dumps(manifest) + "\n")
        git("add", "-A", cwd=candidate)
        return fixture, candidate, env

    def _filelist(
        self, fixture: dict[str, str], candidate: Path, env: dict[str, str]
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = run_generate(
            "filelist",
            "--records",
            fixture["records"],
            "--tree",
            str(candidate),
            "--commit",
            fixture["target_commit"],
            cwd=fixture["template_repo"],
            env=env,
        )
        record = Path(f"{fixture['records']}.filelist.json")
        self.assertTrue(record.is_file(), result.stderr)
        return result, json.loads(record.read_text())

    def test_a_faithful_candidate_passes_with_every_path_accounted_for(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, candidate, env = self._candidate(directory)

            result, record = self._filelist(fixture, candidate, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(record["ok"])
            self.assertEqual(record["missing"], [])
            self.assertEqual(record["strays"], [])
            self.assertEqual(record["ignored_tracked"], [])
            self.assertEqual(record["ignored_present"], [".env"])
            self.assertEqual(
                record["additions"],
                [
                    ".repo-template.json",
                    "apps/ledger/.unit.json",
                    "apps/ledger/src/.gitkeep",
                    "docs/adrs/0001-split-billing.md",
                    "docs/adrs/index.md",
                ],
            )
            # Every copy is the payload's blob; what step 8 wrote is authored.
            copy = record["copy"]
            assert isinstance(copy, dict)
            self.assertEqual(
                copy["authored"],
                [
                    ".repo-template.json",
                    "CLAUDE.md",
                    "apps/billing-api/.unit.json",
                    "apps/billing-api/src/.gitkeep",
                    "apps/ledger/.unit.json",
                    "apps/ledger/src/.gitkeep",
                    "docs/adrs/0001-split-billing.md",
                    "docs/adrs/index.md",
                ],
            )
            # The ignored .env is proved against disk, inside the one count.
            tracked = git_output("ls-files", cwd=candidate).splitlines()
            self.assertEqual(copy["total"], len(tracked) + 1)
            self.assertEqual(copy["identical"], copy["total"] - 8)
            self.assertEqual(json.loads(result.stdout), record)

    def test_a_deleted_payload_file_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, candidate, env = self._candidate(directory)
            git("rm", "-qf", "scripts/legacy", cwd=candidate)

            result, record = self._filelist(fixture, candidate, env)

            self.assertEqual(result.returncode, 1)
            self.assertFalse(record["ok"])
            self.assertEqual(record["missing"], ["scripts/legacy"])

    def test_a_stray_file_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, candidate, env = self._candidate(directory)
            (candidate / "notes.txt").write_text("scratch\n")
            git("add", "notes.txt", cwd=candidate)

            result, record = self._filelist(fixture, candidate, env)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(record["strays"], ["notes.txt"])
            self.assertEqual(record["missing"], [])

    def test_a_force_added_ignored_path_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, candidate, env = self._candidate(directory)
            git("add", "-f", ".env", cwd=candidate)

            result, record = self._filelist(fixture, candidate, env)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(record["ignored_tracked"], [".env"])
            self.assertEqual(record["missing"], [])
            self.assertEqual(record["strays"], [])


class HooksTests(unittest.TestCase):
    """Step 9: the candidate's hooks, installed by retrofit's recipe and resolved."""

    def _candidate(self, directory: str, payload: Path) -> tuple[Path, dict[str, str]]:
        """A fresh candidate holding `payload`, under an isolated global config."""
        config = Path(directory) / "gitconfig"
        config.write_text("")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(config), **COMMIT_IDENTITY}
        candidate = Path(directory) / "tmp" / "billing-service"
        shutil.copytree(payload, candidate)
        git("init", "-q", "-b", "main", cwd=candidate)
        return candidate, env

    def _hooks(
        self, candidate: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return run_generate(
            "hooks",
            "--records",
            str(candidate.parent / "billing-service.0123456789ab"),
            "--tree",
            str(candidate),
            cwd=candidate.parent,
            env=env,
        )

    def test_installs_every_configured_type_where_git_will_consult_it(self) -> None:
        reason = hook_environments_unavailable()
        if reason:
            self.skipTest(reason)
        with tempfile.TemporaryDirectory() as directory:
            candidate, env = self._candidate(directory, PAYLOAD)

            result = self._hooks(candidate, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout)
            self.assertTrue(record["ok"])
            self.assertEqual(record["findings"], [])
            hooks = candidate / ".git/hooks"
            self.assertEqual(record["hooks_path"], str(hooks))
            self.assertIn("pre-commit", record["hook_types"])
            for kind in record["hook_types"]:
                self.assertIn(
                    "File generated by pre-commit", (hooks / kind).read_text()
                )
            self.assertEqual(
                git_output("config", "--local", "core.hooksPath", cwd=candidate),
                str(hooks),
            )
            resolved = git_output(
                "rev-parse",
                "--path-format=absolute",
                "--git-path",
                "hooks",
                cwd=candidate,
            )
            self.assertEqual(resolved, str(hooks))
            saved = candidate.parent / "billing-service.0123456789ab.hooks.json"
            self.assertEqual(json.loads(saved.read_text()), record)

    def test_a_payload_without_a_hook_config_installs_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "payload"
            empty.mkdir()
            (empty / "CLAUDE.md").write_text("payload\n")
            candidate, env = self._candidate(directory, empty)

            result = self._hooks(candidate, env)

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout)
            self.assertEqual(record["outcome"], "not-applicable")
            unset = git(
                "config", "--local", "core.hooksPath", cwd=candidate, check=False
            )
            self.assertEqual(unset.returncode, 1)


class ManifestTests(unittest.TestCase):
    """Step 8: `.repo-template.json` from the canonical ownership list."""

    def _fixture(self, directory: str) -> dict[str, str]:
        """A materialized candidate whose template carries the real ownership list."""
        fixture = generation_fixture(directory)
        template = Path(fixture["template_repo"])
        (template / "ownership.json").write_text(OWNERSHIP.read_text())
        git("add", "-A", cwd=template)
        git("commit", "-q", "-m", "chore: ownership", cwd=template)
        fixture["target_commit"] = git_output("rev-parse", "HEAD", cwd=template)
        fixture["records"] = str(
            template / "tmp" / f"billing-service.{fixture['target_commit'][:12]}"
        )
        materialized = self._run(
            fixture,
            "materialize",
            "--target",
            fixture["target_commit"],
            "--subtree",
            fixture["subtree"],
            "--destination-repository",
            fixture["destination_repository"],
            env=isolated_git_config(directory),
        )
        self.assertEqual(materialized.returncode, 0, materialized.stderr)
        fixture["candidate"] = str(template / "tmp" / "billing-service")
        return fixture

    @staticmethod
    def _run(
        fixture: dict[str, str], *arguments: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        command, *rest = arguments
        return subprocess.run(
            [
                "python3",
                str(MODULE_PATH),
                command,
                "--records",
                fixture["records"],
                *rest,
            ],
            cwd=fixture["template_repo"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _manifest(
        self, fixture: dict[str, str], *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return self._run(
            fixture,
            "manifest",
            "--repository",
            fixture["destination_repository"],
            "--commit",
            fixture["target_commit"],
            "--subtree",
            fixture["subtree"],
            *extra,
        )

    def test_the_manifest_is_valid_staged_and_reaches_every_payload_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)

            result = self._manifest(
                fixture,
                "--application",
                "billing-api",
                "--application",
                "billing-worker",
                "--feature",
                "codeql=omitted-by-choice",
                "--feature",
                "prs_are_requests=true",
                "--feature",
                "triage_labels.bug=defect",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            candidate = Path(fixture["candidate"])
            path = candidate / ".repo-template.json"
            manifest, rules, _ = preflight.validate_manifest(path)
            self.assertEqual(
                manifest["template"],
                {
                    "repository": str(Path(fixture["template_repo"]).resolve()),
                    "subtree": fixture["subtree"],
                    "commit": fixture["target_commit"],
                },
            )
            self.assertEqual(
                manifest["destination"],
                {"repository": "acme/billing-service", "default_branch": "main"},
            )
            self.assertEqual(
                manifest["generation"],
                {
                    "applications": ["billing-api", "billing-worker"],
                    "features": {
                        "codeql": "omitted-by-choice",
                        "prs_are_requests": True,
                        "triage_labels": {"bug": "defect"},
                    },
                },
            )
            self.assertEqual(
                manifest["ownership"], json.loads(OWNERSHIP.read_text())["ownership"]
            )
            payload = preflight.tree_paths(
                Path(fixture["template_repo"]),
                fixture["target_commit"],
                fixture["subtree"],
            )
            unreached = [
                payload_path
                for payload_path in payload
                if preflight.classify_path(payload_path, rules)[1] is None
            ]
            self.assertEqual(unreached, [])
            self.assertEqual(
                git_output("diff", "--cached", "--name-only", cwd=candidate),
                ".repo-template.json",
            )
            record = json.loads(Path(f"{fixture['records']}.manifest.json").read_text())
            self.assertEqual(record["manifest"], str(path))
            self.assertTrue(record["staged"])
            self.assertEqual(json.loads(result.stdout), record)

    def test_what_step_6_recorded_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            path = Path(fixture["candidate"]) / ".repo-template.json"
            path.write_text(
                json.dumps(
                    {"generation": {"features": {"issue_tracker": "Linear, team BIL"}}}
                )
            )

            result = self._manifest(fixture, "--feature", "codeql=omitted-by-choice")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(path.read_text())["generation"]["features"],
                {"issue_tracker": "Linear, team BIL", "codeql": "omitted-by-choice"},
            )

    def test_a_role_label_joins_the_roles_step_6_respelled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            path = Path(fixture["candidate"]) / ".repo-template.json"
            path.write_text(
                json.dumps(
                    {"generation": {"features": {"triage_labels": {"bug": "defect"}}}}
                )
            )

            result = self._manifest(fixture, "--feature", "triage_labels.feat=feature")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(path.read_text())["generation"]["features"],
                {"triage_labels": {"bug": "defect", "feat": "feature"}},
            )

    def test_a_feature_value_the_flows_do_not_read_is_refused_unwritten(self) -> None:
        for feature in ("codeql=dropped", "prs_are_requests=yes", "codeql", "=x"):
            with (
                self.subTest(feature=feature),
                tempfile.TemporaryDirectory() as directory,
            ):
                fixture = self._fixture(directory)

                result = self._manifest(fixture, "--feature", feature)

                self.assertEqual(result.returncode, 2)
                self.assertIn("--feature", json.loads(result.stderr)["error"])
                self.assertFalse(
                    (Path(fixture["candidate"]) / ".repo-template.json").exists()
                )
                self.assertFalse(Path(f"{fixture['records']}.manifest.json").exists())

    def test_a_payload_path_no_rule_reaches_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            template = Path(fixture["template_repo"])
            (template / fixture["subtree"] / "STRAY.md").write_text("stray\n")
            # Only the stray: tmp/ now holds the candidate, a repository of its own.
            git("add", f"{fixture['subtree']}/STRAY.md", cwd=template)
            git("commit", "-q", "-m", "chore: stray", cwd=template)
            fixture["target_commit"] = git_output("rev-parse", "HEAD", cwd=template)

            result = self._manifest(fixture)

            self.assertEqual(result.returncode, 2)
            self.assertIn("STRAY.md", json.loads(result.stderr)["error"])
            self.assertFalse(
                (Path(fixture["candidate"]) / ".repo-template.json").exists()
            )


REPO = "repos/acme/billing-service"
IDENTITY = {
    "GIT_AUTHOR_NAME": "Generate Test",
    "GIT_AUTHOR_EMAIL": "generate@example.invalid",
    "GIT_COMMITTER_NAME": "Generate Test",
    "GIT_COMMITTER_EMAIL": "generate@example.invalid",
}
UNPROCESSABLE = {
    "stdout": json.dumps(
        {"message": "Secret scanning is not available", "status": "422"}
    ),
    "status": 1,
}
# The rejection GitHub's receive side prints for a push a ruleset refuses.
GH013_HOOK = """#!/bin/sh
echo "remote: error: GH013: Repository rule violations found for refs/heads/main." >&2
exit 1
"""


def settings_responses(
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """A new repository with every setting off, each write answered 2xx."""
    repo = {
        "visibility": "public",
        "permissions": {"admin": True},
        "allow_merge_commit": False,
        "allow_squash_merge": True,
        "allow_rebase_merge": True,
        "delete_branch_on_merge": False,
        "security_and_analysis": {
            "secret_scanning_push_protection": {"status": "disabled"}
        },
    }
    responses: dict[str, dict[str, object]] = {
        "read": {"args": ["api", REPO], "stdout": json.dumps(repo)},
        "alerts-read": {"args": ["api", f"{REPO}/vulnerability-alerts"], **NOT_FOUND},
        "updates-read": {
            "args": ["api", f"{REPO}/automated-security-fixes"],
            "stdout": json.dumps({"enabled": False, "paused": False}),
        },
        "merge-settings": {"args": ["api", "-X", "PATCH", REPO, "-F"], "stdout": "{}"},
        "push-protection": {"args": ["api", "-X", "PATCH", REPO, "-f"], "stdout": "{}"},
        "toggles": {"args": ["api", "-X", "PUT"], "stdout": ""},
        "ruleset": {
            "args": ["api", "-X", "POST", f"{REPO}/rulesets"],
            "stdout": json.dumps({"id": 42}),
        },
    }
    for name, answer in (overrides or {}).items():
        responses[name] = {"args": responses[name]["args"], **answer}
    return list(responses.values())


def required_contexts(workflows: Path) -> list[str]:
    """The job `name:` of every job in ci.yml and security.yml, and of
    codeql.yml's `scanning`: the contexts every pull request reports."""
    contexts: list[str] = []
    for workflow, only in (
        ("ci.yml", None),
        ("security.yml", None),
        ("codeql.yml", "scanning"),
    ):
        job = None
        in_jobs = False
        for line in (workflows / workflow).read_text().splitlines():
            if line and not line.startswith(" "):
                in_jobs = line.rstrip() == "jobs:"
                continue
            started = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line)
            if in_jobs and started:
                job = started.group(1)
                continue
            named = re.fullmatch(r"    name:\s*(.+?)\s*", line)
            if in_jobs and named and only in (None, job):
                contexts.append(named.group(1).strip("'\""))
    return contexts


def ruleset_contexts(body: dict) -> list[str]:
    return [
        check["context"]
        for rule in body["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    ]


class RulesetTests(unittest.TestCase):
    """The checked-in ruleset requires what the payload's workflows report."""

    def test_the_ruleset_requires_the_payload_job_names(self) -> None:
        body = json.loads(RULESET.read_text())

        self.assertEqual(
            ruleset_contexts(body), ["CI", "Security", "Code scanning enabled"]
        )
        self.assertEqual(ruleset_contexts(body), required_contexts(WORKFLOWS))

    def test_a_renamed_job_changes_the_required_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflows = Path(directory) / "workflows"
            shutil.copytree(WORKFLOWS, workflows)
            ci = workflows / "ci.yml"
            ci.write_text(ci.read_text().replace("    name: CI\n", "    name: Build\n"))

            self.assertEqual(
                required_contexts(workflows),
                ["Build", "Security", "Code scanning enabled"],
            )
            self.assertNotEqual(
                required_contexts(workflows),
                ruleset_contexts(json.loads(RULESET.read_text())),
            )


class SettingsTests(unittest.TestCase):
    """Step 5: the settings, the ruleset, and the probe that proves it binds."""

    def _candidate(self, directory: str, refuses: bool) -> tuple[Path, Path, str]:
        """A materialized candidate whose origin holds step 4's empty root.

        The origin refuses a direct push with GH013, as a binding ruleset does,
        only where `refuses` is set.
        """
        origin = Path(directory) / "origin.git"
        git("init", "-q", "--bare", "-b", "main", str(origin))
        candidate = Path(directory) / "tmp" / "billing-service"
        candidate.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=candidate)
        (candidate / "CLAUDE.md").write_text("untracked payload\n")
        empty_tree = git_output("hash-object", "-t", "tree", "/dev/null", cwd=candidate)
        root = git_output("commit-tree", empty_tree, "-m", "chore: init", cwd=candidate)
        git("update-ref", "refs/heads/main", root, cwd=candidate)
        git("remote", "add", "origin", str(origin), cwd=candidate)
        git("push", "-q", "origin", "main", cwd=candidate)
        # Installed after step 4's push, which the ruleset did not yet exist to
        # refuse; a machine without a global core.hooksPath runs it.
        if refuses:
            hook = origin / "hooks" / "pre-receive"
            hook.write_text(GH013_HOOK)
            hook.chmod(0o755)
        Path(f"{self._records(directory)}.materialize.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "candidate": str(candidate),
                    "commit": self._template(directory, RULESET.read_text()),
                    "subtree": "src/base-repo",
                }
            )
        )
        return candidate, origin, root

    @staticmethod
    def _template(directory: str, ruleset: str) -> str:
        """A template whose commit holds `ruleset` beside the payload, returning it.

        The working tree is then changed, so a settings run that read the
        checkout rather than the commit would send the wrong body.
        """
        template = Path(directory) / "template"
        (template / "src" / "base-repo").mkdir(parents=True)
        (template / "src" / "base-repo" / "README.md").write_text("payload\n")
        (template / "src" / "ruleset.json").write_text(ruleset)
        git("init", "-q", "-b", "main", cwd=template)
        git("add", "-A", cwd=template)
        git("commit", "-q", "-m", "chore: template", cwd=template)
        (template / "src" / "ruleset.json").write_text("{}")
        return git_output("rev-parse", "HEAD", cwd=template)

    @staticmethod
    def _records(directory: str) -> Path:
        return Path(directory) / "tmp" / "billing-service.0123456789ab"

    def _settings(
        self, directory: str, responses: list[dict[str, object]]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(MODULE_PATH),
                "settings",
                "--records",
                str(self._records(directory)),
                "--repository",
                "acme/billing-service",
                "--template-repo",
                str(Path(directory) / "template"),
            ],
            cwd=directory,
            # The isolated config keeps a global core.hooksPath from replacing
            # the origin's pre-receive hook.
            env={
                **stub_gh(directory, responses),
                **IDENTITY,
                "GIT_CONFIG_GLOBAL": isolated_git_config(directory)[
                    "GIT_CONFIG_GLOBAL"
                ],
            },
            text=True,
            capture_output=True,
            check=False,
        )

    def _record(self, directory: str) -> dict:
        return json.loads(Path(f"{self._records(directory)}.settings.json").read_text())

    def test_every_write_lands_and_the_refused_probe_leaves_no_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, origin, root = self._candidate(directory, refuses=True)

            result = self._settings(directory, settings_responses())

            self.assertEqual(result.returncode, 0, result.stderr)
            record = self._record(directory)
            self.assertEqual(
                record["writes"],
                {
                    "merge-settings": "done",
                    "dependabot-alerts": "done",
                    "security-updates": "done",
                    "push-protection": "done",
                    "ruleset": "done",
                },
            )
            writes = [call for call in gh_calls(directory) if "-X" in call]
            self.assertEqual(
                [call[2:4] for call in writes],
                [
                    ["PATCH", REPO],
                    ["PUT", f"{REPO}/vulnerability-alerts"],
                    ["PUT", f"{REPO}/automated-security-fixes"],
                    ["PATCH", REPO],
                    ["POST", f"{REPO}/rulesets"],
                ],
            )
            sent = writes[-1][writes[-1].index("--input") + 1]
            body = json.loads(Path(sent).read_text())
            self.assertEqual(
                ruleset_contexts(body), ["CI", "Security", "Code scanning enabled"]
            )
            self.assertEqual(record["required_contexts"], ruleset_contexts(body))
            self.assertEqual(record["probe"]["outcome"], "refused")
            self.assertIn("GH013", record["probe"]["detail"])
            self.assertEqual(git_output("rev-parse", "main", cwd=origin), root)
            self.assertEqual(git_output("rev-parse", "main", cwd=candidate), root)
            self.assertTrue((candidate / "CLAUDE.md").exists())
            self.assertEqual(json.loads(result.stdout), record)

    def test_a_rerun_probes_the_ruleset_an_earlier_run_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, origin, root = self._candidate(directory, refuses=True)
            Path(f"{self._records(directory)}.writes.json").write_text(
                json.dumps(
                    [
                        {
                            "write": "ruleset",
                            "before": None,
                            "after": {"id": 42},
                            "reverse_command": [],
                        }
                    ]
                )
            )

            result = self._settings(directory, settings_responses())

            self.assertEqual(result.returncode, 0, result.stderr)
            record = self._record(directory)
            self.assertEqual(record["writes"]["ruleset"], "logged")
            self.assertEqual(record["probe"]["outcome"], "refused")
            self.assertEqual(git_output("rev-parse", "main", cwd=origin), root)

    def test_a_plan_refusal_is_not_offered_and_nothing_is_probed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, origin, root = self._candidate(directory, refuses=False)
            responses = settings_responses(
                {"push-protection": UNPROCESSABLE, "ruleset": FORBIDDEN}
            )

            result = self._settings(directory, responses)

            self.assertEqual(result.returncode, 0, result.stderr)
            record = self._record(directory)
            self.assertEqual(record["writes"]["merge-settings"], "done")
            self.assertEqual(record["writes"]["push-protection"], "not offered")
            self.assertEqual(record["writes"]["ruleset"], "not offered")
            self.assertIsNone(record["probe"])
            self.assertEqual(git_output("rev-parse", "main", cwd=origin), root)

    def test_an_upgrade_message_on_the_ruleset_is_not_offered_either(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, origin, root = self._candidate(directory, refuses=False)

            result = self._settings(directory, settings_responses({"ruleset": UPGRADE}))

            self.assertEqual(result.returncode, 0, result.stderr)
            record = self._record(directory)
            self.assertEqual(record["writes"]["ruleset"], "not offered")
            self.assertIsNone(record["probe"])
            self.assertEqual(git_output("rev-parse", "main", cwd=origin), root)

    def test_an_accepted_probe_stops_and_names_the_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, origin, root = self._candidate(directory, refuses=False)

            result = self._settings(directory, settings_responses())

            self.assertNotEqual(result.returncode, 0)
            landed = git_output("rev-parse", "main", cwd=origin)
            self.assertNotEqual(landed, root)
            self.assertIn(landed, json.loads(result.stderr)["error"])


SUMMARY_PASS = "lint               pass             ruff\ntest               pass             pytest\n"
AUTHORED = [".repo-template.json", "CLAUDE.md", "apps/billing-api/.unit.json"]
# One record per step that writes one, as a finished generate leaves them.
RECORDS: dict[str, dict[str, object]] = {
    "materialize": {
        "ok": True,
        "default_branch": "main",
        "head": "refs/heads/main",
        "payload_paths": 40,
    },
    "bootstrap": {"ok": True, "default_branch": "main", "root": "a" * 40},
    "settings": {
        "ok": True,
        "writes": {
            "merge-settings": "done",
            "dependabot-alerts": "done",
            "security-updates": "done",
            "push-protection": "not offered",
            "ruleset": "done",
        },
        "reasons": {"push-protection": "Upgrade to GitHub Pro (HTTP 403)"},
        "required_contexts": ["CI", "Security", "Code scanning enabled"],
        "probe": {"commit": "b" * 40, "outcome": "refused", "detail": "GH013"},
    },
    "labels": {
        "ok": True,
        "created": ["perf", "wayfinder:map"],
        "renamed": [{"from": "Bug", "to": "bug"}],
        "existing": ["bug"],
        "kept": [],
    },
    "manifest": {"ok": True, "features": {}, "applications": ["billing-api"]},
    "hooks": {
        "ok": True,
        "outcome": "installed",
        "hook_types": ["pre-commit", "commit-msg"],
        "hooks_path": "/x/tmp/billing-service/.git/hooks",
        "prior_hooks": {"path": "/x/hooks", "scope": "global"},
        "moved_aside": [],
        "chained": [],
        "findings": [],
    },
    "filelist": {
        "ok": True,
        "payload_paths": 40,
        "tracked_paths": 40,
        "missing": [],
        "additions": [
            ".repo-template.json",
            "docs/adrs/0001-write-billing-api-in-python.md",
            "docs/adrs/index.md",
        ],
        "strays": [],
        "ignored_present": [".env"],
        "ignored_tracked": [],
        "copy": {"identical": 38, "total": 41, "authored": AUTHORED},
    },
    "orca": {
        "ok": True,
        "repository": "/home/operator/code/billing-service",
        "registered": "added",
        "status": "set",
        "icon": {"type": "emoji", "emoji": "\U0001f4b3"},
    },
    "publish": {
        "ok": True,
        "pull_request": "https://github.com/acme/billing-service/pull/1",
    },
}
PR_TEMPLATE = PAYLOAD / ".github" / "PULL_REQUEST_TEMPLATE.md"


class RenderTests(unittest.TestCase):
    """Steps 11 and 14: the body and the report, rendered from the records."""

    def _records(self, directory: str, *, without: str = "") -> tuple[dict, str]:
        """A finished generate's records, against a template whose payload has
        one workflow a pull request triggers and one it never does."""
        fixture = generation_fixture(directory)
        template = Path(fixture["template_repo"])
        workflows = template / fixture["subtree"] / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("on:\n  pull_request:\n")
        (workflows / "release.yml").write_text("on:\n  push:\n    tags: ['v*']\n")
        git("add", "-A", cwd=template)
        git("commit", "-q", "-m", "chore: workflows", cwd=template)
        commit = git_output("rev-parse", "HEAD", cwd=template)
        records = str(template / "tmp" / f"billing-service.{commit[:12]}")
        Path(records).parent.mkdir(exist_ok=True)
        candidate = template / "tmp" / "billing-service"
        documents = json.loads(json.dumps(RECORDS))
        documents["materialize"] |= {"candidate": str(candidate), "commit": commit}
        documents["filelist"]["template"] = {
            "subtree": fixture["subtree"],
            "commit": commit,
        }
        for name, document in documents.items():
            if name != without:
                Path(f"{records}.{name}.json").write_text(json.dumps(document))
        if without != "check":
            Path(f"{records}.check.txt").write_text(SUMMARY_PASS)
        return fixture, records

    def test_a_full_record_set_leaves_slots_only_for_judgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, records = self._records(directory)

            result = run_generate(
                "report",
                "--records",
                records,
                "--repository",
                "acme/billing-service",
                "--visibility",
                "private",
                cwd=fixture["template_repo"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            report = Path(output["path"]).read_text()
            self.assertEqual(output["path"], f"{records}.report.md")
            self.assertEqual(
                sorted(slot.split(":")[0] for slot in output["slots"]),
                ["addons", "boundaries", "default-branch", "first-manifest", "tickets"],
            )
            self.assertEqual(report.count("[[FILL:"), len(output["slots"]))
            commit = json.loads(Path(f"{records}.materialize.json").read_text())[
                "commit"
            ]
            for line in (
                "- Status: finished",
                "- Operation: generate",
                "- Pull request: https://github.com/acme/billing-service/pull/1",
                f"- Template: not previously generated -> {commit}",
                "- Destination: acme/billing-service",
                (
                    "- Orca: /home/operator/code/billing-service registered, "
                    "icon \U0001f4b3 set"
                ),
                "- ADRs written: docs/adrs/0001-write-billing-api-in-python.md",
                "- Authored surface: " + ", ".join(AUTHORED),
                "- Push protection: unavailable (Upgrade to GitHub Pro (HTTP 403))",
                (
                    "- Branch ruleset: enabled; probe refused with GH013; requires "
                    "CI, Security, Code scanning enabled"
                ),
                (
                    "- Issue tracker: GitHub Issues via gh (the default); labels: "
                    "created (perf, wayfinder:map); renamed to the spelling in force "
                    "(Bug -> bug; label search is case-sensitive, so anything pinned "
                    "to the old string stops matching); already present (bug)"
                ),
                "- `scripts/check`: pass",
                (
                    "- Copied paths byte-identical to their source: 38/41; the rest are "
                    "the authored surface, under File list"
                ),
                (
                    "- Workflows the pull-request event never ran: "
                    ".github/workflows/release.yml"
                ),
                "### Pending action",
                "Work acme/billing-service in /home/operator/code/billing-service.",
            ):
                self.assertIn(line, report)
            self.assertIn("skipped CodeQL detect and analyze legs", report)
            for dropped in ("### Reconciliation", "Drift", "### Resumption"):
                self.assertNotIn(dropped, report)

    def test_a_missing_record_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, records = self._records(directory, without="hooks")

            result = run_generate(
                "report",
                "--records",
                records,
                "--repository",
                "acme/billing-service",
                "--visibility",
                "public",
                cwd=fixture["template_repo"],
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn(f"{records}.hooks.json", json.loads(result.stderr)["error"])
            self.assertFalse(Path(f"{records}.report.md").exists())

    def test_the_body_has_one_section_per_template_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, records = self._records(directory)
            tree = Path(directory) / "candidate"
            (tree / ".github").mkdir(parents=True)
            shutil.copy(PR_TEMPLATE, tree / ".github" / "PULL_REQUEST_TEMPLATE.md")

            result = run_generate(
                "pr-body",
                "--records",
                records,
                "--tree",
                str(tree),
                cwd=fixture["template_repo"],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["path"], f"{records}.pr-body.md")
            body = Path(output["path"]).read_text()
            headings = [
                line
                for line in PR_TEMPLATE.read_text().splitlines()
                if line.startswith("## ")
            ]
            self.assertEqual(
                [line for line in body.splitlines() if line.startswith("## ")],
                headings,
            )
            self.assertEqual(
                [slot.split(":")[0] for slot in output["slots"]], ["boundaries"]
            )
            self.assertIn("- `CLAUDE.md`", body)
            self.assertIn(SUMMARY_PASS.splitlines()[0], body)

    def test_a_body_still_holding_a_slot_is_refused_at_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, records = materialized_candidate(directory)
            Path(f"{records}.pr-body.md").write_text(
                "## Decisions\n\n[[FILL: boundaries: one line per deployable]]\n"
            )

            result = run_generate(
                "publish",
                "--records",
                records,
                cwd=directory,
                env=stub_gh(directory, []),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("[[FILL:", json.loads(result.stderr)["error"])
            self.assertEqual(gh_calls(directory), [])


if __name__ == "__main__":
    unittest.main()
