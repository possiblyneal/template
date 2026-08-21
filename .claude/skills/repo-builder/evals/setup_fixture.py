#!/usr/bin/env python3
"""Create isolated Git fixtures for repo-builder evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Repo Builder Eval",
    "GIT_AUTHOR_EMAIL": "repo-builder-eval@example.invalid",
    "GIT_COMMITTER_NAME": "Repo Builder Eval",
    "GIT_COMMITTER_EMAIL": "repo-builder-eval@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def run(repo: Path, *args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=GIT_ENV,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )
    return result.stdout.strip() if capture else ""


def write(root: Path, relative: str, content: str, executable: bool = False) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def init_repo(path: Path, bare: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    args = ["init", "--initial-branch=main"]
    if bare:
        args.append("--bare")
    run(path, *args)


def commit(repo: Path, message: str) -> str:
    run(repo, "add", "-A")
    run(repo, "commit", "-m", message)
    return run(repo, "rev-parse", "HEAD", capture=True)


def template_payload(repo: Path) -> None:
    write(
        repo,
        "base-repo/AGENTS.md",
        """## Commands

- `scripts/check` — run repository checks

## Placeholders

`apps/app-name/` is a placeholder. Rename it before adding code, then delete this section.

## Child Index

This project is not yet indexed. Replace this message with the actual index.
""",
    )
    write(repo, "base-repo/apps/app-name/src/.gitkeep", "")
    write(
        repo,
        "base-repo/docs/adrs/0000-template.md",
        """---
type: Template
title: <Decision title>
status: proposed
---

# <Decision title>

Copy this file to create an ADR. Replace the placeholders in the copy.
""",
    )
    write(
        repo,
        "base-repo/docs/LESSONS.md",
        """---
type: Template
title: Repository Lessons Learned
generated: { by: "<actor>", at: "<ISO 8601 timestamp>" }
status: draft
---

<Replace the metadata and this placeholder.>

# Lessons learned

## Lessons

<Add repository lessons here.>
""",
    )
    write(
        repo,
        "base-repo/scripts/check",
        """#!/usr/bin/env bash
set -euo pipefail

echo "check v1"
""",
        executable=True,
    )
    write(
        repo,
        "base-repo/scripts/legacy",
        """#!/usr/bin/env bash
set -euo pipefail

echo "preflight ok"
""",
        executable=True,
    )


def addon_payload(repo: Path) -> None:
    write(
        repo,
        "repository-addons/README.md",
        "# [REPLACE: project name]\n\n[REPLACE: one-line tagline]\n",
    )
    write(
        repo,
        "repository-addons/CONTRIBUTORS.md",
        "<!-- ALL-CONTRIBUTORS-LIST:START -->\n<!-- ALL-CONTRIBUTORS-LIST:END -->\n",
    )
    write(
        repo,
        "repository-addons/.all-contributorsrc",
        '{\n  "projectOwner": "REPO-OWNER",\n  "projectName": "REPO-NAME"\n}\n',
    )
    index = {
        "_about": ["Fixture addon adoption index."],
        "files": {
            "README.md": {
                "slots": [
                    {
                        "token": "[REPLACE: project name]",
                        "value_key": "project-title",
                        "what": "The project name in the H1 header.",
                    }
                ],
                "reviews": [],
                "external": [],
            },
            "CONTRIBUTORS.md": {
                "slots": [],
                "reviews": [],
                "external": [
                    {
                        "step": "Install the All Contributors app on the repository.",
                        "consequence": "Without it the @allcontributors comment syntax does nothing.",
                    }
                ],
            },
            ".all-contributorsrc": {
                "slots": [
                    {"token": "REPO-OWNER", "value_key": "repo-owner", "what": "projectOwner."},
                    {"token": "REPO-NAME", "value_key": "repo-name", "what": "projectName."},
                ],
                "reviews": [],
                "external": [],
            },
        },
    }
    write(repo, "addon-adoption.json", json.dumps(index, indent=2) + "\n")


def manifest(template: Path, remote: Path, old_commit: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "template": {
            "repository": str(template.resolve()),
            "subtree": "base-repo",
            "commit": old_commit,
        },
        "destination": {
            "repository": str(remote.resolve()),
            "default_branch": "main",
        },
        "generation": {
            "application_name": "billing-api",
            "visibility": "private",
            "features": {"codeql": "omitted-by-choice"},
        },
        "ownership": [
            {"path": ".repo-template.json", "mode": "managed"},
            {"path": "scripts/**", "mode": "managed"},
            {"path": ".github/**", "mode": "managed"},
            {"path": ".claude/settings.json", "mode": "managed"},
            {"path": "apps/**", "mode": "product"},
            {"path": "docs/**", "mode": "product"},
            {"path": "libs/**", "mode": "product"},
            {"path": "tests/**", "mode": "product"},
            {"path": "tools/**", "mode": "product"},
            {"path": ".claude/hooks/**", "mode": "product"},
            {"path": ".claude/rules/**", "mode": "product"},
            {"path": ".claude/skills/**", "mode": "product"},
            {"path": ".claude/agents/**", "mode": "product"},
            {"path": ".claude/output-styles/**", "mode": "product"},
            {"path": ".claude/workflows/**", "mode": "product"},
        ],
    }


def create_destination(root: Path, template: Path, old_commit: str, conflict: bool) -> tuple[Path, Path]:
    remote = root / "destination.git"
    destination = root / "destination"
    init_repo(remote, bare=True)
    init_repo(destination)

    if conflict:
        check = """#!/usr/bin/env bash
