#!/usr/bin/env python3
"""Create isolated Git fixtures for repo-builder evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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


PAYLOAD_COMMANDS = "- `scripts/check` — run repository checks\n"


def payload_instructions(commands: str) -> str:
    """The payload's root instructions, varying only the Commands section.

    A scenario that changes the root instructions on the template's side edits
    that section, so the text around it is written once here rather than
    restated per scenario and drifting out of step with the payload.

    The Child Index sentence is copied from the payload's own skeleton at
    `apps/github-repository-template/src/base-repo/CLAUDE.md`. It is addressed
    to the destination's first session, not to a generate, so every generate
    scenario asserts it survives untouched; a fixture that told the flow to
    leave it alone would be testing wording the payload does not ship.
    """
    return f"""## Commands

{commands}
## Apps

An `apps/` entry is one deployable service.

`apps/app-name/` is a placeholder. Rename it before adding code, then delete this paragraph.

## Child Index

This project is not yet indexed. Before continuing you must scan the repository, create a `CLAUDE.md` in every child folder that is a durable boundary, and replace this message with one bullet per child `CLAUDE.md` — its path, then what that file owns.
"""


def template_payload(repo: Path) -> None:
    write(
        repo,
        "base-repo/CLAUDE.md",
        payload_instructions(PAYLOAD_COMMANDS),
    )
    write(
        repo,
        "base-repo/apps/app-name/.unit.json",
        '{"schema_version": 1, "run": "none", "ships": {"kind": "none"}}\n',
    )
    write(repo, "base-repo/apps/app-name/src/.gitkeep", "")
    # The payload ships `docs/agents/` rather than a flow collecting it, so the
    # fixture ships it too: a generate confirms these three and creates the
    # labels they name. `issue-tracker.md` records local markdown, which is the
    # tracker every scenario here uses, since none may contact GitHub.
    write(
        repo,
        "base-repo/docs/agents/issue-tracker.md",
        "# Issue tracker\n\nIssues live as local markdown under `.scratch/`.\n",
    )
    write(
        repo,
        "base-repo/docs/agents/domain.md",
        "# Domain\n\nThe glossary lives in `CONTEXT.md`; ADRs live in `docs/adrs/`.\n",
    )
    write(
        repo,
        "base-repo/docs/agents/triage-labels.md",
        "# Triage labels\n\nbug, enhancement, needs-triage, needs-info, "
        "ready-for-agent, ready-for-human, wontfix\n",
    )
    write(
        repo,
        "base-repo/docs/adrs/0000-template.md",
        """---
type: Template
title: <Decision title>
scope: [] # `apps/<app-name>` for one deployable, `domain` for a business area rather than a deployable, `global` for the repository as a whole, `lang:<name>` for a language
status: proposed
---

# <Decision title>

## Context

<What forced the decision.>

## Alternatives Considered

<One entry per option, each with why it was rejected.>

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


TEMPLATE_ROOT = Path(__file__).resolve().parents[4]
PAYLOAD_ROOT = TEMPLATE_ROOT / "apps/github-repository-template/src/base-repo"

RETROFIT_CHECK = """#!/usr/bin/env bash
set -euo pipefail

# The fixture's whole check surface: the layout audit, then the tests, in the
# Result shape scripts/libs/result.sh defines. A retrofit's bar is this file,
# so it is the real audit and the real suite rather than an echo.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# shellcheck source=libs/result.sh
source "$repo_root/scripts/libs/result.sh"

scripts/structure || result_failed=1

tests=()
while IFS= read -r path; do
  tests+=("$path")
done < <(git ls-files 'test_*.py' '*/test_*.py')

if (( ${#tests[@]} == 0 )); then
  result test not-applicable "no test file"
elif ! grep -q '^test = "unittest"$' pyproject.toml 2> /dev/null; then
  # A tool the root manifest never declared did not run, and a check that did
  # not run is not a check that passed.
  result test unavailable "the root manifest declares no test tool"
else
  for path in "${tests[@]}"; do
    python3 "$path" > /dev/null 2>&1 || record "$path: the suite failed"
  done
  verdict test "every test file passes"
fi

tally
"""


