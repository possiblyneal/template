#!/usr/bin/env python3
"""Verify repo-builder evaluation artifacts with objective checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

Check = tuple[str, bool, str]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contains_none(path: Path, needles: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return not any(needle in text for needle in needles)


def report_check(
    report: Path, name: str, predicate: Callable[[str], bool], expected: str
) -> Check:
    if not report.is_file():
        return name, False, f"missing {report}"
    text = report.read_text(encoding="utf-8")
    return name, predicate(text), expected


def no_remote_check(candidate: Path) -> Check:
    """A generate forbidden from contacting GitHub stops at step 4's gate, so no remote is set."""
    return (
        "no configured remote",
        not (candidate / ".git").exists() or not git(candidate, "remote"),
        "candidate has no Git remote",
    )


def setup_skill_checks(candidate: Path) -> list[Check]:
    """`/setup-matt-pocock-skills` ran: every generate configures the tracker."""
    agents = candidate / "docs/agents"
    claude = candidate / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8") if claude.is_file() else ""
    # The skill writes triage-labels.md and its sub-block only where the `triage`
    # skill is installed beside it, so the pair is what holds, not either half.
    labels = (agents / "triage-labels.md").is_file()
    sub_block = "### Triage labels" in text
    return [
        (
            "engineering-skill config written",
            all(
                (agents / name).is_file() for name in ("issue-tracker.md", "domain.md")
            ),
            "docs/agents holds issue-tracker.md and domain.md",
        ),
        (
            "agent skills block added",
            "## Agent skills" in text,
            "root CLAUDE.md carries the ## Agent skills block",
        ),
        (
            "triage labels consistent",
            labels == sub_block,
            "triage-labels.md and the ### Triage labels sub-block are both present or both absent",
        ),
    ]


def generation(root: Path, fixture: dict[str, object]) -> list[Check]:
    candidate = root.parent / "candidate"
    report = root.parent / "report.md"
    manifest_path = candidate / ".repo-template.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    template = manifest.get("template", {}) if isinstance(manifest, dict) else {}
    return [
        ("manifest exists", manifest_path.is_file(), str(manifest_path)),
        (
            "exact provenance",
            template.get("commit") == fixture["target_commit"]
            and template.get("repository") == fixture["template_repo"]
            and template.get("subtree") == fixture["subtree"],
            "manifest template fields match fixture",
        ),
        (
            "application renamed",
            (candidate / "apps/billing-api").is_dir(),
            "apps/billing-api exists",
        ),
        (
            "placeholder app removed",
            not (candidate / "apps/app-name").exists(),
            "apps/app-name absent",
        ),
        (
            "CLAUDE bootstrap resolved",
            contains_none(
                candidate / "CLAUDE.md", ("apps/app-name", "not yet indexed")
            ),
            "root CLAUDE.md has no generation placeholders",
        ),
        (
            "lessons initialized",
            contains_none(
                candidate / "docs/LESSONS.md",
                ("<actor>", "<ISO 8601", "<Replace", "<Add repository"),
            ),
            "lessons metadata and placeholders resolved",
        ),
        (
            "ADR template retained",
            (candidate / "docs/adrs/0000-template.md").is_file()
            and "type: Template"
            in (candidate / "docs/adrs/0000-template.md").read_text(encoding="utf-8"),
            "docs/adrs/0000-template.md remains a template",
        ),
        report_check(
            report,
            "boundaries reported as supplied",
            lambda text: (
                "billing-api" in text
                and any(
                    term in text.lower()
                    for term in ("supplied", "not derived", "skipped")
                )
            ),
            "report names the deployable and says it was supplied rather than derived",
        ),
        report_check(
            report,
            "PR bootstrap described",
            lambda text: all(
                term in text.lower()
                for term in ("empty", "main", "branch", "pull request")
            ),
            "report describes empty main base and content PR",
        ),
        no_remote_check(candidate),
        *setup_skill_checks(candidate),
    ]


def adr_records(candidate: Path) -> list[Path]:
    """Every ADR the build wrote, excluding the retained template."""
    adrs = candidate / "docs/adrs"
    if not adrs.is_dir():
        return []
    return sorted(
        p
        for p in adrs.glob("[0-9][0-9][0-9][0-9]-*.md")
        if p.name != "0000-template.md"
    )


