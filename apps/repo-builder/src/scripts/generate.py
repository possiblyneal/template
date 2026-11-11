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
    git_output,
    normalize_relative_path,
    require_git_repository,
    require_subtree,
    resolve_commit,
    run_git,
    tree_paths,
)
from retrofit import (
    WriteLog,
    load_required,
    record_path,
    write_labels,
    write_log_path,
)

SCHEMA_VERSION = 1
# GitHub's own alphabet for a repository name, which also keeps the candidate
# a single directory under tmp/.
REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


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


def materialized_candidate(records: Path) -> tuple[Path, dict]:
    materialized = load_required(records, "materialize")
    candidate = require_git_repository(Path(materialized["candidate"]), "candidate")
    return candidate, materialized


ROOT_MESSAGE = "chore: initialize empty repository"


def bootstrap(arguments: argparse.Namespace) -> dict[str, object]:
    """Push one parentless, empty-tree commit to the remote's default branch.

    `commit-tree` builds it without checking the branch out, which the
    candidate's `no-commit-to-branch` hook would refuse. A default branch
    already on the remote is refused rather than replaced: it is a bootstrap
    that already ran, or someone else's history. One already in the candidate
    is pushed when it is an empty root, which is a push that failed before,
    and refused otherwise.
    """
    candidate, materialized = materialized_candidate(arguments.records)
    branch = arguments.default_branch or materialized["default_branch"]
    ref = f"refs/heads/{branch}"
    git_output(candidate, "check-ref-format", ref)
    remote = run_git(candidate, "remote", "get-url", "origin", check=False)
    if remote.returncode != 0:
        raise PreflightError(f"the candidate has no origin remote: {candidate}")
    if git_output(candidate, "ls-remote", "--heads", "origin", ref):
        raise PreflightError(f"{branch} already exists on origin")
    tree = git_output(candidate, "hash-object", "-w", "-t", "tree", "/dev/null")
    root = run_git(candidate, "rev-parse", "--verify", "-q", ref, check=False).stdout
    root = root.strip()
    if root:
        # A parentless commit lists only itself.
        listed = git_output(candidate, "rev-list", "--parents", "-n", "1", root)
        held = git_output(candidate, "rev-parse", f"{root}^{{tree}}")
        if listed != root or held != tree:
            raise PreflightError(f"{branch} already exists in the candidate")
    else:
        root = git_output(candidate, "commit-tree", tree, "-m", ROOT_MESSAGE)
        # An empty old value makes the write refuse a branch created meanwhile.
        git_output(candidate, "update-ref", ref, root, "")
    git_output(candidate, "push", "-q", "origin", f"{ref}:{ref}")
    return {
        "operation": "bootstrap",
        "repository": arguments.repository,
        "candidate": str(candidate),
        "remote": remote.stdout.strip(),
        "default_branch": branch,
        "root": root,
    }


# The engineering skills' defaults: the sixteen roles, which a
# `generation.features.triage_labels` departure may respell, then the map
# label and the four ticket types a map's tickets carry.
TRIAGE_ROLES = (
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
)
WAYFINDER_LABELS = (
    "wayfinder:map",
    "wayfinder:research",
    "wayfinder:prototype",
    "wayfinder:grilling",
    "wayfinder:task",
)


def triage_departure(candidate: Path) -> dict[str, str]:
    """Step 6's recorded respellings, or none where nothing was recorded."""
    manifest = candidate / ".repo-template.json"
    if not manifest.is_file():
        return {}
    document = json.loads(manifest.read_text())
    mapping = document.get("generation", {}).get("features", {}).get("triage_labels")
    if mapping is None:
        return {}
    if not isinstance(mapping, dict) or not all(
        role in TRIAGE_ROLES and isinstance(label, str) and label
        for role, label in mapping.items()
    ):
        raise PreflightError(
            "generation.features.triage_labels must map triage roles to label names"
        )
    return mapping


def labels(arguments: argparse.Namespace) -> dict[str, object]:
    """Create each missing label through retrofit's writer.

    A case variant is renamed to the default spelling, except where a
    `triage_labels` departure is in force: then the destination's spellings
    are the vocabulary, and nothing is renamed.
    """
    candidate, _ = materialized_candidate(arguments.records)
    departure = triage_departure(candidate)
    names = [departure.get(role, role) for role in TRIAGE_ROLES]
    names += WAYFINDER_LABELS
    log = WriteLog(write_log_path(arguments.records))
    outcome = write_labels(arguments.repository, names, not departure, log)
    if outcome.refused:
        refused = outcome.refused[0]
        raise PreflightError(
            f"label {refused['label']} refused ({refused['outcome']}): "
            f"{refused['reason']}; created before it: {outcome.created or 'none'}"
        )
    return {
        "operation": "labels",
        "repository": arguments.repository,
        "labels": names,
        "created": outcome.created,
        "renamed": outcome.renamed,
        "existing": [item["label"] for item in outcome.skipped],
        "kept": [item for item in outcome.skipped if item["reason"] != "exists"],
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

    bootstrapped = subparsers.add_parser(
        "bootstrap",
        parents=[recorded],
        help="push the empty root commit to the candidate's origin",
    )
    bootstrapped.add_argument("--repository", required=True, help="owner/name")
    bootstrapped.add_argument(
        "--default-branch", help="default: the branch materialize initialized"
    )
    bootstrapped.set_defaults(handler=bootstrap, record="bootstrap")

    labelled = subparsers.add_parser(
        "labels",
        parents=[recorded],
        help="create the triage roles and wayfinder labels that are missing",
    )
    labelled.add_argument("--repository", required=True, help="owner/name")
    labelled.set_defaults(handler=labels, record="labels")
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
