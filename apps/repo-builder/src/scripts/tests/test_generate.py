from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_preflight import git, git_output
from test_retrofit import (
    COMMIT_IDENTITY,
    FORBIDDEN,
    PAYLOAD,
    gh_calls,
    hook_environments_unavailable,
    stub_gh,
)

MODULE_PATH = Path(__file__).parents[1] / "generate.py"
SETUP = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"


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


def payload_entries(template: str, commit: str, subtree: str) -> dict[str, tuple[str, str]]:
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
        return str(template / "tmp" / f"billing-service.{fixture['target_commit'][:12]}")

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
                git("rev-parse", "--verify", "-q", "HEAD", cwd=candidate, check=False)
                .returncode,
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
        verified = git("rev-parse", "--verify", "-q", "main", cwd=candidate, check=False)
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
            self.assertEqual(git_output("rev-parse", "refs/heads/main", cwd=origin), root)
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
                [["api", "-X", "POST", LABELS, "-f", f"name={name}"] for name in missing],
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

    def _candidate(
        self, directory: str
    ) -> tuple[dict[str, str], Path, dict[str, str]]:
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

    def _candidate(
        self, directory: str, payload: Path
    ) -> tuple[Path, dict[str, str]]:
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
                self.assertIn("File generated by pre-commit", (hooks / kind).read_text())
            self.assertEqual(
                git_output("config", "--local", "core.hooksPath", cwd=candidate),
                str(hooks),
            )
            resolved = git_output(
                "rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=candidate
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
            unset = git("config", "--local", "core.hooksPath", cwd=candidate, check=False)
            self.assertEqual(unset.returncode, 1)


if __name__ == "__main__":
    unittest.main()
