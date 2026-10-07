#!/usr/bin/env python3
"""Run an update's mechanical steps and report each as JSON.

`preflight.py` is read-only by contract and only classifies the delta. The
steps here write the destination -- apply what needs no judgment, prove the
copies, advance the recorded commit -- so they live beside it, and reuse its
helpers by import. What `apply` leaves is what the flow reconciles by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import preflight
from preflight import PreflightError, git_output, run_git

SCHEMA_VERSION = 1
MANIFEST = ".repo-template.json"
AUTOMATION_PREFIX = ".github/"
DEPENDABOT = ".github/dependabot.yml"
CODEQL = ".github/workflows/codeql.yml"
EXECUTABLE = "100755"
SYMLINK = "120000"


def blob_bytes(repository: Path, revision: str) -> bytes:
    """A blob's exact bytes; `run_git` decodes, which would rewrite a binary file."""
    try:
        return subprocess.run(
            ["git", "cat-file", "blob", revision],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip()
        raise PreflightError(detail or f"cannot read {revision}") from error


def payload_mode(template_repo: Path, target: str, subtree: str, path: str) -> str:
    entry = git_output(template_repo, "ls-tree", target, "--", f"{subtree}/{path}")
    if not entry:
        raise PreflightError(f"payload has no {path} at {target}")
    return entry.split()[0]


def is_ignored(destination: Path, path: str) -> bool:
    found = run_git(destination, "check-ignore", "-q", "--", path, check=False)
    if found.returncode not in (0, 1):
        raise PreflightError(found.stderr.strip() or "git check-ignore failed")
    return found.returncode == 0


def stage(destination: Path, path: str) -> None:
    """Stage a write, except where the ignore file excludes the path.

    An ignored path is written to disk only: forcing it into the index would
    commit what the destination chose to keep out of git.
    """
    if not is_ignored(destination, path):
        run_git(destination, "add", "--", path)


def write_payload(
    destination: Path, template_repo: Path, target: str, subtree: str, path: str
) -> None:
    """Write the payload's version of a path, at the payload's mode."""
    mode = payload_mode(template_repo, target, subtree, path)
    content = blob_bytes(template_repo, f"{target}:{subtree}/{path}")
    file = destination / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.unlink(missing_ok=True)
    if mode == SYMLINK:
        os.symlink(content.decode(), file)
    else:
        file.write_bytes(content)
        file.chmod(0o755 if mode == EXECUTABLE else 0o644)
    stage(destination, path)


def remove(destination: Path, path: str) -> None:
    """Delete a path, from the index too where the destination tracks it."""
    if git_output(destination, "ls-files", "--", path):
        run_git(destination, "rm", "-q", "-f", "--", path)
    else:
        (destination / path).unlink(missing_ok=True)


def apply_one(
    change: dict[str, object],
    destination: Path,
    template_repo: Path,
    target: str,
    subtree: str,
) -> dict[str, str]:
    """Land one change and describe it.

    An expired override's old path is untracked, so nothing is removed for it:
    the payload's version lands at the new path.
    """
    status = str(change["status"])
    path = str(change["path"])
    expired = bool(change.get("override_expired"))
    if status.startswith("D"):
        if expired or change.get("destination_state") == "absent":
            return {"path": path, "action": "already-absent"}
        remove(destination, path)
        return {"path": path, "action": "delete"}
    if status.startswith("R"):
        old_path = str(change["old_path"])
        if not expired:
            remove(destination, old_path)
        write_payload(destination, template_repo, target, subtree, path)
        return {"path": path, "action": "move", "old_path": old_path}
    write_payload(destination, template_repo, target, subtree, path)
    return {"path": path, "action": "write"}


def left_reason(
    change: dict[str, object],
    codeql_omitted: bool,
    rules: list[preflight.OwnershipRule],
) -> str | None:
    """Why `apply` does not land a change, or None where it does."""
    path = str(change["path"])
    if path == DEPENDABOT:
        return "derive"
    if "old_path" in change and (
        preflight.classify_path(str(change["old_path"]), rules)[0] != "managed"
    ):
        return "product-owned"
    if path.startswith(AUTOMATION_PREFIX):
        if codeql_omitted and path == CODEQL:
            return "codeql-omitted-by-choice"
        return None
    if change["ownership"] != "managed":
        return "product-owned"
    if change.get("override_expired"):
        return None
    state = change["destination_state"]
    if state == "unmodified":
        return None
    if state == "absent" and str(change["status"])[0] in "AD":
        return None
    return str(state)


def apply_update(arguments: argparse.Namespace) -> dict[str, object]:
    result = preflight.update_preflight(
        argparse.Namespace(**{**vars(arguments), "manifest": MANIFEST})
    )
    template = result["template"]
    assert isinstance(template, dict)
    target, subtree = str(template["target_commit"]), str(template["subtree"])
    destination = arguments.destination.resolve()
    template_repo = arguments.template_repo.resolve()
    manifest, rules, overrides = preflight.validate_manifest(destination / MANIFEST)
    generation = manifest.get("generation", {})
    assert isinstance(generation, dict)
    features = generation.get("features", {})
    codeql_omitted = isinstance(features, dict) and (
        features.get("codeql") == "omitted-by-choice"
    )

    applied: dict[str, int] = {}
    removed: list[dict[str, str]] = []
    discarded: list[dict[str, str]] = []
    left: list[dict[str, str]] = []
    overridden: list[dict[str, str]] = []
    unmatched = result["unmatched_overrides"]
    assert isinstance(unmatched, list)
    refused_overrides = [
        {"path": entry["path"], "reason": entry["reason"]}
        for entry in unmatched
        if entry["path"].startswith(AUTOMATION_PREFIX)
    ]
    changes = result["changes"]
    assert isinstance(changes, list)
    for change in changes:
        refused = False
        if change.get("overridden"):
            path = str(change["path"])
            entry = {
                "path": path if path in overrides else str(change["old_path"]),
                "reason": str(change.get("override_reason")),
            }
            if not path.startswith(AUTOMATION_PREFIX):
                overridden.append(entry)
                continue
            refused_overrides.append(entry)
            refused = True
        reason = left_reason(change, codeql_omitted, rules)
        if reason:
            left.append(
                {
                    "path": str(change["path"]),
                    "status": str(change["status"]),
                    "destination_state": str(change.get("destination_state")),
                    "reason": reason,
                }
            )
            continue
        landed = apply_one(change, destination, template_repo, target, subtree)
        applied[landed["action"]] = applied.get(landed["action"], 0) + 1
        if landed["action"] != "write":
            removed.append(landed)
        lost = landed.get("old_path", landed["path"])
        if lost.startswith(AUTOMATION_PREFIX) and (
            refused or change.get("destination_state") == "modified"
        ):
            discarded.append(landed)
    return {
        "operation": "update-apply",
        "template": template,
        "destination": result["destination"],
        "applied": dict(sorted(applied.items())),
        "removed": removed,
        "discarded": discarded,
        "left": left,
        "overridden": overridden,
        "refused_overrides": refused_overrides,
        "unmatched_overrides": [
            entry
            for entry in unmatched
            if not entry["path"].startswith(AUTOMATION_PREFIX)
        ],
    }


def ignored_payload_paths(
    destination: Path, template_repo: Path, recorded: str, target: str, subtree: str
) -> list[str]:
    """Delta paths the destination's ignore rules exclude and disk holds.

    Only paths the update could have written: a payload path it never touched
    may carry a long-standing local edit, which is not this update's to prove.
    """
    prefix = f"{subtree.rstrip('/')}/"
    delta = preflight.nul_fields(
        template_repo,
        "diff",
        "--name-only",
        "--diff-filter=d",
        "-z",
        "--find-renames",
        recorded,
        target,
        "--",
        subtree,
    )
    paths = [
        path
        for path in (entry.removeprefix(prefix) for entry in delta)
        if (destination / path).is_file() or (destination / path).is_symlink()
    ]
    if not paths:
        return []
    found = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"],
        cwd=destination,
        input="\0".join(paths) + "\0",
        text=True,
        capture_output=True,
        check=False,
    )
    if found.returncode not in (0, 1):
        raise PreflightError(found.stderr.strip() or "git check-ignore failed")
    return [path for path in found.stdout.split("\0") if path]


