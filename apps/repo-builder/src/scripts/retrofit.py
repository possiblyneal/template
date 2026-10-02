#!/usr/bin/env python3
"""Run the fixed steps of a retrofit and report each as JSON.

`preflight.py` is read-only by contract and only authorizes the next stage.
The steps here act on the candidate, the operator's clone, or the host, so
they live beside it rather than in it, and reuse its git helpers by import.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

import preflight
from preflight import PreflightError, git_output, nul_fields, run_git

SCHEMA_VERSION = 1


def staged_changes(candidate: Path) -> list[tuple[str, list[str]]]:
    """Every staged change as (status, paths), renames detected."""
    fields = nul_fields(candidate, "diff", "--cached", "-M", "--name-status", "-z")
    changes: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        width = 2 if status[0] in "RC" else 1
        changes.append((status, fields[index + 1 : index + 1 + width]))
        index += 1 + width
    return changes


def blob(repository: Path, revision: str) -> str | None:
    found = run_git(repository, "rev-parse", "-q", "--verify", revision, check=False)
    return found.stdout.strip() if found.returncode == 0 else None


def line_delta(candidate: Path, old: str, new: str) -> tuple[int, int]:
    """Lines added and removed by a move, read from the index."""
    numstat = git_output(
        candidate, "diff", "--cached", "-M", "--numstat", "--", old, new
    )
    added = removed = 0
    for line in numstat.splitlines():
        plus, minus, _ = line.split("\t", 2)
        if plus != "-":
            added += int(plus)
            removed += int(minus)
    return added, removed


def proofs(arguments: argparse.Namespace) -> dict[str, object]:
    """Measure the copy proof and the rename-purity proof from the index.

    Both read `--cached`, so they are only true before the flow's first
    commit: afterwards the index holds nothing they read and both report a
    clean count over an empty set. The refusals below are that ordering.
    """
    template = preflight.require_git_repository(arguments.template_repo, "template")
    target = preflight.resolve_commit(template, arguments.target)
    subtree = preflight.normalize_relative_path(arguments.subtree, "template subtree")
    preflight.require_subtree(template, target, subtree)
    candidate = preflight.require_git_repository(arguments.candidate, "candidate")
    base = preflight.resolve_commit(candidate, arguments.base)

    if git_output(candidate, "rev-parse", "HEAD") != base:
        raise PreflightError(
            "the candidate has commits past its base; measure both proofs "
            "before the flow's first commit"
        )
    changes = staged_changes(candidate)
    if not changes:
        raise PreflightError(
            "nothing is staged; stage the candidate before measuring, since "
            "both proofs read the index"
        )

    prefix = subtree.rstrip("/")
    payload = [
        path
        for path in preflight.tree_paths(template, target, subtree)
        if not path.startswith(preflight.PLACEHOLDER_UNIT_PREFIX)
    ]
    payload_set = set(payload)
    staged = {paths[-1] for status, paths in changes if status != "D"}
    # `--cached` never lists a path the candidate's own ignore rules exclude,
    # so those copies are read from disk instead.
    excluded = payload_set & set(
        preflight.listed_paths(candidate, "--others", "--ignored", "--exclude-standard")
    )

    identical = 0
    differing: list[dict[str, object]] = []
    missing: list[str] = []
    for path in payload:
        if not (candidate / path).is_file():
            missing.append(path)
            continue
        if path not in staged and path not in excluded:
            continue
        expected = blob(template, f"{target}:{prefix}/{path}")
        actual = git_output(candidate, "hash-object", "--", path)
        if actual == expected:
            identical += 1
            continue
        at_base = blob(candidate, f"{base}:{path}") is not None
        differing.append(
            {
                "path": path,
                "class": "merged" if at_base else "extended",
                "ignored": path in excluded,
            }
        )

    moves: list[dict[str, object]] = []
    for status, paths in changes:
        if not status.startswith("R"):
            continue
        old, new = paths
        added, removed = line_delta(candidate, old, new)
        moves.append(
            {
                "from": old,
                "to": new,
                "similarity": int(status[1:]),
                "identical": blob(candidate, f"{base}:{old}")
                == blob(candidate, f":{new}"),
                "added": added,
                "removed": removed,
            }
        )

    moved = {str(move["to"]) for move in moves}
    authored = sorted(staged - payload_set - moved)
    return {
        "operation": "proofs",
        "template": {"commit": target, "subtree": subtree},
        "candidate": {"path": str(candidate), "base": base},
        "copy": {
            "identical": identical,
            "total": identical + len(differing),
            "differing": differing,
            "missing": missing,
        },
        "rename_purity": {
            "identical": sum(1 for move in moves if move["identical"]),
            "total": len(moves),
            "moves": moves,
        },
        # Neither proof can produce a finding here, so this is what the
        # review reads, together with every differing copy and impure move.
        "authored": authored,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    measure = subparsers.add_parser(
        "proofs", help="measure the copy and rename-purity proofs from the index"
    )
    measure.add_argument("--template-repo", type=Path, required=True)
    measure.add_argument("--target", required=True, help="template ref or commit")
    measure.add_argument("--subtree", required=True)
    measure.add_argument("--candidate", type=Path, required=True)
    measure.add_argument(
        "--base",
        required=True,
        help="the destination commit the candidate branched from",
    )
    measure.set_defaults(handler=proofs)
    return parser


def fail(message: str, status: int = 2) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}, indent=2), file=sys.stderr)
    raise SystemExit(status)


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = arguments.handler(arguments)
    except PreflightError as error:
        fail(str(error))
    output = {"ok": True, "schema_version": SCHEMA_VERSION, **result}
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
