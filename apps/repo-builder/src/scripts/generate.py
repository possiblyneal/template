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
    tree_paths,
)
from retrofit import record_path

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