def prove_copies(arguments: argparse.Namespace) -> dict[str, object]:
    destination = preflight.require_git_repository(arguments.destination, "destination")
    template_repo = preflight.require_git_repository(
        arguments.template_repo, "template repository"
    )
    target = preflight.resolve_commit(template_repo, arguments.target)
    manifest, _, _ = preflight.validate_manifest(destination / MANIFEST)
    template = manifest["template"]
    assert isinstance(template, dict)
    subtree = str(template["subtree"])
    staged = preflight.nul_fields(
        destination, "diff", "--cached", "--name-only", "--diff-filter=d", "-z"
    )
    recorded = preflight.resolve_commit(template_repo, str(template["commit"]))
    ignored = ignored_payload_paths(
        destination, template_repo, recorded, target, subtree
    )
    paths = sorted({*staged, *ignored, MANIFEST})
    authored: list[str] = []
    for path in paths:
        file = destination / path
        held = (
            git_output(destination, "hash-object", "--", path)
            if file.is_file() or file.is_symlink()
            else None
        )
        source = run_git(
            template_repo,
            "rev-parse",
            "--verify",
            "--quiet",
            f"{target}:{subtree}/{path}",
            check=False,
        )
        if path == MANIFEST or source.returncode != 0 or source.stdout.strip() != held:
            authored.append(path)
    return {
        "operation": "update-proof",
        "template": {"subtree": subtree, "target_commit": target},
        "identical": len(paths) - len(authored),
        "total": len(paths),
        "authored": authored,
    }