set -euo pipefail

echo "product policy: checks are advisory during incident response"
"""
    else:
        check = """#!/usr/bin/env bash
set -euo pipefail

echo "check v1"

# Operational note: run this before every deployment.
"""

    write(destination, "scripts/check", check, executable=True)
    write(
        destination,
        "scripts/legacy",
        """#!/usr/bin/env bash
set -euo pipefail

echo "preflight ok"
""",
        executable=True,
    )
    write(destination, "apps/billing-api/src/service.py", "PRODUCT_BEHAVIOR = 'invoice customers'\n")
    write(destination, "docs/product-runbook.md", "# Product runbook\n\nPage the billing team for invoice failures.\n")
    write(
        destination,
        ".repo-template.json",
        json.dumps(manifest(template, remote, old_commit), indent=2) + "\n",
    )
    commit(destination, "Initialize generated product repository")
    run(destination, "remote", "add", "origin", str(remote.resolve()))
    run(destination, "push", "-u", "origin", "main")
    return destination, remote


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_generation(root: Path) -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    target = commit(template, "Add base repository payload")
    return {
        "scenario": "generation",
        "template_repo": str(template),
        "subtree": "base-repo",
        "target_commit": target,
        "candidate": str(root / "candidate"),
        "destination_repository": "acme/billing-service",
    }


def build_update(root: Path, scenario: str) -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    old_commit = commit(template, "Add initial base repository")

    if scenario == "unrelated":
        run(template, "checkout", "--orphan", "unrelated")
        run(template, "rm", "-rf", ".")
        write(
            template,
            "base-repo/scripts/check",
            "#!/usr/bin/env bash\nset -euo pipefail\n\necho \"unrelated template\"\n",
            executable=True,
        )
        target_commit = commit(template, "Start unrelated template history")
    elif scenario == "conflict":
        write(
            template,
            "base-repo/scripts/check",
            """#!/usr/bin/env bash
set -euo pipefail

echo "template policy: checks are always blocking"
""",
            executable=True,
        )
        target_commit = commit(template, "Make checks unconditionally blocking")
    else:
        run(template, "mv", "base-repo/scripts/legacy", "base-repo/scripts/preflight")
        write(
            template,
            "base-repo/scripts/check",
            """#!/usr/bin/env bash
set -euo pipefail

scripts/preflight
echo "check v2"
""",
            executable=True,
        )
        target_commit = commit(template, "Run preflight before repository checks")

    destination, remote = create_destination(root, template, old_commit, scenario == "conflict")
    return {
        "scenario": scenario,
        "template_repo": str(template),
        "subtree": "base-repo",
        "old_commit": old_commit,
        "target_commit": target_commit,
        "destination": str(destination),
        "destination_remote": str(remote),
        "product_hashes": {
            "apps/billing-api/src/service.py": sha256(destination / "apps/billing-api/src/service.py"),
            "docs/product-runbook.md": sha256(destination / "docs/product-runbook.md"),
        },
    }


def build_adopt(root: Path) -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    addon_payload(template)
    recorded = commit(template, "Add base repository payload and repository addons")

    destination, remote = create_destination(root, template, recorded, conflict=False)
    return {
        "scenario": "adopt",
        "template_repo": str(template),
        "subtree": "base-repo",
        "recorded_commit": recorded,
        "destination": str(destination),
        "destination_remote": str(remote),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=("generation", "clean-update", "unrelated", "conflict", "adopt"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true", help="replace an existing output directory")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        if not args.force:
            parser.error(f"output already exists: {output}; pass --force to replace it")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    try:
        if args.scenario == "generation":
            details = build_generation(output)
        elif args.scenario == "adopt":
            details = build_adopt(output)
        else:
            details = build_update(output, args.scenario)
    except subprocess.CalledProcessError as error:
        print(f"fixture setup failed: git {' '.join(error.cmd[1:])}", file=sys.stderr)
        return 1

    metadata = output / "fixture.json"
    metadata.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    print(metadata)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
