#!/usr/bin/env python3
"""Run the fixed steps of a generate and report each as JSON.

`preflight.py` is read-only by contract and only authorizes the next stage.
The steps here write the candidate and the host, so they live beside it, as
`retrofit.py` and `update.py` do, and reuse their helpers by import.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import NoReturn

from preflight import (
    PreflightError,
    classify_path,
    git_output,
    normalize_relative_path,
    repository_identity,
    require_git_repository,
    require_subtree,
    resolve_commit,
    run_git,
    sibling_of_subtree,
    tree_paths,
    validate_manifest,
)
from retrofit import record_path

SCHEMA_VERSION = 1
# GitHub's own alphabet for a repository name, which also keeps the candidate
# a single directory under tmp/.
REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
MANIFEST = ".repo-template.json"
# The features whose value a flow reads as a fixed word rather than free text,
# so any other spelling would record a departure nothing honors.
FIXED_FEATURES = {"codeql": "omitted-by-choice", "prs_are_requests": "true"}


def repository_name(repository: str) -> str:
    owner, _, name = repository.partition("/")
    if not owner or not REPOSITORY_NAME.fullmatch(name) or name in (".", ".."):
        raise PreflightError(f"destination repository is not owner/name: {repository}")
    return name


def extracted_paths(candidate: Path) -> list[str]:
    return sorted(
        path.relative_to(candidate).as_posix()
        for path in candidate.rglob("*")
        if path.is_symlink() or path.is_file()
    )


def materialize(arguments: argparse.Namespace) -> dict[str, object]:
    """Archive the payload at the source commit into tmp/<name>/ and init it.

    `git archive` carries each mode and link out of the pinned tree, never the
    working tree's. A candidate already holding files is refused rather than
    overwritten: it is a resumable generate, or someone else's.
    """
    template = require_git_repository(arguments.template_repo, "template repository")
    root = Path(git_output(template, "rev-parse", "--show-toplevel"))
    commit = resolve_commit(template, arguments.target)
    subtree = normalize_relative_path(arguments.subtree, "template subtree")
    require_subtree(template, commit, subtree)
    candidate = root / "tmp" / repository_name(arguments.destination_repository)
    if candidate.exists() and any(candidate.iterdir()):
        raise PreflightError(f"candidate directory is not empty: {candidate}")

    try:
        archive = subprocess.run(
            ["git", "archive", "--format=tar", f"{commit}:{subtree}"],
            cwd=template,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        raise PreflightError(error.stderr.decode().strip()) from error
    candidate.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(candidate, filter="tar")
    # An export-ignore attribute drops a path from the archive silently.
    payload = tree_paths(template, commit, subtree)
    missing = sorted(set(payload) - set(extracted_paths(candidate)))
    if missing:
        raise PreflightError(f"the archive left out payload paths: {missing}")

    git_output(candidate, "init", "-q", "-b", arguments.default_branch)
    return {
        "candidate": str(candidate),
        "commit": commit,
        "default_branch": arguments.default_branch,
        "head": git_output(candidate, "symbolic-ref", "HEAD"),
        "payload_paths": len(payload),
    }


def ownership_rules(template: Path, commit: str, subtree: str) -> list[object]:
    """Read the canonical ownership list beside the payload at the source commit.

    Read at the commit rather than from the working tree, so the rules are the
    ones written for the payload being generated.
    """
    location = sibling_of_subtree(subtree, "ownership.json")
    shown = run_git(template, "show", f"{commit}:{location}", check=False)
    if shown.returncode != 0:
        raise PreflightError(f"ownership list does not exist at {commit}: {location}")
    try:
        rules = json.loads(shown.stdout).get("ownership")
    except (json.JSONDecodeError, AttributeError) as error:
        raise PreflightError(
            f"ownership list is not a JSON object: {location}"
        ) from error
    if not isinstance(rules, list):
        raise PreflightError(f"ownership list has no ownership array: {location}")
    return rules


def parse_features(raw: list[str]) -> dict[str, object]:
    """Read each `--feature key=value`, `triage_labels.<role>=<label>` for a role."""
    features: dict[str, object] = {}
    labels: dict[str, str] = {}
    for entry in raw:
        key, separator, value = entry.partition("=")
        if not separator or not key or not value:
            raise PreflightError(f"--feature must be key=value: {entry!r}")
        fixed = FIXED_FEATURES.get(key)
        if fixed is not None and value != fixed:
            raise PreflightError(f"--feature {key} takes only {fixed!r}, not {value!r}")
        role = key.removeprefix("triage_labels.")
        if role != key:
            labels[role] = value
        else:
            features[key] = True if key == "prs_are_requests" else value
    if labels:
        features["triage_labels"] = labels
    return features


def recorded_generation(path: Path) -> dict[str, object]:
    """What step 6 already wrote into the manifest, which step 8 keeps."""
    if not path.exists():
        return {}
    try:
        generation = json.loads(path.read_text(encoding="utf-8")).get("generation", {})
    except (json.JSONDecodeError, AttributeError) as error:
        raise PreflightError(f"{path} is not a JSON object") from error
    if not isinstance(generation, dict):
        raise PreflightError(f"{path} generation is not an object")
    return generation


def manifest(arguments: argparse.Namespace) -> dict[str, object]:
    """Write, validate and stage the candidate's `.repo-template.json`.

    A written manifest that fails validation, or leaves a payload path no rule
    reaches, is put back as it was: an unreached path is product-owned, so a
    later template fix to it would land nowhere while the update reports success.
    """
    template = require_git_repository(arguments.template_repo, "template repository")
    root = Path(git_output(template, "rev-parse", "--show-toplevel"))
    commit = resolve_commit(template, arguments.commit)
    subtree = normalize_relative_path(arguments.subtree, "template subtree")
    require_subtree(template, commit, subtree)
    features = parse_features(arguments.feature)
    candidate = require_git_repository(
        root / "tmp" / repository_name(arguments.repository), "candidate"
    )
    path = candidate / MANIFEST
    previous = path.read_bytes() if path.exists() else None
    generation = recorded_generation(path)
    if arguments.application:
        generation["applications"] = arguments.application
    recorded = generation.get("features", {})
    generation["features"] = {
        **(recorded if isinstance(recorded, dict) else {}),
        **features,
    }
    document = {
        "schema_version": SCHEMA_VERSION,
        "template": {
            "repository": repository_identity(template),
            "subtree": subtree,
            "commit": commit,
        },
        "destination": {
            "repository": arguments.repository,
            "default_branch": arguments.default_branch,
        },
        "generation": generation,
        "ownership": ownership_rules(template, commit, subtree),
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    try:
        _, rules, _ = validate_manifest(path)
        unreached = [
            payload_path
            for payload_path in tree_paths(template, commit, subtree)
            if classify_path(payload_path, rules)[1] is None
        ]
        if unreached:
            raise PreflightError(
                f"no ownership rule reaches these payload paths: {unreached}"
            )
    except PreflightError:
        if previous is None:
            path.unlink()
        else:
            path.write_bytes(previous)
        raise
    git_output(candidate, "add", "--", MANIFEST)
    return {
        "manifest": str(path),
        "features": generation["features"],
        "applications": generation.get("applications", []),
        "ownership_rules": len(rules),
        "staged": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Every step's JSON lands at `<prefix>.<record>.json`, retrofit's convention.
    recorded = argparse.ArgumentParser(add_help=False)
    recorded.add_argument(
        "--records",
        type=Path,
        required=True,
        help="the run's record prefix, tmp/<repo>.<commit>",
    )

    materialized = subparsers.add_parser(
        "materialize",
        parents=[recorded],
        help="archive the payload at the source commit into tmp/<name>/",
    )
    materialized.add_argument(
        "--template-repo",
        type=Path,
        default=Path("."),
        help="the template checkout (default: the working directory)",
    )
    materialized.add_argument("--target", required=True, help="template ref or commit")
    materialized.add_argument("--subtree", required=True)
    materialized.add_argument(
        "--destination-repository", required=True, help="owner/name"
    )
    materialized.add_argument("--default-branch", default="main")
    materialized.set_defaults(handler=materialize, record="materialize")

    manifested = subparsers.add_parser(
        "manifest",
        parents=[recorded],
        help="write and stage the candidate's .repo-template.json",
    )
    manifested.add_argument("--template-repo", type=Path, default=Path("."))
    manifested.add_argument("--repository", required=True, help="owner/name")
    manifested.add_argument("--commit", required=True, help="the source commit")
    manifested.add_argument("--subtree", required=True)
    manifested.add_argument("--default-branch", default="main")
    manifested.add_argument("--application", action="append", default=[])
    manifested.add_argument(
        "--feature",
        action="append",
        default=[],
        help="key=value, or triage_labels.<role>=<label>",
    )
    manifested.set_defaults(handler=manifest, record="manifest")
    return parser


def fail(message: str, status: int = 2) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}, indent=2), file=sys.stderr)
    raise SystemExit(status)


def main() -> int:
    arguments = build_parser().parse_args()
    # A step that fails leaves no record, so a renderer never reads an earlier
    # run's result as this one's.
    record = record_path(arguments.records, f"{arguments.record}.json")
    record.unlink(missing_ok=True)
    try:
        result = arguments.handler(arguments)
    except PreflightError as error:
        fail(str(error))
    output = json.dumps(
        {"ok": True, "schema_version": SCHEMA_VERSION, **result},
        indent=2,
        sort_keys=True,
    )
    record.write_text(output + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
