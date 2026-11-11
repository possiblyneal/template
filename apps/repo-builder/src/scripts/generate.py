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
    nul_fields,
    require_git_repository,
    require_subtree,
    resolve_commit,
    tree_paths,
    validate_manifest,
)
from retrofit import hook_types, install_hooks, prior_hooks, record_path
from update import MANIFEST, copy_proof

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


def hooks(arguments: argparse.Namespace) -> dict[str, object]:
    """Install the candidate's pre-commit hooks by retrofit's recipe.

    The candidate is a dedicated clone, so the shims go in its own `.git/hooks`
    and `core.hooksPath` is pinned at local scope; a hook git was already
    running from a global `core.hooksPath` is chained under them. Success is
    read from the outcome `install_hooks` checks, a shim for every configured
    type in the directory git resolves, never from an exit status: a missed
    install ships a candidate with no secret scan or branch refusal while
    every check step 9 runs directly still passes.
    """
    tree = require_git_repository(arguments.tree, "candidate")
    if not (tree / ".pre-commit-config.yaml").is_file():
        return {
            "operation": "hooks",
            "outcome": "not-applicable",
            "reason": "the candidate carries no .pre-commit-config.yaml",
        }
    types = hook_types(tree)
    prior = prior_hooks(tree)
    installed = install_hooks(tree, tree, types, Path(prior["path"]))
    return {
        "ok": installed.ready and not installed.findings,
        "operation": "hooks",
        "outcome": "installed" if installed.ready else "failed",
        "hook_types": types,
        "hooks_path": str(installed.hooks_dir),
        "prior_hooks": prior,
        "moved_aside": installed.moved,
        "chained": installed.chained,
        "findings": installed.findings,
    }


TEMPLATE_APPLICATION = "apps/app-name/"
ADR = re.compile(r"^docs/adrs/\d{4}-[^/]+\.md$")
ADDITIONS = (MANIFEST, "docs/adrs/index.md")


def ignored_tracked(tree: Path) -> list[str]:
    """Tracked paths the candidate's own ignore rules exclude.

    `--no-index` is the whole check: without it `check-ignore` consults the
    index, where a tracked path is never ignored, so a force-added path reads
    as clean in exactly the case this looks for.
    """
    tracked = nul_fields(tree, "ls-files", "-z")
    if not tracked:
        return []
    found = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=tree,
        input="\0".join(tracked) + "\0",
        text=True,
        capture_output=True,
        check=False,
    )
    if found.returncode not in (0, 1):
        raise PreflightError(found.stderr.strip() or "git check-ignore failed")
    return sorted(path for path in found.stdout.split("\0") if path)


def filelist(arguments: argparse.Namespace) -> dict[str, object]:
    """Account for every path the payload ships and every path the candidate adds.

    A content check cannot see absence, so the payload's tracked paths at the
    source commit are compared with the candidate's. A path the candidate
    ignores is present on disk rather than tracked, read with
    `ls-files -o -i --exclude-standard`, the one form that lists it. The first
    application stands where the payload's `apps/app-name/` stood. What only
    the candidate holds is an addition step 8 makes or a stray; a local issue
    tracker's `.scratch/` is an addition where the manifest records one.
    """
    template = require_git_repository(arguments.template_repo, "template repository")
    tree = require_git_repository(arguments.tree, "candidate")
    commit = resolve_commit(template, arguments.commit)
    manifest, _, _ = validate_manifest(tree / MANIFEST)
    recorded = manifest["template"]
    assert isinstance(recorded, dict)
    subtree = str(recorded["subtree"])
    generation = manifest.get("generation")
    generation = generation if isinstance(generation, dict) else {}
    applications = [str(name) for name in generation.get("applications") or []]
    features = generation.get("features")
    tracker = isinstance(features, dict) and "issue_tracker" in features

    def placed(path: str) -> str:
        if applications and path.startswith(TEMPLATE_APPLICATION):
            return f"apps/{applications[0]}/{path.removeprefix(TEMPLATE_APPLICATION)}"
        return path

    payload = {placed(path) for path in tree_paths(template, commit, subtree)}
    tracked = set(nul_fields(tree, "ls-files", "-z"))
    untracked_ignored = set(
        nul_fields(tree, "ls-files", "-z", "-o", "-i", "--exclude-standard")
    )
    ignored_present = sorted(payload & untracked_ignored)
    missing = sorted(payload - tracked - untracked_ignored)

    added = tuple(f"apps/{name}/" for name in applications[1:])
    if tracker:
        added += (".scratch/",)
    additions: list[str] = []
    strays: list[str] = []
    for path in sorted(tracked - payload):
        allowed = path in ADDITIONS or ADR.match(path) or path.startswith(added)
        (additions if allowed else strays).append(path)
    defects = ignored_tracked(tree)
    return {
        "ok": not (missing or strays or defects),
        "operation": "filelist",
        "template": {"subtree": subtree, "commit": commit},
        "payload_paths": len(payload),
        "tracked_paths": len(tracked),
        "missing": missing,
        "additions": additions,
        "strays": strays,
        "ignored_present": ignored_present,
        "ignored_tracked": defects,
        "copy": copy_proof(tree, template, commit, subtree, ignored_present),
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

    hooked = subparsers.add_parser(
        "hooks", parents=[recorded], help="install and resolve the candidate's hooks"
    )
    hooked.add_argument("--tree", type=Path, required=True, help="the candidate")
    hooked.set_defaults(handler=hooks, record="hooks")

    listed = subparsers.add_parser(
        "filelist",
        parents=[recorded],
        help="account for every payload and candidate path, and prove the copies",
    )
    listed.add_argument("--tree", type=Path, required=True, help="the candidate")
    listed.add_argument("--commit", required=True, help="the source commit")
    listed.add_argument(
        "--template-repo",
        type=Path,
        default=Path("."),
        help="the template checkout (default: the working directory)",
    )
    listed.set_defaults(handler=filelist, record="filelist")
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
    # A step that ran and found defects sets `ok` false: recorded, exit 1.
    reported = {"ok": True, "schema_version": SCHEMA_VERSION, **result}
    output = json.dumps(reported, indent=2, sort_keys=True)
    record.write_text(output + "\n")
    print(output)
    return 0 if reported["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