def retrofit_payload(repo: Path) -> None:
    """The payload additions that make a retrofit fixture checkable.

    The real layout audit and the result library it sources, copied from the
    payload this repository ships, plus a check surface that runs them. A
    hand-written stand-in would audit a shape nobody enforces, and then "the
    audit fails before the moves and passes after" would prove nothing.
    """
    for relative in ("scripts/structure", "scripts/libs/result.sh"):
        source = PAYLOAD_ROOT / relative
        write(
            repo,
            f"base-repo/{relative}",
            source.read_text(encoding="utf-8"),
            executable=source.stat().st_mode & 0o100 != 0,
        )
    write(repo, "base-repo/scripts/check", RETROFIT_CHECK, executable=True)


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
    # The GitHub Pages exclusive pair, here so preflight's rejection of the two
    # together has something real to reject.
    write(repo, "repository-addons/_config.yml", "theme: minima\n")
    write(repo, "repository-addons/.nojekyll", "Turns the Jekyll processor off.\n")
    # The one-directional pair: AUTHORS requires LICENSE, and LICENSE alone is
    # the ordinary case. Both here so preflight has something real to check
    # against, including the sequence where LICENSE was adopted long before.
    write(repo, "repository-addons/LICENSE", "License text, verbatim.\n")
    write(repo, "repository-addons/AUTHORS", "REPLACE-COPYRIGHT-HOLDER\n")
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
                    {
                        "token": "REPO-OWNER",
                        "value_key": "repo-owner",
                        "what": "projectOwner.",
                    },
                    {
                        "token": "REPO-NAME",
                        "value_key": "repo-name",
                        "what": "projectName.",
                    },
                ],
                "reviews": [],
                "external": [],
            },
            "_config.yml": {"slots": [], "reviews": [], "external": []},
            ".nojekyll": {"slots": [], "reviews": [], "external": []},
            "LICENSE": {"slots": [], "reviews": [], "external": []},
            "AUTHORS": {
                "slots": [
                    {
                        "token": "REPLACE-COPYRIGHT-HOLDER",
                        "value_key": "copyright-holder",
                        "what": "The first copyright holder.",
                    }
                ],
                "reviews": [],
                "external": [],
            },
        },
    }
    write(repo, "addon-adoption.json", json.dumps(index, indent=2) + "\n")