def generation_multi(root: Path, fixture: dict[str, object]) -> list[Check]:
    """Two deployables derived by wayfinding, each with a directory and an ADR."""
    candidate = root.parent / "candidate"
    report = root.parent / "report.md"
    manifest_path = candidate / ".repo-template.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    applications = (
        manifest.get("generation", {}).get("applications", [])
        if isinstance(manifest, dict)
        else []
    )
    expected = ("recorder", "ingest-api")
    records = adr_records(candidate)
    adr_text = "\n".join(p.read_text(encoding="utf-8") for p in records)
    return [
        (
            "both deployables created",
            all((candidate / f"apps/{name}").is_dir() for name in expected),
            "apps/recorder and apps/ingest-api exist",
        ),
        (
            "skeleton replicated",
            all(
                (candidate / f"apps/{name}" / "src").is_dir()
                and (candidate / f"apps/{name}" / ".unit.json").is_file()
                for name in expected
            ),
            "each app carries src and .unit.json",
        ),
        (
            "placeholder app removed",
            not (candidate / "apps/app-name").exists(),
            "apps/app-name absent",
        ),
        (
            "manifest lists both",
            sorted(applications) == sorted(expected),
            "generation.applications names exactly the two deployables",
        ),
        (
            "no language in manifest",
            not any(
                lang in json.dumps(manifest.get("generation", {})).lower()
                for lang in ("typescript", "golang", '"go"', "python", "rust")
            ),
            "generation records names only; language lives in the ADRs",
        ),
        (
            "one ADR per deployable",
            len(records) == 2,
            f"two numbered ADRs, found {len(records)}",
        ),
        (
            "ADRs scoped to their app and language",
            all(f"apps/{name}" in adr_text for name in expected)
            and adr_text.count("lang:") >= 2,
            "each ADR scopes to apps/<name> and a lang: tag",
        ),
        (
            "ADRs accepted, not proposed",
            bool(records)
            and all(
                "status: accepted" in p.read_text(encoding="utf-8") for p in records
            ),
            "every written ADR records status: accepted",
        ),
        (
            "ADR template retained",
            (candidate / "docs/adrs/0000-template.md").is_file()
            and "type: Template"
            in (candidate / "docs/adrs/0000-template.md").read_text(encoding="utf-8"),
            "docs/adrs/0000-template.md remains a template",
        ),
        (
            "boundaries carried into CLAUDE.md",
            contains_none(candidate / "CLAUDE.md", ("apps/app-name", "not yet indexed"))
            and all(
                name in (candidate / "CLAUDE.md").read_text(encoding="utf-8")
                for name in expected
            ),
            "root CLAUDE.md names both deployables and keeps no placeholders",
        ),
        report_check(
            report,
            "choke points reported",
            lambda text: (
                all(name in text for name in expected) and "choke point" in text.lower()
            ),
            "report names each deployable with the constraint that selected its language",
        ),
        no_remote_check(candidate),
        *setup_skill_checks(candidate),
    ]


def generation_handoff(root: Path, fixture: dict[str, object]) -> list[Check]:
    """The decomposition is fogged: the generate stops at the wayfinding handoff."""
    candidate = root.parent / "candidate"
    report = root.parent / "report.md"
    # The eval forbids contacting GitHub, so step 6 has no remote to propose from
    # and records local markdown. `/wayfinder` charts where that file sends it.
    map_dir = candidate / ".scratch"
    map_files = sorted(map_dir.glob("**/*.md")) if map_dir.is_dir() else []
    tracker = candidate / "docs/agents/issue-tracker.md"
    return [
        (
            "candidate materialized",
            (candidate / "scripts").is_dir()
            and (candidate / "docs/adrs/0000-template.md").is_file(),
            "the subtree was copied before the stop, so a resume need not rebuild it",
        ),
        (
            "placeholder app retained",
            (candidate / "apps/app-name").is_dir(),
            "personalization has not run; apps/app-name is still the placeholder",
        ),
        (
            "no boundaries invented",
            not adr_records(candidate),
            "no numbered ADR written, since no choke point was established",
        ),
        (
            "tracker recorded before charting",
            tracker.is_file()
            and "markdown" in tracker.read_text(encoding="utf-8").lower(),
            "docs/agents/issue-tracker.md records the local-markdown tracker",
        ),
        (
            "map charted on the tracker",
            bool(map_files),
            "the map is under .scratch/, where the recorded tracker puts issues",
        ),
        (
            "map has open tickets",
            any(p.name != "map.md" for p in map_files),
            "charting produced tickets, not just a map body",
        ),
        (
            "no ticket resolved",
            bool(map_files)
            and not any(
                "status: resolved" in p.read_text(encoding="utf-8").lower()
                for p in map_files
            ),
            "charting hand-resolves nothing; every ticket is still open",
        ),
        report_check(
            report,
            "reported as stopped",
            lambda text: "stopped" in text.lower() and "not created" in text.lower(),
            "Operation: stopped with no pull request",
        ),
        report_check(
            report,
            "handoff named",
            lambda text: "/wayfinder" in text and ".scratch" in text,
            "report hands off to /wayfinder and points at the map",
        ),
        report_check(
            report,
            "trigger named",
            lambda text: "wayfinding:" in text.lower(),
            "the Wayfinding line records which trigger fired",
        ),
        no_remote_check(candidate),
        *setup_skill_checks(candidate),
    ]


