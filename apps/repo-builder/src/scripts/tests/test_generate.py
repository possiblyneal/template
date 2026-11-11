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

from test_preflight import git, git_output
from test_retrofit import FORBIDDEN, NOT_FOUND, UPGRADE, gh_calls, stub_gh

MODULE_PATH = Path(__file__).parents[1] / "generate.py"
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
        if refuses:
            hook = origin / "hooks" / "pre-receive"
            hook.write_text(GH013_HOOK)
            hook.chmod(0o755)
        candidate = Path(directory) / "tmp" / "billing-service"
        candidate.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=candidate)
        (candidate / "CLAUDE.md").write_text("untracked payload\n")
        empty_tree = git_output("hash-object", "-t", "tree", "/dev/null", cwd=candidate)
        root = git_output("commit-tree", empty_tree, "-m", "chore: init", cwd=candidate)
        git("update-ref", "refs/heads/main", root, cwd=candidate)
        git("remote", "add", "origin", str(origin), cwd=candidate)
        git("push", "-q", "origin", "main", cwd=candidate)
        Path(f"{self._records(directory)}.materialize.json").write_text(
            json.dumps({"ok": True, "candidate": str(candidate)})
        )
        return candidate, origin, root

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


if __name__ == "__main__":
    unittest.main()