def advance_commit(arguments: argparse.Namespace) -> dict[str, object]:
    destination = preflight.require_git_repository(arguments.destination, "destination")
    template_repo = preflight.require_git_repository(
        arguments.template_repo, "template repository"
    )
    new = preflight.resolve_commit(template_repo, arguments.target)
    path = destination / MANIFEST
    manifest, _, _ = preflight.validate_manifest(path)
    template = manifest["template"]
    assert isinstance(template, dict)
    old = str(template["commit"])
    text = path.read_text(encoding="utf-8")
    pair = re.compile(rf'("commit"\s*:\s*"){re.escape(old)}(")')
    found = len(pair.findall(text))
    if found != 1:
        raise PreflightError(
            f'{MANIFEST} holds {found} "commit": "{old}" pairs; refusing to rewrite it'
        )
    path.write_text(pair.sub(lambda m: f"{m[1]}{new}{m[2]}", text), encoding="utf-8")
    try:
        preflight.validate_manifest(path)
    except PreflightError:
        path.write_text(text, encoding="utf-8")
        raise
    run_git(destination, "add", "--", MANIFEST)
    return {"operation": "update-advance", "old_commit": old, "new_commit": new}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, handler, help_text in (
        ("apply", apply_update, "land the paths that need no judgment, staged"),
        ("proof", prove_copies, "split the staged diff into copies and authored"),
        ("advance", advance_commit, "rewrite template.commit to the target"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--template-repo", type=Path, required=True)
        command.add_argument("--target", required=True, help="template ref or commit")
        command.add_argument("--destination", type=Path, required=True)
        command.set_defaults(handler=handler)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = arguments.handler(arguments)
    except PreflightError as error:
        preflight.fail(str(error))
    print(
        json.dumps(
            {"ok": True, "schema_version": SCHEMA_VERSION, **result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