def update(root: Path, fixture: dict[str, object], scenario: str) -> list[Check]:
    destination = Path(str(fixture["destination"]))
    report = root / "report.md"
    manifest_path = destination / ".repo-template.json"
    manifest = json.loads(manifest_path.read_text())
    current_commit = manifest["template"]["commit"]
    remote = Path(str(fixture["destination_remote"]))
    remote_head = git(remote, "rev-parse", "refs/heads/main")
    local_head = git(destination, "rev-parse", "HEAD")
    # The fixture is parsed JSON, so every value arrives as `object`. This one
    # is the path-to-digest map setup_fixture.py wrote; the cast states that
    # shape rather than re-deriving it at runtime.
    product_hashes = cast("dict[str, str]", fixture["product_hashes"])

    checks: list[Check] = [
        (
            "product files preserved",
            all(
                digest(destination / path) == expected
                for path, expected in product_hashes.items()
            ),
            "recorded product hashes remain equal",
        ),
        (
            "remote unchanged",
            remote_head == local_head,
            "bare remote main still equals local HEAD",
        ),
    ]

    if scenario == "clean-update":
        check_path = destination / "scripts/check"
        checks.extend(
            [
                (
                    "manifest advanced",
                    current_commit == fixture["target_commit"],
                    "manifest records target commit",
                ),
                (
                    "managed change applied",
                    check_path.is_file()
                    and "scripts/preflight" in check_path.read_text(encoding="utf-8")
                    and "check v2" in check_path.read_text(encoding="utf-8"),
                    "scripts/check runs preflight and check v2",
                ),
                (
                    "destination note preserved",
                    check_path.is_file()
                    and "run this before every deployment"
                    in check_path.read_text(encoding="utf-8"),
                    "non-overlapping operational note remains",
                ),
                (
                    "rename applied",
                    (destination / "scripts/preflight").is_file()
                    and not (destination / "scripts/legacy").exists(),
                    "legacy renamed to preflight",
                ),
                report_check(
                    report,
                    "classification reported",
                    lambda text: all(
                        term in text.lower()
                        for term in ("applied", "preserved", "renamed", "conflict")
                    ),
                    "report classifies lifecycle paths",
                ),
            ]
        )
    else:
        checks.extend(
            [
                (
                    "manifest unchanged",
                    current_commit == fixture["old_commit"],
                    "manifest remains at recorded commit",
                ),
                (
                    "worktree unchanged",
                    not git(destination, "status", "--porcelain"),
                    "destination has no tracked or untracked changes",
                ),
                (
                    "no local commit",
                    local_head == remote_head,
                    "local HEAD remains at remote main",
                ),
            ]
        )
        if scenario == "unrelated":
            checks.append(
                report_check(
                    report,
                    "ancestry rejection reported",
                    lambda text: "ancestor" in text.lower() and "not" in text.lower(),
                    "report says recorded commit is not an ancestor",
                )
            )
        else:
            checks.extend(
                [
                    report_check(
                        report,
                        "semantic conflict reported",
                        lambda text: (
                            "scripts/check" in text
                            and "conflict" in text.lower()
                            and "template" in text.lower()
                            and "product" in text.lower()
                        ),
                        "report explains both intents for scripts/check",
                    ),
                    (
                        "no conflict markers",
                        all(
                            marker not in path.read_text(encoding="utf-8")
                            for path in destination.rglob("*")
                            if path.is_file() and ".git" not in path.parts
                            for marker in ("<<<<<<<", "=======", ">>>>>>>")
                        ),
                        "tracked content contains no conflict markers",
                    ),
                ]
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="path to fixture.json")
    args = parser.parse_args()
    fixture_path = args.fixture.resolve()
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    scenario = str(fixture["scenario"])
    if scenario == "generation":
        checks = generation(fixture_path.parent, fixture)
    elif scenario == "generation-multi":
        checks = generation_multi(fixture_path.parent, fixture)
    elif scenario == "generation-handoff":
        checks = generation_handoff(fixture_path.parent, fixture)
    else:
        checks = update(fixture_path.parent, fixture, scenario)
    result = {
        "scenario": scenario,
        "passed": sum(passed for _, passed, _ in checks),
        "failed": sum(not passed for _, passed, _ in checks),
        "checks": [
            {"text": text, "passed": passed, "evidence": evidence}
            for text, passed, evidence in checks
        ],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"verification failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
