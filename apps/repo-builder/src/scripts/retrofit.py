#!/usr/bin/env python3
"""Run the fixed steps of a retrofit and report each as JSON.

`preflight.py` is read-only by contract and only authorizes the next stage.
The steps here act on the candidate, the operator's clone, or the host, so
they live beside it rather than in it, and reuse its git helpers by import.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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


SHIM_MARKER = "File generated by pre-commit"
HOOK_TEST_FILE = "docs/retrofit-hook-test.md"
AGENT_TRAILER = "Co-Authored-By: Retrofit Hook Test <noreply@anthropic.com>"
REWRITTEN_TRAILER = "Generated-By: Retrofit Hook Test"
MESSAGE_HOOK_TYPES = ("prepare-commit-msg", "commit-msg")


def run_tool(
    cwd: Path, *command: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, cwd=cwd, input=stdin, text=True, capture_output=True, check=False
        )
    except FileNotFoundError as error:
        raise PreflightError(f"{command[0]} is required but was not found") from error


def hook_types(tree: Path) -> list[str]:
    """The hook types the destination's own helper reads from its config.

    Read through `pre_commit_hook_types` rather than parsed here, because it is
    what `pre_commit_hooks_missing` grades against: setting up from anything
    else passes setup and fails the grade once the config's list changes.
    """
    helper = tree / "scripts/libs/precommit.sh"
    if not helper.is_file():
        raise PreflightError(
            "the default branch ships no scripts/libs/precommit.sh to read the "
            "configured hook types from"
        )
    listed = run_tool(
        tree,
        "bash",
        "-c",
        'source "$1" && pre_commit_hook_types "$2"',
        "_",
        str(helper),
        ".pre-commit-config.yaml",
    )
    if listed.returncode != 0:
        raise PreflightError(f"could not read the hook types: {listed.stderr.strip()}")
    return listed.stdout.split()


def is_shim(path: Path) -> bool:
    return path.is_file() and SHIM_MARKER in path.read_text(errors="replace")


def global_hooks(tree: Path) -> list[Path]:
    configured = run_git(
        tree, "config", "--global", "--type=path", "core.hooksPath", check=False
    ).stdout.strip()
    if not configured:
        return []
    directory = Path(configured)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix != ".sample" and path.stat().st_mode & 0o111
    )


def duplicates_payload(hook: Path, tree: Path) -> bool:
    """Whether a global message hook does exactly what the payload's stage does.

    Only a message hook can be compared by outcome: both run on the same probe
    message and a duplicate is one that changes it, identically. Any other
    global hook is linked in, since keeping a hook the payload already covers
    costs a second run, and dropping one it does not costs the operator a check.
    """
    if hook.name not in MESSAGE_HOOK_TYPES:
        return False
    probe = f"chore: probe\n\n{AGENT_TRAILER}\n"
    scratch = tree / ".git-retrofit-probe"
    scratch.mkdir()
    try:
        theirs, ours = scratch / "global", scratch / "payload"
        theirs.write_text(probe)
        ours.write_text(probe)
        run_tool(tree, str(hook), str(theirs))
        run_tool(
            tree,
            "pre-commit",
            "run",
            "--hook-stage",
            hook.name,
            "--commit-msg-filename",
            str(ours),
        )
        rewritten = ours.read_text()
        return theirs.read_text() == rewritten != probe
    finally:
        shutil.rmtree(scratch)


def install_hooks(
    clone: Path, tree: Path, types: list[str]
) -> tuple[Path, list[dict[str, str]], list[dict[str, str]], list[str], bool]:
    """The lifecycle's recipe for a destination clone after the merge.

    `init-templatedir` installs with overwrite, and overwrite deletes
    `<type>.legacy` after moving any existing hook there, so a hook the clone
    already had is held under `<type>.held` across the install and only then
    put at `<type>.legacy`, where the shim chains it. Pinning `core.hooksPath`
    stops git reading the operator's global directory for this clone, so each
    global hook is linked back in, after the install for the same reason,
    unless it duplicates the payload's. The key is absolute because the clone
    has more than one worktree and a relative value resolves against each
    one's top.

    The last value says whether the hooks are in place to be tested.
    """
    common = Path(
        git_output(clone, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    hooks = common / "hooks"
    hooks.mkdir(exist_ok=True)
    found = global_hooks(tree)
    ours = {hook.resolve() for hook in found}
    findings: list[str] = []

    held: dict[str, Path] = {}
    for kind in types:
        current, legacy = hooks / kind, hooks / f"{kind}.legacy"
        candidates = [
            path
            for path in (current, legacy)
            if path.exists()
            and not is_shim(path)
            and not (path.is_symlink() and path.resolve() in ours)
        ]
        if len(candidates) > 1:
            findings.append(
                f"{current} and {legacy} are both the clone's own and the shim "
                "chains one; nothing was installed"
            )
        elif candidates and (hooks / f"{kind}.held").exists():
            findings.append(f"{hooks / kind}.held is left from an earlier run")
        elif candidates:
            held[kind] = candidates[0]
    if findings:
        return hooks, [], [], findings, False

    moved: list[dict[str, str]] = []
    for kind, path in held.items():
        path.rename(hooks / f"{kind}.held")
        moved.append({"type": kind, "from": str(path), "to": f"{hooks / kind}.legacy"})

    template = [argument for kind in types for argument in ("-t", kind)]
    installed = run_tool(tree, "pre-commit", "init-templatedir", *template, str(common))
    for kind in held:
        (hooks / f"{kind}.held").rename(hooks / f"{kind}.legacy")
    if installed.returncode != 0:
        findings.append(
            f"pre-commit init-templatedir failed: {installed.stderr.strip()}"
        )
        return hooks, moved, [], findings, False

    linked: list[dict[str, str]] = []
    for hook in found:
        if duplicates_payload(hook, tree):
            linked.append({"hook": str(hook), "disposition": "duplicate"})
            continue
        slot = hooks / (f"{hook.name}.legacy" if hook.name in types else hook.name)
        if slot.is_symlink() and slot.resolve() == hook.resolve():
            pass
        elif slot.exists() or slot.is_symlink():
            findings.append(f"{hook} was not linked in: {slot} is already taken")
            continue
        else:
            slot.symlink_to(hook)
        linked.append({"hook": str(hook), "disposition": "linked", "as": str(slot)})

    run_git(clone, "config", "--local", "core.hooksPath", str(hooks))

    # By outcome, not by the exit statuses above.
    resolved = Path(
        git_output(clone, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    )
    unready = [
        f"no {kind} shim in {hooks}" for kind in types if not is_shim(hooks / kind)
    ]
    if resolved != hooks:
        unready.append(f"git resolves the hooks at {resolved}, not {hooks}")
    return hooks, moved, linked, findings + unready, not unready


def attempt_commit(tree: Path, message: str) -> str | None:
    """The message a commit landed with, undone again, or None if refused.

    Undone with `--soft` so the test file stays staged for the next attempt and
    the tree is never left holding a commit its removal would have to force.
    """
    if run_git(tree, "commit", "-q", "-m", message, check=False).returncode != 0:
        return None
    landed = git_output(tree, "log", "-1", "--format=%B")
    run_git(tree, "reset", "-q", "--soft", "HEAD~1")
    return landed


def hook_outcomes(tree: Path, default_branch: str) -> dict[str, bool]:
    """The three refusals the destination will experience, in a throwaway tree.

    The trailer commit runs first, on the detached head, and must land: it is
    what shows the staged file and a well-formed message pass every hook, so
    the two refusals after it are the branch and the subject and nothing else.
    The test file sits under `docs/` because the structure audit refuses an
    unpermitted root file, which would refuse all three for the wrong reason.

    The default branch is stood in for by a per-worktree ref of the same name,
    `refs/worktree/<default>`. `no-commit-to-branch` reads only the name after
    the second slash of what HEAD points at, so it refuses this one exactly as
    it would the real branch, and a hook that fails to refuse advances a ref
    that leaves with the worktree rather than the clone's own default branch.
    """
    (tree / HOOK_TEST_FILE).write_text("Proves the hooks refuse and rewrite.\n")
    run_git(tree, "add", "--", HOOK_TEST_FILE)

    message = attempt_commit(tree, f"docs: prove the hooks run\n\n{AGENT_TRAILER}\n")
    trailer_rewritten = (
        message is not None
        and REWRITTEN_TRAILER in message
        and AGENT_TRAILER not in message
    )
    malformed_refused = (
        attempt_commit(tree, f"Not a conventional subject\n\n{AGENT_TRAILER}\n") is None
    )

    scratch_ref = f"refs/worktree/{default_branch}"
    run_git(tree, "update-ref", scratch_ref, "HEAD")
    run_git(tree, "symbolic-ref", "HEAD", scratch_ref)
    default_refused = (
        attempt_commit(tree, f"docs: commit to the default branch\n\n{AGENT_TRAILER}\n")
        is None
    )

    # Leave the tree as it was checked out, so its removal needs no force.
    run_git(tree, "reset", "-q", "--", HOOK_TEST_FILE)
    (tree / HOOK_TEST_FILE).unlink()
    return {
        "default_branch_refused": default_refused,
        "malformed_subject_refused": malformed_refused,
        "trailer_rewritten": trailer_rewritten,
    }


def hooks(arguments: argparse.Namespace) -> dict[str, object]:
    """Install the destination's hooks in the operator's clone, and prove them.

    Only where the merge was taken: the config this installs arrived with it.
    """
    clone = preflight.require_git_repository(arguments.clone, "clone")
    scratch = arguments.scratch.resolve()
    if scratch.exists():
        raise PreflightError(f"the throwaway worktree path already exists: {scratch}")
    branch = arguments.default_branch
    run_git(clone, "fetch", "-q", "origin", branch)
    base = preflight.resolve_commit(clone, f"origin/{branch}")
    if blob(clone, f"{base}:.pre-commit-config.yaml") is None:
        raise PreflightError(
            f"origin/{branch} carries no .pre-commit-config.yaml; install only "
            "after the merge has landed"
        )
    previous = run_git(clone, "config", "--local", "core.hooksPath", check=False)

    findings: list[str] = []
    run_git(clone, "worktree", "add", "-q", "--detach", str(scratch), base)
    try:
        types = hook_types(scratch)
        hooks_dir, moved, linked, installed, ready = install_hooks(
            clone, scratch, types
        )
        findings.extend(installed)
        checks = hook_outcomes(scratch, branch) if ready else {}
        findings.extend(
            f"outcome check failed: {name}"
            for name, passed in checks.items()
            if not passed
        )
    finally:
        removed = run_git(clone, "worktree", "remove", str(scratch), check=False)
    if removed.returncode != 0:
        findings.append(f"throwaway worktree not removed: {removed.stderr.strip()}")

    return {
        "operation": "hooks",
        "clone": {"path": str(clone), "default_branch": branch, "base": base},
        "hook_types": types,
        "hooks_path": str(hooks_dir),
        "previous_local_hooks_path": previous.stdout.strip() or None,
        "moved_aside": moved,
        "global_hooks": linked,
        "checks": checks,
        "worktree_removed": removed.returncode == 0,
        "findings": findings,
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

    install = subparsers.add_parser(
        "hooks", help="install and prove the hooks in the clone after the merge"
    )
    install.add_argument("--clone", type=Path, required=True)
    install.add_argument("--default-branch", required=True)
    install.add_argument(
        "--scratch",
        type=Path,
        required=True,
        help="where the throwaway worktree goes; must not exist",
    )
    install.set_defaults(handler=hooks)
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
