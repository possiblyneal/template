from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_preflight import git, git_output, preflight

MODULE_PATH = Path(__file__).parents[1] / "generate.py"
SETUP = MODULE_PATH.parents[1] / "evals" / "setup_fixture.py"
OWNERSHIP = (
    MODULE_PATH.parents[3] / "github-repository-template" / "src" / "ownership.json"
)


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


if __name__ == "__main__":
    unittest.main()