def manifest(
    template: Path,
    remote: Path,
    old_commit: str,
    overrides: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    generation: dict[str, object] = {
        "application_name": "billing-api",
        "features": {"codeql": "omitted-by-choice"},
    }
    # Absent unless the scenario resolved a collision. An empty list would read
    # as a decision nobody made, and preflight treats the missing key as the
    # ordinary case rather than as an omission.
    if overrides:
        generation["overrides"] = overrides
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
        "generation": generation,
        "ownership": [
            {"path": ".repo-template.json", "mode": "managed"},
            {"path": "CLAUDE.md", "mode": "managed"},
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


def destination_instructions(commands: str) -> str:
    """The root instructions as a generated repository would carry them.

    The payload's text, personalized the way a generate personalizes it -- the
    placeholder app paragraph gone, the Child Index filled -- plus a Deployment
    section the template never shipped. `commands` is the only part a scenario
    varies, because it is the one both sides may reach for.
    """
    return f"""## Commands

{commands}
## Apps

An `apps/` entry is one deployable service.

## Deployment

Deploy `apps/billing-api` from `main` only, and never during month-end close.

## Child Index

- `apps/billing-api/` — invoicing and dunning
"""


def create_destination(
    root: Path,
    template: Path,
    old_commit: str,
    own_check: bool,
    overrides: list[dict[str, str]] | None = None,
    instructions: str | None = None,
) -> tuple[Path, Path]:
    remote = root / "destination.git"
    destination = root / "destination"
    init_repo(remote, bare=True)
    init_repo(destination)

    if own_check:
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
    # Only the scenarios that exercise the root instructions write them. A
    # destination with no CLAUDE.md leaves a template edit to that path an
    # addition rather than the both-changed delta those scenarios need.
    if instructions is not None:
        write(destination, "CLAUDE.md", instructions)
    write(
        destination,
        "scripts/legacy",
        """#!/usr/bin/env bash
set -euo pipefail

echo "preflight ok"
""",
        executable=True,
    )
    write(
        destination,
        "apps/billing-api/src/service.py",
        "PRODUCT_BEHAVIOR = 'invoice customers'\n",
    )
    write(
        destination,
        "docs/product-runbook.md",
        "# Product runbook\n\nPage the billing team for invoice failures.\n",
    )
    write(
        destination,
        ".repo-template.json",
        json.dumps(manifest(template, remote, old_commit, overrides), indent=2) + "\n",
    )
    commit(destination, "Initialize generated product repository")
    run(destination, "remote", "add", "origin", str(remote.resolve()))
    run(destination, "push", "-u", "origin", "main")
    return destination, remote


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_generation(root: Path, scenario: str = "generation") -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    # The held-back tree comes with the payload, as it does in the real
    # template. Without it a flow asking which paths are addons reads a
    # template shape that does not exist, and a destination's own readme
    # cannot be shown to stay out of the payload's collision list.
    addon_payload(template)
    target = commit(template, "Add base repository payload and repository addons")
    return {
        "scenario": scenario,
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
            '#!/usr/bin/env bash\nset -euo pipefail\n\necho "unrelated template"\n',
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
    elif scenario == "instructions-merge":
        # A different section of the root instructions than the destination
        # touched, so the path is a both-changed entry that reconciles rather
        # than a disagreement.
        write(
            template,
            "base-repo/CLAUDE.md",
            payload_instructions(
                PAYLOAD_COMMANDS
                + "- `scripts/fix` — rewrite formatting for every detected stack\n"
            ),
        )
        target_commit = commit(template, "Document the formatting command")
    elif scenario == "instructions-conflict":
        # The same instruction the destination rewrote, decided the other way.
        # The conflicted path is the whole delta here, so "the destination is
        # left exactly as it was" is what a stop looks like. Adding a second,
        # appliable path to this scenario would make that expectation wrong:
        # a stop reports every path's classification, applied ones included.
        write(
            template,
            "base-repo/CLAUDE.md",
            payload_instructions(
                "- `scripts/check` — run repository checks; never skipped,"
                " including during an incident\n"
            ),
        )
        target_commit = commit(template, "Make the check instruction unconditional")
    else:
        # clean-update and override take the same template delta. What differs
        # is the destination: override's carries its own scripts/check and the
        # record saying that collision was settled once, against the payload.
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

    overrides = (
        [
            {
                "path": "scripts/check",
                "reason": "destination runs checks advisory during incident response",
            }
        ]
        if scenario == "override"
        else None
    )
    instructions = None
    if scenario == "instructions-merge":
        instructions = destination_instructions(PAYLOAD_COMMANDS)
    elif scenario == "instructions-conflict":
        instructions = destination_instructions(
            "- `scripts/check` — run repository checks; advisory during an incident\n"
        )
    destination, remote = create_destination(
        root,
        template,
        old_commit,
        own_check=scenario in ("conflict", "override"),
        overrides=overrides,
        instructions=instructions,
    )
    return {
        "scenario": scenario,
        "template_repo": str(template),
        "subtree": "base-repo",
        "old_commit": old_commit,
        "target_commit": target_commit,
        "destination": str(destination),
        "destination_remote": str(remote),
        "product_hashes": {
            "apps/billing-api/src/service.py": sha256(
                destination / "apps/billing-api/src/service.py"
            ),
            "docs/product-runbook.md": sha256(destination / "docs/product-runbook.md"),
        },
    }


def build_adopt(root: Path) -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    addon_payload(template)
    recorded = commit(template, "Add base repository payload and repository addons")

    destination, remote = create_destination(root, template, recorded, own_check=False)
    return {
        "scenario": "adopt",
        "template_repo": str(template),
        "subtree": "base-repo",
        "recorded_commit": recorded,
        "destination": str(destination),
        "destination_remote": str(remote),
    }


RATES_SOURCE = '''"""Interest rates, as the ledger states them."""


def monthly_rate(annual: float) -> float:
    """The annual rate spread across the twelve months that charge it."""
    return annual / {divisor}
'''

RATES_TEST = '''"""The ledger's own suite, run from wherever the file sits.

The source tree is found relative to this file rather than from the repository
root, so the suite passes both before the retrofit moves it and after.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ledger.rates import monthly_rate  # noqa: E402


class MonthlyRateTests(unittest.TestCase):
    def test_spreads_the_annual_rate_across_twelve_months(self) -> None:
        self.assertAlmostEqual(monthly_rate(0.12), 0.01)


if __name__ == "__main__":
    unittest.main()
'''


def create_retrofit_destination(root: Path, red: bool) -> tuple[Path, Path]:
    """A repository that grew without the template: foreign, and checkable.

    Foreign in the ways the flow has to reconcile -- source and tests at the
    root, a root folder nobody granted, a script in the wrong language, records
    at the singular path, and a manifest declaring no tools -- and checkable in
    that its suite really passes and the layout audit really has something to
    fail on. `red` adds the debt the layout work does not fix: a root file that
    cannot move anywhere, and arithmetic that was wrong before this flow
    arrived and is wrong after it.
    """
    remote = root / "destination.git"
    destination = root / "destination"
    init_repo(remote, bare=True)
    init_repo(destination)

    write(destination, "src/ledger/__init__.py", "")
    write(
        destination,
        "src/ledger/rates.py",
        RATES_SOURCE.format(divisor=10 if red else 12),
    )
    write(destination, "tests/test_rates.py", RATES_TEST)
    write(
        destination,
        "scripts/build.py",
        '#!/usr/bin/env python3\n"""Build the ledger wheel."""\n\nprint("built")\n',
        executable=True,
    )
    write(
        destination,
        "pyproject.toml",
        '[project]\nname = "ledger"\nversion = "0.1.0"\n',
    )
    write(
        destination,
        "docs/adr/0001-one-ledger-per-currency.md",
        "# One ledger per currency\n\nEvery currency keeps its own ledger.\n",
    )
    write(
        destination,
        "notes/architecture.md",
        "# Architecture\n\nThe scripts live at the repository root, beside the"
        " source tree they build.\n",
    )
    write(destination, "README.md", "# ledger\n\nInterest and dunning.\n")
    if red:
        write(
            destination,
            "Makefile",
            "build:\n\tpython3 scripts/build.py\n",
        )
    commit(destination, "Initialize the ledger")
    run(destination, "remote", "add", "origin", str(remote.resolve()))
    run(destination, "push", "-u", "origin", "main")
    return destination, remote


def build_retrofit(root: Path, scenario: str) -> dict[str, object]:
    template = root / "template"
    init_repo(template)
    template_payload(template)
    retrofit_payload(template)
    addon_payload(template)
    target = commit(template, "Add base repository payload and repository addons")

    destination, remote = create_retrofit_destination(
        root, red=scenario == "retrofit-red"
    )
    return {
        "scenario": scenario,
        "template_repo": str(template),
        "subtree": "base-repo",
        "target_commit": target,
        "destination": str(destination),
        "destination_remote": str(remote),
        # The blobs the layout step moves rather than writes. A retrofit proves
        # a move is a move, so the scorer needs what the file was beforehand.
        "moved_hashes": {
            "src/ledger/rates.py": sha256(destination / "src/ledger/rates.py"),
            "tests/test_rates.py": sha256(destination / "tests/test_rates.py"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        choices=(
            "generation",
            "generation-multi",
            "generation-handoff",
            "clean-update",
            "override",
            "instructions-merge",
            "instructions-conflict",
            "unrelated",
            "conflict",
            "adopt",
            "retrofit",
            "retrofit-red",
        ),
    )
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--force", action="store_true", help="replace an existing output directory"
    )
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        if not args.force:
            parser.error(f"output already exists: {output}; pass --force to replace it")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    try:
        if args.scenario in ("generation", "generation-multi", "generation-handoff"):
            details = build_generation(output, args.scenario)
        elif args.scenario == "adopt":
            details = build_adopt(output)
        elif args.scenario in ("retrofit", "retrofit-red"):
            details = build_retrofit(output, args.scenario)
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
