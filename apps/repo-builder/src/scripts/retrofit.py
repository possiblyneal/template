#!/usr/bin/env python3
"""Run the fixed steps of a retrofit and report each as JSON.

`preflight.py` is read-only by contract and only authorizes the next stage.
The steps here act on the candidate, the operator's clone, or the host, so
they live beside it rather than in it, and reuse its git helpers by import.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
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


def overrides(candidate: Path) -> list[dict[str, str]]:
    """The overridden paths the candidate's record carries, as written there."""
    record = candidate / ".repo-template.json"
    if not record.is_file():
        return []
    return json.loads(record.read_text()).get("generation", {}).get("overrides", [])


def emptied_directories(candidate: Path, removed: list[str]) -> list[dict[str, object]]:
    """Each topmost directory the staged removals leave with nothing tracked.

    Git tracks no directories, so the residue that holds one open after the
    merge is never in the candidate's diff: it is untracked or ignored output
    in the operator's clone, read from there while the tracked file still
    names it.
    """
    emptied: set[str] = set()
    for path in removed:
        parent = Path(path).parent
        while parent != Path("."):
            if not git_output(candidate, "ls-files", "--", str(parent)):
                emptied.add(str(parent))
            parent = parent.parent
    topmost = sorted(
        path
        for path in emptied
        if not any(path.startswith(f"{other}/") for other in emptied)
    )
    common = Path(
        git_output(candidate, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    clone = common.parent
    return [
        {
            "path": path,
            "residue": [
                entry[3:]
                for entry in nul_fields(
                    clone,
                    "status",
                    "--ignored",
                    "--untracked-files=all",
                    "--porcelain",
                    "-z",
                    "--",
                    path,
                )
                if entry.startswith(("!! ", "?? "))
            ],
        }
        for path in topmost
    ]


# `pull_request` outside a comment and not as `pull_request_target`, whose run
# reads the base branch's workflow rather than this pull request's.
PULL_REQUEST_TRIGGER = re.compile(r"^[^#\n]*\bpull_request\b", re.MULTILINE)


def workflows_without_pull_request(candidate: Path) -> list[str]:
    """Workflows no pull-request event triggers, so its checks never exercise them."""
    return sorted(
        str(path.relative_to(candidate))
        for path in (candidate / ".github/workflows").glob("*.y*ml")
        if not PULL_REQUEST_TRIGGER.search(path.read_text())
    )


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

    overridden = overrides(candidate)
    overridden_set = {entry["path"] for entry in overridden}
    identical = applied = unchanged = 0
    differing: list[dict[str, object]] = []
    missing: list[str] = []
    preserved: list[str] = []
    replaced: list[str] = []
    for path in payload:
        # Settled once already, so neither proof measures it.
        if path in overridden_set:
            continue
        if not (candidate / path).is_file():
            missing.append(path)
            continue
        expected = blob(template, f"{target}:{prefix}/{path}")
        actual = git_output(candidate, "hash-object", "--", path)
        at_base = blob(candidate, f"{base}:{path}") is not None
        if path not in staged and path not in excluded:
            # Untouched since the base: the destination's version stands.
            if actual != expected:
                preserved.append(path)
            else:
                unchanged += 1
            continue
        # An ignored copy is on disk only, so it is no path the branch writes.
        if not at_base and path not in excluded:
            applied += 1
        if actual == expected:
            identical += 1
            # The destination's own version is gone, though the copy is exact.
            if at_base:
                replaced.append(path)
            continue
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
    # A move edited past git's rename threshold lands here as a deletion,
    # with its new path under `authored`.
    deleted = sorted(paths[0] for status, paths in changes if status == "D")
    return {
        "operation": "proofs",
        "template": {"commit": target, "subtree": subtree},
        "candidate": {
            "path": str(candidate),
            "base": base,
            "pre_commit_config": (candidate / ".pre-commit-config.yaml").is_file(),
        },
        "payload_total": len(payload),
        "applied": applied,
        "unchanged": unchanged,
        "preserved": preserved,
        "replaced": replaced,
        "overridden": overridden,
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
        "deleted": deleted,
        "emptied": emptied_directories(
            candidate, deleted + [str(move["from"]) for move in moves]
        ),
        "workflows_without_pull_request": workflows_without_pull_request(candidate),
    }


# The payload's hooks that rewrite a file rather than judge it. Run before the
# proofs, so a move the hooks would otherwise edit at commit time is measured
# as the commit will carry it.
NORMALIZING_HOOKS = (
    "trailing-whitespace",
    "end-of-file-fixer",
    "mixed-line-ending",
    "adr-index",
)


def staged_paths(candidate: Path) -> list[str]:
    return nul_fields(
        candidate, "diff", "--cached", "--name-only", "--diff-filter=d", "-z"
    )


def index_entries(candidate: Path, paths: list[str]) -> dict[str, tuple[str, str]]:
    """Each path's mode and blob as the index holds them."""
    entries = {}
    for entry in nul_fields(candidate, "ls-files", "-s", "-z", "--", *paths):
        meta, path = entry.split("\t", 1)
        mode, object_id, _ = meta.split(" ")
        entries[path] = (mode, object_id)
    return entries


def untracked(candidate: Path) -> set[str]:
    return set(
        nul_fields(candidate, "ls-files", "--others", "--exclude-standard", "-z")
    )


def restage_rewritten(candidate: Path, untracked_before: set[str]) -> list[str]:
    # A hook can write a file from nothing, as adr-index does its index; an
    # untracked file it did not write is the bar's to dispose, not this step's.
    rewritten = nul_fields(candidate, "diff", "--name-only", "-z") + sorted(
        untracked(candidate) - untracked_before
    )
    if rewritten:
        run_git(candidate, "add", "--", *rewritten)
    return rewritten


def normalize(arguments: argparse.Namespace) -> dict[str, object]:
    """Give the staged candidate the line endings, modes and whitespace it commits with.

    Every rewrite here is one the destination's own attributes or hooks make
    at the first commit anyway; made after the proofs, it lands as an edit
    to a move the rename-purity proof already called byte-identical.
    """
    candidate = preflight.require_git_repository(arguments.candidate, "candidate")
    paths = staged_paths(candidate)
    if not paths:
        raise PreflightError(
            "nothing is staged; stage the candidate before normalizing"
        )

    before = index_entries(candidate, paths)
    run_git(candidate, "add", "--renormalize", "--", *paths)
    after = index_entries(candidate, paths)
    renormalized = [path for path in paths if before[path][1] != after[path][1]]

    # A text file with no shebang has nothing to execute it; a binary, read
    # as git does by a NUL in its first 8000 bytes, may be a real program.
    cleared = []
    for path, (mode, _) in after.items():
        file = candidate / path
        head = file.read_bytes()[:8000]
        if mode == "100755" and not head.startswith(b"#!") and b"\0" not in head:
            file.chmod(file.stat().st_mode & ~0o111)
            cleared.append(path)
    if cleared:
        # `add` skips a mode change where `core.fileMode` is false.
        run_git(candidate, "update-index", "--chmod=-x", "--", *cleared)

    config = candidate / ".pre-commit-config.yaml"
    configured = config.read_text() if config.is_file() else ""
    hook_ids = [
        hook
        for hook in NORMALIZING_HOOKS
        if re.search(
            rf"^\s*(?:-\s*)?id:\s*([\"']?){re.escape(hook)}\1\s*(?:#.*)?$",
            configured,
            re.MULTILINE,
        )
    ]
    untracked_before = untracked(candidate)
    rewritten: list[str] = []
    still_failing: list[str] = []
    failed = []
    for hook in hook_ids:
        if run_tool(candidate, "pre-commit", "run", hook, "--files", *paths).returncode:
            failed.append(hook)
    rewritten += restage_rewritten(candidate, untracked_before)
    # A rewriting hook fails the run that rewrites; only a second failure is a finding.
    for hook in failed:
        if run_tool(candidate, "pre-commit", "run", hook, "--files", *paths).returncode:
            still_failing.append(hook)
    rewritten += restage_rewritten(candidate, untracked_before)

    return {
        "operation": "normalize",
        "candidate": str(candidate),
        "renormalized": renormalized,
        "executable_cleared": cleared,
        "hooks_run": hook_ids,
        "rewritten": sorted(set(rewritten)),
        "still_failing": still_failing,
    }


# The payload's `scripts/run` and `scripts/package` both open with this when a
# unit has no manifest, and both exit zero.
NO_MANIFEST = "No project manifest found"


def tail(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def executed_fact(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    output = result.stdout + result.stderr
    return {
        "exit": result.returncode,
        "tail": tail(output),
        "no_manifest": NO_MANIFEST in output,
    }


def facts(arguments: argparse.Namespace) -> dict[str, object]:
    """Execute each unit's declared run and ship facts once.

    Neither command is in the check surface, so a declaration contradicting
    the tree passes every capability and fails the first time it is used.
    `scripts/run` and `scripts/package` report a unit with no manifest and
    exit zero, which is why their output is read rather than their status.
    """
    candidate = preflight.require_git_repository(arguments.candidate, "candidate")
    shipped = all(
        (candidate / "scripts" / name).is_file() for name in ("package", "run")
    )
    declarations = sorted(candidate.glob("apps/*/.unit.json")) if shipped else []
    units = []
    for declaration in declarations:
        unit = declaration.parent.name
        packaged = run_tool(candidate, "scripts/package", unit)
        ran = run_tool(
            candidate, "scripts/run", unit, env={**os.environ, "CI_DRY_RUN": "1"}
        )
        units.append(
            {
                "unit": unit,
                "package": executed_fact(packaged),
                "run": executed_fact(ran),
            }
        )
    return {
        "operation": "facts",
        "candidate": str(candidate),
        "shipped": shipped,
        "units": units,
    }


def worktree_state(candidate: Path) -> str:
    return run_git(candidate, "diff", "HEAD").stdout


def autofix(arguments: argparse.Namespace) -> dict[str, object]:
    """Run the destination's own autofix over the committed candidate.

    At most two passes, and a second only where the first changed something:
    the order is lint then format, so a layout change can expose a finding
    the linter never saw. A payload copy the pass rewrote is a payload
    defect, reverted so the copy proof stays true of the branch.
    """
    template = preflight.require_git_repository(arguments.template_repo, "template")
    target = preflight.resolve_commit(template, arguments.target)
    subtree = preflight.normalize_relative_path(arguments.subtree, "template subtree")
    candidate = preflight.require_git_repository(arguments.candidate, "candidate")
    if git_output(candidate, "status", "--porcelain", "--untracked-files=no"):
        raise PreflightError(
            "the candidate has uncommitted changes; commit this flow's own work "
            "before the pass, so the pass commits by itself"
        )
    if not (candidate / "scripts/fix").is_file():
        return {"operation": "autofix", "candidate": str(candidate), "shipped": False}

    passes = 0
    status = 0
    while passes < 2:
        before = worktree_state(candidate)
        status = run_tool(candidate, "scripts/fix").returncode
        passes += 1
        if worktree_state(candidate) == before:
            break

    prefix = subtree.rstrip("/")
    rewritten = nul_fields(candidate, "diff", "--name-only", "-z", "HEAD")
    reverted = [
        path
        for path in rewritten
        if blob(candidate, f"HEAD:{path}")
        == blob(template, f"{target}:{prefix}/{path}")
    ]
    if reverted:
        run_git(candidate, "restore", "--", *reverted)
    return {
        "operation": "autofix",
        "candidate": str(candidate),
        "shipped": True,
        "passes": passes,
        "exit_status": status,
        "rewritten": [path for path in rewritten if path not in reverted],
        "reverted": reverted,
    }


SHIM_MARKER = "File generated by pre-commit"
HOOK_TEST_FILE = "docs/retrofit-hook-test.md"
AGENT_TRAILER = "Co-Authored-By: Retrofit Hook Test <noreply@anthropic.com>"
REWRITTEN_TRAILER = "Generated-By: Retrofit Hook Test"
MESSAGE_HOOK_TYPES = ("prepare-commit-msg", "commit-msg")


def run_tool(
    cwd: Path,
    *command: str,
    stdin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            env=env,
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


def executable_hooks(directory: Path) -> list[Path]:
    """The hooks git would run from a directory, leaving out pre-commit's shims."""
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix != ".sample"
        and path.stat().st_mode & 0o111
        and not is_shim(path)
    )


def prior_hooks(clone: Path) -> dict[str, str]:
    """The directory git ran the clone's hooks from, and the scope that chose it.

    `--git-path hooks` resolves `core.hooksPath` as git does when it runs a
    hook: local over global, and the clone's own `hooks` directory where no
    scope sets it.
    """
    shown = run_git(
        clone, "config", "--show-scope", "--get", "core.hooksPath", check=False
    ).stdout
    return {
        "scope": shown.split("\t", 1)[0] if shown else "default",
        "path": git_output(
            clone, "rev-parse", "--path-format=absolute", "--git-path", "hooks"
        ),
    }


def duplicates_payload(hook: Path, tree: Path) -> bool:
    """Whether a chained message hook does exactly what the payload's stage does.

    Only a message hook can be compared by outcome: both run on the same probe
    message and a duplicate is one that changes it, identically. Any other
    hook is linked in, since keeping a hook the payload already covers costs a
    second run, and dropping one it does not costs the operator a check.
    """
    if hook.name not in MESSAGE_HOOK_TYPES:
        return False
    probe = f"chore: probe\n\n{AGENT_TRAILER}\n"
    scratch = tree / ".git-retrofit-probe"
    scratch.mkdir()
    try:
        theirs, ours = scratch / "prior", scratch / "payload"
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


@dataclass(frozen=True)
class Installed:
    """What `install_hooks` did to the clone's hooks directory."""

    hooks_dir: Path
    moved: list[dict[str, str]]
    chained: list[dict[str, str]]
    findings: list[str]
    # Whether the hooks are in place to be tested.
    ready: bool


def install_hooks(clone: Path, tree: Path, types: list[str], prior: Path) -> Installed:
    """The lifecycle's recipe for a destination clone after the merge.

    `prior` is the directory git ran the clone's hooks from before the key is
    pinned, and only its hooks are chained under the shims. Where that is the
    clone's own directory, `init-templatedir` installs with overwrite, and
    overwrite deletes `<type>.legacy` after moving any existing hook there, so
    each hook is held under `<type>.held` across the install and only then put
    at `<type>.legacy`, where the shim chains it. Where it is another directory,
    each of its hooks is linked in after the install for the same reason, unless
    it duplicates the payload's, and the clone's own hooks, which git was not
    running, are renamed `<name>.dormant` so pinning the key does not start
    them. The key is absolute because the clone has more than one worktree and
    a relative value resolves against each one's top.
    """
    common = Path(
        git_output(clone, "rev-parse", "--path-format=absolute", "--git-common-dir")
    )
    hooks = common / "hooks"
    hooks.mkdir(exist_ok=True)
    chain = executable_hooks(prior) if prior != hooks else []
    linked_in = {hook.resolve() for hook in chain}
    own = [
        path
        for path in sorted(hooks.iterdir())
        if (path.is_file() or path.is_symlink())
        and not is_shim(path)
        and not (path.is_symlink() and path.resolve() in linked_in)
    ]
    findings: list[str] = []

    # Each hook to move before the install, and where it ends up after it.
    aside: dict[Path, tuple[Path, Path]] = {}
    if prior == hooks:
        for kind in types:
            current, legacy = hooks / kind, hooks / f"{kind}.legacy"
            held = hooks / f"{kind}.held"
            candidates = [path for path in (current, legacy) if path in own]
            if len(candidates) > 1:
                findings.append(
                    f"{current} and {legacy} are both the clone's own and the shim "
                    "chains one; nothing was installed"
                )
            elif candidates and held.exists():
                findings.append(f"{held} is left from an earlier run")
            elif candidates:
                aside[candidates[0]] = (held, legacy)
    else:
        legacies = {f"{kind}.legacy" for kind in types}
        for path in own:
            runs = (
                "." not in path.name and path.is_file() and path.stat().st_mode & 0o111
            )
            if not runs and path.name not in legacies:
                continue
            dormant = path.with_name(f"{path.name}.dormant")
            if dormant.exists() or dormant.is_symlink():
                findings.append(f"{dormant} is left from an earlier run")
            else:
                aside[path] = (dormant, dormant)
    if findings:
        return Installed(hooks, [], [], findings, False)

    moved: list[dict[str, str]] = []
    for path, (during, after) in aside.items():
        path.rename(during)
        moved.append({"from": str(path), "to": str(after)})

    template = [argument for kind in types for argument in ("-t", kind)]
    installed = run_tool(tree, "pre-commit", "init-templatedir", *template, str(common))
    for during, after in aside.values():
        if during != after:
            during.rename(after)
    if installed.returncode != 0:
        findings.append(
            f"pre-commit init-templatedir failed: {installed.stderr.strip()}"
        )
        return Installed(hooks, moved, [], findings, False)

    chained: list[dict[str, str]] = []
    for hook in chain:
        if duplicates_payload(hook, tree):
            chained.append({"hook": str(hook), "disposition": "duplicate"})
            continue
        slot = hooks / (f"{hook.name}.legacy" if hook.name in types else hook.name)
        if slot.is_symlink() and slot.resolve() == hook.resolve():
            pass
        elif slot.exists() or slot.is_symlink():
            findings.append(f"{hook} was not linked in: {slot} is already taken")
            continue
        else:
            slot.symlink_to(hook)
        chained.append({"hook": str(hook), "disposition": "linked", "as": str(slot)})

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
    return Installed(hooks, moved, chained, findings + unready, not unready)


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
    landed = message is not None
    malformed_refused = (
        landed
        and attempt_commit(tree, f"Not a conventional subject\n\n{AGENT_TRAILER}\n")
        is None
    )

    scratch_ref = f"refs/worktree/{default_branch}"
    run_git(tree, "update-ref", scratch_ref, "HEAD")
    run_git(tree, "symbolic-ref", "HEAD", scratch_ref)
    default_refused = (
        landed
        and attempt_commit(
            tree, f"docs: commit to the default branch\n\n{AGENT_TRAILER}\n"
        )
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
    The merge has landed once `.repo-template.json` is on the default branch,
    and refusing otherwise. A landed default branch with no
    `.pre-commit-config.yaml` records `not-applicable`.
    """
    clone = preflight.require_git_repository(arguments.clone, "clone")
    scratch = arguments.scratch.resolve()
    if scratch.exists():
        raise PreflightError(f"the throwaway worktree path already exists: {scratch}")
    branch = arguments.default_branch
    run_git(clone, "fetch", "-q", "origin", branch)
    base = preflight.resolve_commit(clone, f"origin/{branch}")
    if blob(clone, f"{base}:.repo-template.json") is None:
        raise PreflightError(
            f"origin/{branch} carries no .repo-template.json; install only "
            "after the merge has landed"
        )
    if blob(clone, f"{base}:.pre-commit-config.yaml") is None:
        # A landed merge whose payload ships no hooks leaves nothing to install.
        return {
            "operation": "hooks",
            "outcome": "not-applicable",
            "reason": "the default branch carries no .pre-commit-config.yaml",
        }
    # Unobservable once the key is pinned, so a resumed run reads it back.
    record = arguments.resume_record
    recorded = json.loads(record.read_text()) if record.exists() else {}
    if not isinstance(recorded, dict):
        raise PreflightError(f"the resume record holds no JSON object: {record}")
    prior = recorded.get("prior_hooks")
    if not isinstance(prior, dict):
        prior = prior_hooks(clone)
        recorded["prior_hooks"] = prior
        record.write_text(json.dumps(recorded, indent=2) + "\n")

    findings: list[str] = []
    run_git(clone, "worktree", "add", "-q", "--detach", str(scratch), base)
    try:
        types = hook_types(scratch)
        installed = install_hooks(clone, scratch, types, Path(prior["path"]))
        findings.extend(installed.findings)
        checks = hook_outcomes(scratch, branch) if installed.ready else {}
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
        "hooks_path": str(installed.hooks_dir),
        "prior_hooks": prior,
        "moved_aside": installed.moved,
        "chained": installed.chained,
        "checks": checks,
        "worktree_removed": removed.returncode == 0,
        "findings": findings,
    }


PULL_REQUESTS_NOT_APPLICABLE = {
    "outcome": "not-applicable",
    "reason": "origin is a local path, not a GitHub repository",
}


def is_github_slug(clone: Path, repository: str) -> bool:
    """Whether `--repository` is `owner/name`, rather than the origin path.

    An owner is letters, digits and hyphens, so `../origin` and `./origin`
    fail the pattern; `remote/x` passes it and is a path only if it exists,
    resolved from the clone as git resolves a relative remote.
    """
    slug = r"[A-Za-z0-9][A-Za-z0-9-]*/(?!\.\.?$)[\w.-]+"
    return (
        re.fullmatch(slug, repository) is not None and not (clone / repository).exists()
    )


def pull_requests(clone: Path, repository: str, branch: str) -> list[object] | None:
    """Every pull request whose head is the branch, or None when unreadable."""
    owner = repository.split("/", 1)[0]
    listed = run_tool(
        clone,
        "gh",
        "api",
        f"repos/{repository}/pulls?head={owner}:{branch}&state=all",
        "--jq",
        "[.[] | {number, state, merged: (.merged_at != null), url: .html_url}]",
    )
    if listed.returncode != 0:
        return None
    return json.loads(listed.stdout)


def sweep(arguments: argparse.Namespace) -> dict[str, object]:
    """Take down what the flow created, in the order each stage needs.

    Nothing is forced. Each refusal is a finding and stops the stages that
    depend on it: a worktree git will not remove keeps its hooks directory,
    its resume record and its branch, because it may still be resumed from.
    """
    clone = preflight.require_git_repository(arguments.clone, "clone")
    candidate = arguments.candidate.resolve()
    branch, default = arguments.branch, arguments.default_branch
    scratch: dict[str, Path] = {
        stage: path
        for stage in ("hooks_dir", "resume_record")
        if (path := getattr(arguments, stage)) is not None
    }
    scratch["write_log"] = write_log_path(arguments.records)
    stages: dict[str, str] = {}
    findings: list[str] = []

    def refused(stage: str, result: subprocess.CompletedProcess[str]) -> bool:
        if result.returncode == 0:
            stages[stage] = "done"
            return False
        stages[stage] = "refused"
        detail = result.stderr.strip() or result.stdout.strip()
        findings.append(f"{stage} refused: {detail}")
        return True

    # Refreshes the remote-tracking ref the containment test reads; the build
    # fetch at step 2 aimed the worktree and is stale by now.
    fetch_refused = refused(
        "fetch", run_git(clone, "fetch", "-q", "origin", default, check=False)
    )

    # Ignored output does not block the removal; a file some step wrote and no
    # step committed does, and the destination's own clean reaches it only
    # where its ignore rules do not cover it.
    if not candidate.is_dir():
        stages["clean"] = stages["worktree"] = "absent"
    elif not (candidate / "scripts/clean").is_file():
        stages["clean"] = "not shipped"
    else:
        refused("clean", run_tool(candidate, "scripts/clean"))
    worktree_refused = False
    if candidate.is_dir():
        worktree_refused = refused(
            "worktree",
            run_git(clone, "worktree", "remove", str(candidate), check=False),
        )
    if not worktree_refused:
        refused("prune", run_git(clone, "worktree", "prune", check=False))

    # The hooks directory, the record and the write log are siblings of the
    # candidate rather than files in it, so the removal above does not take them.
    for stage, path in scratch.items():
        if worktree_refused:
            stages[stage] = "skipped"
        elif not path.exists():
            stages[stage] = "absent"
        else:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            stages[stage] = "removed"

    # `branch -d` compares against an upstream or HEAD, never against the
    # fetched default branch, so the ancestry test is the containment guard
    # and `-d` the second line behind it.
    exists = blob(clone, f"refs/heads/{branch}") is not None
    if not exists:
        stages["branch"] = "absent"
    elif worktree_refused or fetch_refused:
        stages["branch"] = "skipped"
    elif (
        run_git(
            clone,
            "merge-base",
            "--is-ancestor",
            branch,
            f"origin/{default}",
            check=False,
        ).returncode
        != 0
    ):
        stages["branch"] = "kept"
    else:
        refused("branch", run_git(clone, "branch", "-d", branch, check=False))
        if stages["branch"] == "done":
            stages["branch"] = "deleted"

    left: list[dict[str, object]] = []
    on_github = is_github_slug(clone, arguments.repository)
    for name in git_output(
        clone, "branch", "--list", "--format=%(refname:short)", "retrofit/*"
    ).splitlines():
        if name == branch and stages["branch"] == "skipped":
            reason = "left standing with its worktree, which can still be resumed"
        elif name == branch and stages["branch"] == "refused":
            reason = f"contained in origin/{default}, but `branch -d` refused it"
        elif name == branch:
            reason = f"not contained in origin/{default}, so its merge was declined"
        else:
            reason = "an earlier run at another payload commit"
        if not on_github:
            left.append({"branch": name, "reason": reason, "pull_requests": []})
            continue
        requests = pull_requests(clone, arguments.repository, name)
        if requests is None:
            findings.append(f"could not read the pull requests for {name}")
        left.append({"branch": name, "reason": reason, "pull_requests": requests})

    record: dict[str, object] = {
        "operation": "sweep",
        "clone": {"path": str(clone), "default_branch": default},
        "candidate": {"path": str(candidate), "branch": branch},
        "scratch": {stage: str(path) for stage, path in scratch.items()},
        "stages": stages,
        "left_for_the_operator": left,
        "findings": findings,
    }
    if not on_github:
        record["pull_requests"] = PULL_REQUESTS_NOT_APPLICABLE
    return record


MERGE_SETTINGS = {
    "allow_merge_commit": True,
    "allow_squash_merge": False,
    "allow_rebase_merge": False,
    "delete_branch_on_merge": True,
}
UPGRADE_MESSAGE = "Upgrade to GitHub"


class Outcome(StrEnum):
    """What one approved hosted write came to."""

    DONE = "done"
    ALREADY_SET = "already set"
    # Performed by an earlier run, so not performed again.
    LOGGED = "logged"
    NOT_OFFERED = "not offered"
    PERMISSIONS_GAP = "permissions gap"
    REFUSED = "refused"


class Refusal(Exception):
    """The host answered a request with an error rather than a body."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(f"{message} (HTTP {status})")
        self.status = status
        self.message = message

    @property
    def outcome(self) -> Outcome:
        """An upgrade message means the plan lacks the feature; any other 403
        means this credential does, which is a different finding."""
        if self.status == "403" and self.message.startswith(UPGRADE_MESSAGE):
            return Outcome.NOT_OFFERED
        if self.status == "403":
            return Outcome.PERMISSIONS_GAP
        return Outcome.REFUSED


class Unoffered(Exception):
    """A write whose own precondition does not hold here, so it is not offered."""


def gh(*arguments: str) -> object:
    """A `gh` call's JSON body, or a Refusal carrying the host's status.

    `gh api` prints GitHub's error document to stdout and exits 1 on any HTTP
    error, so the body is read either way and its status tells a 404 from a
    403, the same reading `scripts/repo-settings` makes.
    """
    called = run_tool(Path.cwd(), "gh", *arguments)
    try:
        body = json.loads(called.stdout) if called.stdout.strip() else None
    except json.JSONDecodeError:
        body = None
    if called.returncode == 0:
        return body
    if isinstance(body, dict):
        raise Refusal(str(body.get("status", "")), str(body.get("message", "")))
    raise Refusal("", called.stderr.strip() or "gh printed no JSON")


def gh_object(*arguments: str) -> dict[str, object]:
    """A `gh` call whose body must be a JSON object."""
    body = gh(*arguments)
    if not isinstance(body, dict):
        raise PreflightError(f"`gh {shlex.join(arguments)}` answered no JSON object")
    return body


def lookup(document: object, *path: str) -> object:
    """A nested JSON field, or None where any step along the path is absent."""
    for key in path:
        if not isinstance(document, dict):
            return None
        document = document.get(key)
    return document


def read_repository(repository: str) -> dict[str, object]:
    return gh_object("api", f"repos/{repository}")


def push_protection_status(repo: dict[str, object]) -> object:
    """None where the key is absent: only an admin is shown it at all."""
    return lookup(
        repo, "security_and_analysis", "secret_scanning_push_protection", "status"
    )


def label_names(repository: str) -> list[str]:
    listed = gh("api", "--paginate", f"repos/{repository}/labels")
    if not isinstance(listed, list):
        raise PreflightError(f"repos/{repository}/labels answered no JSON list")
    return [str(lookup(label, "name")) for label in listed]


def refused_reading(refusal: Refusal) -> dict[str, str]:
    """A reading the host refused, in the reading's place."""
    return {"refused": refusal.outcome, "detail": str(refusal)}


def gh_or_refusal(*arguments: str) -> object:
    """A reading, or the refusal's outcome in its place."""
    try:
        return gh(*arguments)
    except Refusal as refusal:
        return refused_reading(refusal)


def enabled_by_status(endpoint: str) -> object:
    """An endpoint that answers 204 when a feature is on and 404 when it is off."""
    try:
        gh("api", endpoint)
    except Refusal as refusal:
        if refusal.status == "404":
            return False
        return refused_reading(refusal)
    return True


def runner_status(repository: str) -> object:
    name = f"dev-{repository.split('/', 1)[1]}"
    try:
        runners = gh_object("api", f"repos/{repository}/actions/runners")
    except Refusal as refusal:
        return refused_reading(refusal)
    listed = runners.get("runners")
    for runner in listed if isinstance(listed, list) else []:
        if lookup(runner, "name") == name:
            return lookup(runner, "status")
    return "absent"


def hosted_read(arguments: argparse.Namespace) -> dict[str, object]:
    """Everything the hosted-write gate's question is built from, in one call."""
    repository = arguments.repository
    try:
        repo = read_repository(repository)
    except Refusal as refusal:
        raise PreflightError(f"{repository} cannot be read: {refusal}") from refusal
    admin = lookup(repo, "permissions", "admin")
    # Absent for a plan that does not offer it, "unavailable" for one that
    # offers it only on another visibility.
    push_protection = push_protection_status(repo)
    if push_protection is None and admin:
        push_protection = "not offered"
    try:
        labels: object = label_names(repository)
    except Refusal as refusal:
        labels = refused_reading(refusal)
    rulesets = gh_or_refusal("api", f"repos/{repository}/rulesets")
    return {
        "operation": "hosted read",
        "repository": repository,
        "visibility": repo.get("visibility"),
        "admin": admin,
        "default_branch": repo.get("default_branch"),
        "merge_settings": {setting: repo.get(setting) for setting in MERGE_SETTINGS},
        "labels": labels,
        "dependabot": {
            "alerts": enabled_by_status(f"repos/{repository}/vulnerability-alerts"),
            "security_updates": gh_or_refusal(
                "api", f"repos/{repository}/automated-security-fixes"
            ),
        },
        "push_protection": "not offered"
        if push_protection == "unavailable"
        else push_protection,
        "rulesets": [
            {
                key: lookup(ruleset, key)
                for key in ("id", "name", "target", "enforcement")
            }
            for ruleset in rulesets
        ]
        if isinstance(rulesets, list)
        else rulesets,
        "runner": runner_status(repository),
    }


class WriteLog:
    """The resume record's write list: one entry per hosted write performed.

    A write's before-state is unobservable once it has landed, so a write
    already logged is never repeated: repeating it would log the applied value
    as the one to restore.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: list[dict[str, object]] = (
            json.loads(path.read_text()) if path.exists() else []
        )

    def logged(self, write: str) -> bool:
        return any(entry["write"] == write for entry in self.entries)

    def append(
        self, write: str, before: object, after: object, reverse: list[str]
    ) -> None:
        self.entries.append(
            {
                "write": write,
                "before": before,
                "after": after,
                "reverse_command": reverse,
            }
        )
        self.path.write_text(json.dumps(self.entries, indent=2) + "\n")


def flags(values: Mapping[str, object]) -> list[str]:
    flagged: list[str] = []
    for setting, value in values.items():
        flagged += ["-F", f"{setting}={json.dumps(value)}"]
    return flagged


def write_merge_settings(repository: str, log: WriteLog) -> Outcome:
    """The four in one PATCH: sent apart, the host can refuse the second after
    the first has landed, and refuses outright to leave no merge method."""
    repo = read_repository(repository)
    before = {setting: repo.get(setting) for setting in MERGE_SETTINGS}
    if before == MERGE_SETTINGS:
        return Outcome.ALREADY_SET
    gh("api", "-X", "PATCH", f"repos/{repository}", *flags(MERGE_SETTINGS))
    log.append(
        "merge-settings",
        before,
        MERGE_SETTINGS,
        ["gh", "api", "-X", "PATCH", f"repos/{repository}", *flags(before)],
    )
    return Outcome.DONE


@dataclass
class LabelOutcome:
    """Each label approved, under what it came to, in the order they landed."""

    created: list[str] = field(default_factory=list)
    renamed: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)


def write_labels(
    repository: str, names: list[str], rename: bool, log: WriteLog
) -> LabelOutcome:
    """Create what is missing; the host matches names case-insensitively, so a
    case variant is renamed to the given spelling, or kept where `rename` is off
    because the destination's own vocabulary file is the one in force."""
    existing = {name.casefold(): name for name in label_names(repository)}
    outcome = LabelOutcome()
    for name in names:
        try:
            write_label(repository, name, existing, rename, log, outcome)
        except Refusal as refusal:
            # Stop at the first: what landed before it is kept in the outcome.
            outcome.refused.append(
                {"label": name, "outcome": refusal.outcome, "reason": str(refusal)}
            )
            break
    return outcome


def write_label(
    repository: str,
    name: str,
    existing: Mapping[str, str],
    rename: bool,
    log: WriteLog,
    outcome: LabelOutcome,
) -> None:
    """One label, its outcome recorded in `outcome` as it lands."""
    write = f"label:{name}"
    present = existing.get(name.casefold())
    if log.logged(write) or present == name:
        outcome.skipped.append({"label": name, "reason": "exists"})
    elif present is not None and not rename:
        outcome.skipped.append({"label": name, "reason": f"exists as {present}, kept"})
    elif present is not None:
        quoted = urllib.parse.quote(present, safe="")
        gh(
            "api",
            "-X",
            "PATCH",
            f"repos/{repository}/labels/{quoted}",
            "-f",
            f"new_name={name}",
        )
        log.append(
            write,
            present,
            name,
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/{repository}/labels/{urllib.parse.quote(name, safe='')}",
                "-f",
                f"new_name={present}",
            ],
        )
        outcome.renamed.append({"from": present, "to": name})
    else:
        gh("api", "-X", "POST", f"repos/{repository}/labels", "-f", f"name={name}")
        log.append(
            write,
            None,
            name,
            [
                "gh",
                "api",
                "-X",
                "DELETE",
                f"repos/{repository}/labels/{urllib.parse.quote(name, safe='')}",
            ],
        )
        outcome.created.append(name)


def write_toggle(write: str, endpoint: str, log: WriteLog) -> Outcome:
    """A feature switched on by PUT and off by DELETE on the same endpoint."""
    try:
        answer = gh("api", endpoint)
    except Refusal as refusal:
        if refusal.status != "404":
            raise
        answer = False
    # vulnerability-alerts answers 204 with no body when on and 404 when off;
    # automated-security-fixes answers a body that names its state.
    before = answer.get("enabled") if isinstance(answer, dict) else answer is None
    if before:
        return Outcome.ALREADY_SET
    gh("api", "-X", "PUT", endpoint)
    log.append(write, False, True, ["gh", "api", "-X", "DELETE", endpoint])
    return Outcome.DONE


def write_push_protection(repository: str, log: WriteLog) -> Outcome:
    key = "security_and_analysis[secret_scanning_push_protection][status]"
    repo = read_repository(repository)
    before = push_protection_status(repo)
    if before == "enabled":
        return Outcome.ALREADY_SET
    if before is None and not lookup(repo, "permissions", "admin"):
        raise Refusal("403", "push protection status is not shown to this credential")
    if before in (None, "unavailable"):
        raise Refusal("403", f"{UPGRADE_MESSAGE}: push protection is not offered")
    gh("api", "-X", "PATCH", f"repos/{repository}", "-f", f"{key}=enabled")
    log.append(
        "push-protection",
        before,
        "enabled",
        ["gh", "api", "-X", "PATCH", f"repos/{repository}", "-f", f"{key}={before}"],
    )
    return Outcome.DONE


# What a ruleset GET returns and its PUT does not take back.
RULESET_READ_ONLY = (
    "id",
    "node_id",
    "_links",
    "created_at",
    "updated_at",
    "source",
    "source_type",
    "current_user_can_bypass",
)


def write_ruleset(
    repository: str, body: Path, replaces: int | None, log: WriteLog
) -> Outcome:
    """Create the ruleset, or repair the destination's own in place.

    The body is the flow's to compose from the references, since which contexts
    it requires and which branch it names are judgements this command does not
    make. A ruleset replaced keeps its before-state beside the log, because the
    command that restores it needs the whole document as its input.
    """
    if replaces is None:
        created = gh_object(
            "api", "-X", "POST", f"repos/{repository}/rulesets", "--input", str(body)
        )
        log.append(
            "ruleset",
            None,
            created["id"],
            [
                "gh",
                "api",
                "-X",
                "DELETE",
                f"repos/{repository}/rulesets/{created['id']}",
            ],
        )
        return Outcome.DONE
    endpoint = f"repos/{repository}/rulesets/{replaces}"
    before = gh_object("api", endpoint)
    restorable = {
        key: value for key, value in before.items() if key not in RULESET_READ_ONLY
    }
    saved = log.path.with_name(f"{log.path.stem}.ruleset-{replaces}.json")
    saved.write_text(json.dumps(restorable, indent=2) + "\n")
    gh("api", "-X", "PUT", endpoint, "--input", str(body))
    log.append(
        "ruleset",
        str(saved),
        str(body),
        ["gh", "api", "-X", "PUT", endpoint, "--input", str(saved)],
    )
    return Outcome.DONE


def write_runner_variable(repository: str, log: WriteLog) -> Outcome:
    """Set only where the repository is private and its runner reads online,
    both read here rather than trusted from the gate's snapshot."""
    visibility = read_repository(repository).get("visibility")
    if visibility != "private":
        raise Unoffered(f"the repository is {visibility}")
    runner = runner_status(repository)
    if runner != "online":
        raise Unoffered(f"the dev runner is {runner}")
    try:
        value = gh_object("api", f"repos/{repository}/actions/variables/RUNNER").get(
            "value"
        )
        before = value if isinstance(value, str) else None
    except Refusal as refusal:
        if refusal.status != "404":
            raise
        before = None
    if before == "self-hosted":
        return Outcome.ALREADY_SET
    run = ["variable", "set", "RUNNER", "--body", "self-hosted", "-R", repository]
    gh(*run)
    log.append(
        "runner-variable",
        before,
        "self-hosted",
        ["gh", "variable", "delete", "RUNNER", "-R", repository]
        if before is None
        else ["gh", "variable", "set", "RUNNER", "--body", before, "-R", repository],
    )
    return Outcome.DONE


@dataclass(frozen=True)
class HostedWrite:
    """One write the gate can approve."""

    name: str
    # Its line under Repository settings; labels report on a line of their own.
    setting: str | None
    perform: Callable[[argparse.Namespace, WriteLog], Outcome | LabelOutcome]


# In the gate's order, which is the order `apply` performs them in.
HOSTED_WRITES = (
    HostedWrite(
        "merge-settings",
        "Merge settings (merge commit only, head branches deleted)",
        lambda arguments, log: write_merge_settings(arguments.repository, log),
    ),
    HostedWrite(
        "labels",
        None,
        lambda arguments, log: write_labels(
            arguments.repository,
            arguments.label,
            not arguments.keep_case_variants,
            log,
        ),
    ),
    HostedWrite(
        "dependabot-alerts",
        "Dependabot alerts",
        lambda arguments, log: write_toggle(
            "dependabot-alerts",
            f"repos/{arguments.repository}/vulnerability-alerts",
            log,
        ),
    ),
    HostedWrite(
        "security-updates",
        "Dependabot security updates",
        lambda arguments, log: write_toggle(
            "security-updates",
            f"repos/{arguments.repository}/automated-security-fixes",
            log,
        ),
    ),
    HostedWrite(
        "push-protection",
        "Push protection",
        lambda arguments, log: write_push_protection(arguments.repository, log),
    ),
    HostedWrite(
        "ruleset",
        "Branch ruleset",
        lambda arguments, log: write_ruleset(
            arguments.repository, arguments.ruleset, arguments.replace_ruleset, log
        ),
    ),
    HostedWrite(
        "runner-variable",
        "Runner variable",
        lambda arguments, log: write_runner_variable(arguments.repository, log),
    ),
)


def hosted_apply(arguments: argparse.Namespace) -> dict[str, object]:
    """Perform the writes the gate approved, in the gate's order, and no others.

    There is no default-branch write here: the rename is a hard stop when
    declined and repairs every clone, so it stays a step the flow runs itself.
    A write approved later in the run, such as the runner variable once its
    runner comes online, is a second call; what the earlier call recorded for
    the writes this one does not approve is kept, so the report sees both.
    """
    approved = set(arguments.approve)
    earlier = arguments.previous
    if "labels" in approved and not arguments.label:
        raise PreflightError("labels approved with no --label to create")
    if "ruleset" in approved and arguments.ruleset is None:
        raise PreflightError("ruleset approved with no --ruleset body")
    log = WriteLog(write_log_path(arguments.records))
    writes: dict[str, object] = {}
    reasons: dict[str, str] = {}
    findings: list[str] = []
    for write in HOSTED_WRITES:
        if write.name not in approved:
            if write.name in earlier.get("writes", {}):
                writes[write.name] = earlier["writes"][write.name]
                if write.name in earlier.get("reasons", {}):
                    reasons[write.name] = earlier["reasons"][write.name]
                findings.extend(
                    finding
                    for finding in earlier.get("findings", [])
                    if finding.startswith(f"{write.name}: ")
                )
            continue
        if write.name != "labels" and log.logged(write.name):
            writes[write.name] = Outcome.LOGGED
            continue
        try:
            outcome = write.perform(arguments, log)
        except Unoffered as unoffered:
            outcome = Outcome.NOT_OFFERED
            reasons[write.name] = str(unoffered)
        except Refusal as refusal:
            outcome = refusal.outcome
            if outcome != Outcome.NOT_OFFERED:
                reasons[write.name] = str(refusal)
                findings.append(f"{write.name}: {refusal}")
        if isinstance(outcome, LabelOutcome):
            findings.extend(
                f"{write.name}: {item['reason']}"
                for item in outcome.refused
                if item["outcome"] != Outcome.NOT_OFFERED
            )
            writes[write.name] = asdict(outcome)
        else:
            writes[write.name] = outcome
    return {
        "operation": "hosted apply",
        "repository": arguments.repository,
        "writes": writes,
        "reasons": reasons,
        "write_log": {"path": str(log.path), "entries": log.entries},
        "findings": findings,
    }


SUMMARY_ROW = re.compile(
    r"^([A-Za-z0-9_-]+) +(pass|not-applicable|unavailable|FAIL|would-run)(?: +(.*))?$"
)
# `scripts/summarize`'s line for a non-zero exit with no failing row.
UNLISTED_FAILURE = re.compile(r"^(.+ exited \d+) with no failing result line")


class Report:
    """The final report's lines, with every judgement left as a marked slot."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.slots: list[str] = []

    def fill(self, what: str) -> str:
        self.slots.append(what)
        return f"[[FILL: {what}]]"

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)

    def section(self, heading: str) -> None:
        self.lines += ["", heading]


@dataclass(frozen=True)
class Row:
    """One `scripts/summarize` result row, with the findings indented under it."""

    check: str
    state: str
    detail: str
    findings: list[str]


def read_summary(path: Path) -> list[Row]:
    """`scripts/summarize` rows: a state line, then the findings indented under it.

    A command that exited non-zero with every row passing fails as a row of its
    own, since the saved summary is the only place its exit status survives.
    """
    rows: list[Row] = []
    for line in path.read_text().splitlines():
        matched = SUMMARY_ROW.match(line)
        unlisted = UNLISTED_FAILURE.match(line)
        if matched:
            check, state, detail = matched.groups()
            rows.append(Row(check, state, detail or "", []))
        elif unlisted:
            exited = unlisted.group(1)
            rows.append(
                Row(
                    "exit-status",
                    "FAIL",
                    exited,
                    [f"{exited} outside the Result table"],
                )
            )
        elif line[:1].isspace() and line.strip() and rows:
            rows[-1].findings.append(line.strip())
    return rows


def failing(rows: list[Row]) -> list[Row]:
    return [row for row in rows if row.state in ("FAIL", "unavailable")]


def command_result(rows: list[Row]) -> str:
    failed = [row.check for row in rows if row.state == "FAIL"]
    if failed:
        return f"fail ({', '.join(failed)})"
    unavailable = [f"{row.check}: {row.detail}" for row in failing(rows)]
    if unavailable:
        return f"unavailable ({'; '.join(unavailable)})"
    return "pass"


def joined(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def record_path(prefix: Path, suffix: str) -> Path:
    return prefix.with_name(f"{prefix.name}.{suffix}")


def write_log_path(prefix: Path) -> Path:
    """Hosted apply's log of each write's before-state, which a resumed run reads."""
    return record_path(prefix, "writes.json")


def required_record(prefix: Path, suffix: str) -> Path:
    path = record_path(prefix, suffix)
    if not path.is_file():
        raise PreflightError(f"{path} is missing; the step that writes it has not run")
    return path


def load_required(prefix: Path, name: str) -> dict:
    return json.loads(required_record(prefix, f"{name}.json").read_text())


def write_entries(apply_record: dict) -> list[dict]:
    return apply_record.get("write_log", {}).get("entries", [])


def load(prefix: Path, name: str) -> dict:
    """The JSON object a step recorded, or an empty one where it did not run."""
    path = record_path(prefix, f"{name}.json")
    if not path.is_file():
        return {}
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise PreflightError(f"{path} holds no JSON object")
    return document


# The candidate branch's sweep stage, as the Cleanup line reads it.
BRANCH_FATES = {
    "kept": "kept for the pull request still open",
    "absent": "already absent",
    "refused": "standing, because `branch -d` refused it",
    "skipped": "standing, because the containment test could not run",
}


def header(report: Report, arguments: argparse.Namespace, proofs: dict) -> None:
    report.add(
        "## Repo Builder Result",
        "",
        f"- Status: stopped ({arguments.stopped})"
        if arguments.stopped
        else "- Status: finished",
        "- Operation: retrofit",
        f"- Pull request: {arguments.pull_request or 'not created'}",
        f"- Template: not previously generated -> {proofs['template']['commit']}",
        f"- Destination: {arguments.repository}",
    )


def merged_paths(proofs: dict) -> list[str]:
    """Payload paths the destination already held, merged rather than copied."""
    return [
        item["path"]
        for item in proofs["copy"]["differing"]
        if item["class"] == "merged"
    ]


def conflicted_line(report: Report, proofs: dict) -> str:
    merged = merged_paths(proofs)
    if not merged:
        return "- Conflicted: none"
    return (
        f"- Conflicted: {', '.join(merged)}, each merged; "
        f"{report.fill('the competing intents each merge settled')}"
    )


def reconciliation(report: Report, proofs: dict) -> None:
    fill = report.fill
    moves = proofs["rename_purity"]["moves"]
    renamed = [f"{move['from']} -> {move['to']}" for move in moves]
    deleted = [f"{path} deleted" for path in proofs["deleted"]]
    report.section("### Reconciliation")
    report.add(
        f"- Applied: {proofs['applied']} payload paths, written because the destination lacked them",
        f"- Preserved: {joined(proofs['preserved'])}",
        f"- Renamed/deleted: {joined(renamed + deleted)}",
        conflicted_line(report, proofs),
        f"- Superseded: {fill('each superseded path, what it did and what carries it now, or none')}",
        f"- Partially covered, not cut: {fill('script paths and the parts already covered, or none')}",
        "- Overridden: "
        + joined(
            [f"{entry['path']} ({entry['reason']})" for entry in proofs["overridden"]]
        ),
    )
    if moves:
        report.add(
            *(f"- Layout plan: {move['from']} -> {move['to']}: moved" for move in moves)
        )
    report.add(
        f"- Layout plan: {fill('each move the operator corrected or declined, or delete this line')}"
        if moves
        else "- Layout plan: none",
        f"- Unmovable: {fill('each path that could not move and why, or none')}",
        f"- Data split: {fill('each data file, read to assets/ or written to state/, and the live copy the operator carries, or none')}",
        f"- References repaired: {fill('each file and the moved path rewritten in it, or none')}",
        f"- References reported, not rewritten: {fill('each file and the prose describing the old structure, or none')}",
        f"- Ignore rules the payload does not cover: {fill('each rule and what it ignored, or none')}",
    )


def application_boundaries(report: Report, proofs: dict) -> None:
    fill = report.fill
    records = [
        path
        for path in proofs["authored"]
        if path.startswith("docs/adrs/") and path != "docs/adrs/index.md"
    ]
    report.section("### Application boundaries")
    report.add(
        f"- ADRs written: {joined(records)}",
        f"- ADR fields defaulted: {fill('each ADR path and field set to the payload template default, or none')}",
        f"- Unit map: {fill('one line per unit, in the Report additions shape')}",
        f"- Ships nothing for want of an adapter: {fill('unit and language, or none')}",
        f"- Declared but not built: {fill('deployable, its descriptor and owning unit, or none')}",
    )


def file_list(report: Report, proofs: dict) -> None:
    authored = [
        f"{item['path']} ({item['class']})" for item in proofs["copy"]["differing"]
    ]
    authored += list(proofs["authored"])
    authored += [
        f"{move['to']} (moved from {move['from']}, +{move['added']}/-{move['removed']})"
        for move in proofs["rename_purity"]["moves"]
        if not move["identical"]
    ]
    copy = proofs["copy"]
    report.section("### File list")
    report.add(
        f"- Payload paths: {proofs['payload_total']}, the placeholder unit left out: "
        f"{copy['identical']} byte-identical copies, {proofs['unchanged']} already "
        f"identical in the destination, {len(copy['differing'])} authored, "
        f"{len(proofs['preserved'])} preserved, {len(proofs['overridden'])} overridden; "
        f"missing: {joined(copy['missing'])}",
        f"- Authored surface: {joined(authored)}",
    )


def addon_adoption(report: Report, preflight_result: dict) -> None:
    held = preflight_result.get("addons_present")
    report.section("### Addon adoption")
    report.add(
        f"- Already held: {joined(held)}"
        if held is not None
        else f"- Already held: {report.fill('addon-shaped paths the destination brought with it, or none')}"
    )


def setting_line(
    name: str, outcome: object, reason: str | None, gate_reached: bool
) -> str:
    if outcome in (Outcome.DONE, Outcome.ALREADY_SET, Outcome.LOGGED):
        return f"- {name}: enabled"
    if not gate_reached:
        return f"- {name}: not reached (stopped before the gate)"
    if outcome is None:
        return f"- {name}: not requested"
    if outcome == Outcome.NOT_OFFERED:
        return f"- {name}: unavailable ({reason or 'not offered for the plan'})"
    return f"- {name}: unavailable ({outcome})"


def labels_line(report: Report, labels: object) -> str:
    if not isinstance(labels, dict):
        return f"none created ({report.fill('reason no labels were created')})"
    parts = []
    if labels["created"]:
        parts.append(f"created ({', '.join(labels['created'])})")
    if labels["renamed"]:
        renames = ", ".join(
            f"{item['from']} -> {item['to']}" for item in labels["renamed"]
        )
        parts.append(
            f"renamed to the payload's spelling ({renames}; label search is "
            "case-sensitive, so anything pinned to the old string stops matching)"
        )
    if labels["skipped"]:
        parts.append(
            f"already present ({', '.join(item['label'] for item in labels['skipped'])})"
        )
    parts += [
        f"refused at {item['label']} ({item['outcome']}), the rest not attempted"
        for item in labels.get("refused", [])
    ]
    return "; ".join(parts)


def repository_settings(
    report: Report, hosted_state: dict, apply_record: dict, stopped: str | None
) -> None:
    writes, reasons = apply_record.get("writes", {}), apply_record.get("reasons", {})
    # The gate opens with `hosted read`, so its JSON marks a run that reached
    # the gate even where it stopped there with nothing applied.
    gate_reached = bool(hosted_state or apply_record) or not stopped
    report.section("### Repository settings")
    report.add(
        f"- Destination visibility: {hosted_state.get('visibility') or report.fill('public or private, read from the API')}"
    )
    for write in HOSTED_WRITES:
        if write.setting is not None:
            report.add(
                setting_line(
                    write.setting,
                    writes.get(write.name),
                    reasons.get(write.name),
                    gate_reached,
                )
            )
    labels = labels_line(report, writes.get("labels"))
    report.add(
        f"- Issue tracker: {report.fill('tracker, recorded in docs/agents/issue-tracker.md, shipped by the payload or kept from the destination')}; labels: {labels}"
    )


def reversible_writes(report: Report, entries: list[dict]) -> None:
    report.section("### Hosted writes, reversible")
    for entry in entries:
        report.add(
            f"- {entry['write']}: was {json.dumps(entry['before'])} -> "
            f"{json.dumps(entry['after'])}; reverse with `{shlex.join(entry['reverse_command'])}`"
        )
    report.add(
        f"- {report.fill('each write the operator declined, with the reason, recorded in generation.features; or delete this line')}"
    )
    if not entries:
        report.add("- none performed")


def ruleset_enforcement(
    report: Report, outcome: object, pull_request: str | None
) -> str:
    """Step 8 proves nothing here; step 9's reading of the pull request does."""
    if outcome not in (Outcome.DONE, Outcome.LOGGED):
        return "n/a (no ruleset written)"
    if pull_request is None:
        return "not yet proven at the gate, and no pull request opened to prove it"
    return report.fill(
        "step 9's mergeable/mergeStateStatus reading of the pull request"
    )


def irreversible_writes(
    report: Report, apply_record: dict, pull_request: str | None
) -> None:
    writes, reasons = apply_record.get("writes", {}), apply_record.get("reasons", {})
    gaps = [
        f"{write}: {reasons[write]}"
        for write, outcome in writes.items()
        if outcome == Outcome.PERMISSIONS_GAP
    ]
    labels = writes.get("labels")
    if isinstance(labels, dict):
        gaps += [
            f"labels: {item['reason']}"
            for item in labels.get("refused", [])
            if item["outcome"] == Outcome.PERMISSIONS_GAP
        ]
    report.section("### Hosted writes, irreversible")
    report.add(
        f"- {report.fill('each irreversible write, its before-state, applied value and cost; or none')}",
        f"- Ruleset enforcement: {ruleset_enforcement(report, writes.get('ruleset'), pull_request)}",
        f"- Permissions gap: {'; '.join(gaps) if gaps else 'none'}",
    )


def bar_lines(report: Report, summaries: list[tuple[str, list[Row]]]) -> list[str]:
    failures = [row for _, rows in summaries for row in failing(rows)]
    if not failures:
        return ["- Bar: met"]
    unmet = "; ".join(
        f"{row.check}: {'fail' if row.state == 'FAIL' else 'unavailable'}"
        + (f" ({row.detail})" if row.state == "unavailable" else "")
        for row in failures
    )
    return [
        f"- Bar: UNMET: {unmet}; stopped before the pull request, zero hosted writes performed",
        f"- Destination fix prepared: {report.fill('the unmet-bar outcome, in the Report additions shape')}",
        f"- Destination fix published: {report.fill('the unmet-bar outcome, in the Report additions shape')}",
    ]


def destination_hooks_line(hooks_result: dict, stopped: str | None) -> str:
    if not hooks_result:
        if stopped:
            return "- Destination hooks after merge: n/a (stopped before the merge was offered)"
        return "- Destination hooks after merge: n/a (merge declined)"
    if hooks_result.get("outcome") == "not-applicable":
        return (
            "- Destination hooks after merge: n/a "
            "(no hooks config on the default branch)"
        )
    moved_aside = [
        f"{item['from']} -> {item['to']}" for item in hooks_result["moved_aside"]
    ]
    prior = hooks_result["prior_hooks"]
    chained = [
        f"{item['hook']} {item['disposition']}"
        + (f" as {item['as']}" if item.get("as") else "")
        for item in hooks_result["chained"]
    ]
    checks = hooks_result["checks"]
    observed = [name for name, held in checks.items() if held]
    failed = [name for name, held in checks.items() if not held]
    return (
        f"- Destination hooks after merge: shims in {hooks_result['hooks_path']}, "
        f"`core.hooksPath` pinned local to it, prior hooks: {prior['path']} "
        f"({prior['scope']}), moved aside: {joined(moved_aside)}, "
        f"chained: {joined(chained)}, verified by {joined(observed)}"
        + (f"; NOT observed: {', '.join(failed)}" if failed else "")
    )


def verification(
    report: Report,
    arguments: argparse.Namespace,
    proofs: dict,
    summaries: list[tuple[str, list[Row]]],
    hooks_result: dict,
    swept: dict,
    executed: dict,
    fixed: dict,
) -> None:
    fill = report.fill
    copy, purity = proofs["copy"], proofs["rename_purity"]
    report.section("### Verification")
    for command, rows in summaries:
        report.add(f"- `{command}`: {command_result(rows)}")
        for row in failing(rows):
            report.add(*(f"  - {row.check}: {finding}" for finding in row.findings))
    report.add(
        candidate_hooks_line(report, proofs, swept),
        f"- Copied paths byte-identical to their source: {copy['identical']}/{copy['total']}; "
        "the rest are the authored surface, under File list. An overridden path is "
        "in neither count, under Reconciliation instead",
        f"- Workflows the pull-request event never ran: {joined(proofs['workflows_without_pull_request'])}",
        f"- Code review: {fill('the axes that ran over the authored surface, the findings corrected or recorded as incorrectly identified, and the Reviewed-Head sha, or why no sign-off was written')}",
        f"- Default branch after merge: {fill('check-suite result')}"
        if hooks_result
        else "- Default branch after merge: n/a (nothing merged)",
        f"- Moved paths byte-identical to their pre-move blob: {purity['identical']}/{purity['total']}",
        f"- Directories emptied by a move: {emptied_line(proofs['emptied'])}",
        f"- Untracked at the bar: {fill('none, or the paths and how they were disposed')}",
        f"- Declared facts executed: {facts_line(executed)}",
        f"- Tool declaration: {fill('per manifest, what was added, kept or declined')}",
        f"- Configuration boundary: {fill('one row per language')}",
        f"- Autofix: {autofix_line(report, fixed)}",
        f"- Autofix settings resolution: {fill('every tool resolved inside the candidate, or SKIPPED and why')}",
        f"- Payload paths the autofix rewrote: {reverted_line(report, fixed)}",
    )
    report.add(*bar_lines(report, summaries))
    report.add(destination_hooks_line(hooks_result, arguments.stopped))


def emptied_line(emptied: list[dict]) -> str:
    return joined(
        [
            f"{item['path']}: held open by {', '.join(item['residue'])}, which is the "
            "destination's own and is left in place, named under Left for the operator"
            if item["residue"]
            else f"{item['path']}: gone after the merge"
            for item in emptied
        ]
    )


def facts_line(executed: dict) -> str:
    if not executed:
        return "not executed"
    if not executed["shipped"]:
        return "the payload ships neither command, so both facts are written and unexecuted"

    def outcome(result: dict, passed: str) -> str:
        if result["exit"]:
            return f"fail ({result['tail']})"
        return f"does nothing ({result['tail']})" if result["no_manifest"] else passed

    return "; ".join(
        f"{unit['unit']}: `scripts/package` {outcome(unit['package'], 'pass')}, "
        f"`scripts/run` {outcome(unit['run'], 'pass under CI_DRY_RUN')}"
        for unit in executed["units"]
    )


def autofix_line(report: Report, fixed: dict) -> str:
    if not fixed:
        return "no pass ran"
    if not fixed["shipped"]:
        return (
            "the payload ships no `scripts/fix`, so the bar was measured without a pass"
        )
    passes = f"{fixed['passes']} pass{'es' if fixed['passes'] > 1 else ''}"
    remaining = (
        "; findings it could not fix remained for the bar"
        if fixed["exit_status"]
        else ""
    )
    if not fixed["rewritten"]:
        return f"nothing rewritten outside the payload ({passes}){remaining}"
    return (
        f"`scripts/fix` rewrote {', '.join(fixed['rewritten'])} in {passes}, "
        f"committed by itself in {report.fill('the commit sha')}{remaining}"
    )


def reverted_line(report: Report, fixed: dict) -> str:
    reverted = fixed.get("reverted", [])
    if not reverted:
        return "none"
    return (
        f"{', '.join(reverted)}, reverted in the candidate and reported as a payload "
        f"defect; {report.fill('the rule or formatter that rewrote each')}"
    )


def candidate_hooks_line(report: Report, proofs: dict, swept: dict) -> str:
    if not proofs["candidate"]["pre_commit_config"]:
        return (
            "- Hooks: none installed, because the candidate carries no "
            "`.pre-commit-config.yaml` to read hook types from"
        )
    hooks_dir = swept.get("scratch", {}).get("hooks_dir")
    clone = swept.get("clone", {}).get("path")
    return (
        f"- Hooks: installed at worktree scope into {hooks_dir or report.fill('the candidate hooks directory')}; "
        f"`extensions.worktreeConfig` set on {clone or report.fill('the clone')} and left set"
    )


def candidate_line(report: Report, swept: dict) -> str:
    if not swept:
        return f"- Candidate: left standing at {report.fill('candidate path')}, because the flow stopped and resumes from it"
    candidate, stages = swept["candidate"], swept["stages"]
    if stages.get("worktree") not in ("done", "absent"):
        return f"- Candidate: left standing at {candidate['path']}, because its removal was refused"
    if stages.get("branch") == "deleted":
        return f"- Candidate: removed from {candidate['path']}, branch {candidate['branch']} deleted"
    return (
        f"- Candidate: worktree removed from {candidate['path']}, branch "
        f"{candidate['branch']} {BRANCH_FATES[stages.get('branch')]}"
    )


def cleanup(report: Report, swept: dict, hooks_result: dict, proofs: dict) -> None:
    report.section("### Cleanup")
    report.add(candidate_line(report, swept))
    if swept:
        scratch = [
            f"{path}: {swept['stages'].get(stage)}"
            for stage, path in swept.get("scratch", {}).items()
        ]
        report.add(f"- Scratch outside the candidate: {joined(scratch)}")
    left = [
        f"{item['branch']}: {item['reason']}"
        + "".join(
            f"; pull request {request['url']} ({'merged' if request['merged'] else request['state']})"
            for request in item["pull_requests"] or []
        )
        for item in swept.get("left_for_the_operator", [])
    ]
    left += [str(finding) for finding in swept.get("findings", [])]
    if swept.get("pull_requests", {}).get("outcome") == "not-applicable":
        left.append(f"pull requests: n/a ({swept['pull_requests']['reason']})")
    left += [str(finding) for finding in hooks_result.get("findings", [])]
    left += [
        f"{item['path']}: {', '.join(item['residue'])}, untracked residue a move left"
        for item in proofs["emptied"]
        if item["residue"]
    ]
    others = report.fill(
        "any other path left in place and why, or delete this entry"
        if left
        else "each path left in place and why, or none"
    )
    report.add(f"- Left for the operator: {'; '.join([*left, others])}")


def resumption(report: Report, writes: dict) -> None:
    fill = report.fill
    logged = [write for write, outcome in writes.items() if outcome == Outcome.LOGGED]
    report.section("### Resumption")
    report.add(
        f"- Re-observed as already done: {fill('what live state showed complete')}",
        f"- Taken from the resume record: hosted writes {joined(logged)}; {fill('the issues and decisions read back')}",
        f"- Redone: {fill('anything performed again and why, or none')}",
        f"- Retries: {fill('transient failures retried and their outcomes, or none')}",
    )


def render_report(arguments: argparse.Namespace) -> dict[str, object]:
    """Render the deterministic lines of a retrofit's final report.

    The shape is reporting.md's Final report with retrofit-report.md's lines in
    place. Every count, setting, write, check result and cleanup outcome is
    read from the records the other steps wrote; everything the flow decided
    or judged is a `[[FILL: ...]]` slot for the session to fill.
    """
    prefix = arguments.records
    proofs = load_required(prefix, "proofs")
    summaries = [("scripts/check", read_summary(required_record(prefix, "check.txt")))]
    hooks_result = load(prefix, "hooks")
    swept = load(prefix, "sweep")
    apply_record = load(prefix, "hosted-apply")
    report = Report()
    header(report, arguments, proofs)
    reconciliation(report, proofs)
    application_boundaries(report, proofs)
    file_list(report, proofs)
    addon_adoption(report, load(prefix, "preflight"))
    repository_settings(
        report, load(prefix, "hosted-read"), apply_record, arguments.stopped
    )
    reversible_writes(report, write_entries(apply_record))
    irreversible_writes(report, apply_record, arguments.pull_request)
    verification(
        report,
        arguments,
        proofs,
        summaries,
        hooks_result,
        swept,
        load(prefix, "facts"),
        load(prefix, "autofix"),
    )
    cleanup(report, swept, hooks_result, proofs)
    if arguments.resumed:
        resumption(report, apply_record.get("writes", {}))
    report.section("### Pending action")
    report.add(
        report.fill("the exact decision or authorization needed")
        if arguments.stopped
        else "none"
    )

    output = record_path(prefix, "report.md")
    output.write_text("\n".join(report.lines) + "\n")
    return {"operation": "report", "path": str(output), "slots": report.slots}


def proof_lines(
    report: Report, proofs: dict, normalized: dict, executed: dict, fixed: dict
) -> list[str]:
    copy, purity = proofs["copy"], proofs["rename_purity"]
    lines = [
        f"- Copied paths byte-identical to the payload: {copy['identical']}/{copy['total']}",
        f"- Moved paths byte-identical to their pre-move blob: {purity['identical']}/{purity['total']}",
    ]
    if normalized:
        lines.append(
            f"- Normalized before measuring: {len(normalized['renormalized'])} renormalized, "
            f"{len(normalized['executable_cleared'])} executable bits cleared, "
            f"rewritten by {joined(normalized['hooks_run'])}: {joined(normalized['rewritten'])}"
        )
    lines += [
        f"- Declared facts executed: {facts_line(executed)}",
        f"- Autofix: {autofix_line(report, fixed)}",
    ]
    return lines


def data_risk(proofs: dict) -> str:
    merged = merged_paths(proofs)
    found = [
        *([f"deleted: {', '.join(proofs['deleted'])}"] if proofs["deleted"] else []),
        *([f"merged over: {', '.join(merged)}"] if merged else []),
        *(
            [f"replaced by the payload: {', '.join(proofs['replaced'])}"]
            if proofs["replaced"]
            else []
        ),
    ]
    return f"yes — {'; '.join(found)}" if found else "no"


def rollback_lines(entries: list[dict]) -> list[str]:
    if not entries:
        return ["Revert the merge commit. No hosted setting was written."]
    return [
        "Revert the merge commit, then restore each hosted setting:",
        "",
        "```",
        *(shlex.join(entry["reverse_command"]) for entry in entries),
        "```",
    ]


def render_pr_body(arguments: argparse.Namespace) -> dict[str, object]:
    """Fill the payload's pull-request template from the records.

    The headings are the payload's `.github/PULL_REQUEST_TEMPLATE.md`, which a
    test holds this to. What the records settle is written; the summary, the
    decisions and the scope are `[[FILL: ...]]` slots.
    """
    prefix = arguments.records
    proofs = load_required(prefix, "proofs")
    check = required_record(prefix, "check.txt").read_text().rstrip()
    entries = write_entries(load(prefix, "hosted-apply"))
    report = Report()
    fill = report.fill
    report.add(
        "## Summary",
        "",
        fill("what the retrofit changed and why, in two or three sentences"),
    )
    report.section("## Linked issue or goal")
    report.add(
        "",
        "none — goal: bring this repository under the repository template at "
        f"{proofs['template']['commit'][:12]}, recorded in `.repo-template.json`, "
        "so later template changes reach it by update",
    )
    report.section("## Verification")
    report.add(
        "",
        "Evidence link: the checks on this pull request, and `scripts/check` on the candidate:",
        "",
        "```",
        check,
        "```",
        "",
        *proof_lines(
            report,
            proofs,
            load(prefix, "normalize"),
            load(prefix, "facts"),
            load(prefix, "autofix"),
        ),
        "",
        "Not verified:",
        "",
        f"- Workflows with no `pull_request` trigger, which this pull request never ran: "
        f"{joined(proofs['workflows_without_pull_request'])}",
        f"- {fill('anything else not exercised, or nothing')}",
    )
    report.section("## Risk")
    report.add(
        "",
        "Answer each. These are checkable against the diff.",
        "",
        f"- Database migration or schema change: {fill('yes / no')}",
        f"- Authentication, authorization, or permission logic touched: {fill('yes / no')}",
        "- Secrets, credentials, or security config touched: yes — the payload adds "
        "gitleaks, a dependency audit, CodeQL and Dependabot",
        f"- Public API, CLI, or on-disk format changed in a way existing callers would notice: {fill('yes / no')}",
        f"- Dependencies added, removed, or upgraded: {fill('yes / no')}",
        f"- Deletes or overwrites existing data: {data_risk(proofs)}",
        "",
        fill(
            "for every yes, what specifically changed and what happens if it is wrong"
        ),
        "",
        "Rollback:",
        "",
        *rollback_lines(entries),
    )
    report.section("## Decisions a reviewer should check")
    report.add(
        "", fill("the unit map, each conflict settled and each override, with why")
    )
    report.section("## Scope")
    report.add(
        "", fill("anything touched beyond the payload and the moves it required")
    )
    report.section("## Screenshots or demos")
    report.add("", "N/A")
    report.section("## Checklist")
    report.add(
        "",
        "- [ ] Verification section links a CI run or contains raw output.",
        '- [ ] Every "yes" under Risk is explained.',
        "- [ ] Decisions section lists real judgment calls, or the change genuinely had none.",
        "- [ ] No secrets, tokens, passwords, or private data in the diff or in this description.",
    )

    output = record_path(prefix, "pr-body.md")
    output.write_text("\n".join(report.lines) + "\n")
    return {"operation": "pr-body", "path": str(output), "slots": report.slots}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Every step's JSON lands at `<prefix>.<record>.json`, where the report
    # and the pull-request body find it without a flag per file.
    recorded = argparse.ArgumentParser(add_help=False)
    recorded.add_argument(
        "--records",
        type=Path,
        required=True,
        help="the run's record prefix, tmp/<repo>.<commit>",
    )

    def payload_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--template-repo", type=Path, required=True)
        command.add_argument("--target", required=True, help="template ref or commit")
        command.add_argument("--subtree", required=True)

    measure = subparsers.add_parser(
        "proofs",
        parents=[recorded],
        help="measure the copy and rename-purity proofs from the index",
    )
    payload_arguments(measure)
    measure.add_argument("--candidate", type=Path, required=True)
    measure.add_argument(
        "--base",
        required=True,
        help="the destination commit the candidate branched from",
    )
    measure.set_defaults(handler=proofs, record="proofs")

    normalized = subparsers.add_parser(
        "normalize",
        parents=[recorded],
        help="renormalize, clear stray executable bits and run the rewriting hooks",
    )
    normalized.add_argument("--candidate", type=Path, required=True)
    normalized.set_defaults(handler=normalize, record="normalize")

    executed = subparsers.add_parser(
        "facts", parents=[recorded], help="package and dry-run every declared unit"
    )
    executed.add_argument("--candidate", type=Path, required=True)
    executed.set_defaults(handler=facts, record="facts")

    fixed = subparsers.add_parser(
        "autofix",
        parents=[recorded],
        help="run scripts/fix over the committed candidate",
    )
    payload_arguments(fixed)
    fixed.add_argument("--candidate", type=Path, required=True)
    fixed.set_defaults(handler=autofix, record="autofix")

    install = subparsers.add_parser(
        "hooks",
        parents=[recorded],
        help="install and prove the hooks in the clone after the merge",
    )
    install.add_argument("--clone", type=Path, required=True)
    install.add_argument("--default-branch", required=True)
    install.add_argument(
        "--resume-record",
        type=Path,
        required=True,
        help="where the prior hooks directory is recorded before the key is pinned",
    )
    install.add_argument(
        "--scratch",
        type=Path,
        required=True,
        help="where the throwaway worktree goes; must not exist",
    )
    install.set_defaults(handler=hooks, record="hooks")

    teardown = subparsers.add_parser(
        "sweep",
        parents=[recorded],
        help="remove what the flow created, forcing nothing",
    )
    teardown.add_argument("--clone", type=Path, required=True)
    teardown.add_argument("--candidate", type=Path, required=True)
    teardown.add_argument("--branch", required=True, help="the retrofit branch")
    teardown.add_argument("--default-branch", required=True)
    teardown.add_argument(
        "--repository", required=True, help="owner/name, or the origin path"
    )
    teardown.add_argument("--hooks-dir", type=Path, help="the candidate's own")
    teardown.add_argument("--resume-record", type=Path)
    teardown.set_defaults(handler=sweep, record="sweep")

    hosted = subparsers.add_parser(
        "hosted", help="read the gate's snapshot, or perform the approved writes"
    )
    hosted_commands = hosted.add_subparsers(dest="hosted_command", required=True)
    read = hosted_commands.add_parser(
        "read", parents=[recorded], help="snapshot the hosted state"
    )
    read.add_argument("--repository", required=True, help="owner/name")
    read.set_defaults(handler=hosted_read, record="hosted-read")
    apply = hosted_commands.add_parser(
        "apply", parents=[recorded], help="perform the approved writes"
    )
    apply.add_argument("--repository", required=True, help="owner/name")
    apply.add_argument(
        "--approve",
        action="append",
        choices=[write.name for write in HOSTED_WRITES],
        default=[],
        required=True,
    )
    apply.add_argument("--label", action="append", default=[])
    apply.add_argument(
        "--keep-case-variants",
        action="store_true",
        help="the destination's own label vocabulary is the one in force",
    )
    apply.add_argument("--ruleset", type=Path, help="the ruleset body, as JSON")
    apply.add_argument(
        "--replace-ruleset", type=int, help="the id of a ruleset to repair in place"
    )
    apply.set_defaults(handler=hosted_apply, record="hosted-apply")

    render = subparsers.add_parser(
        "report",
        parents=[recorded],
        help="render the final report's deterministic lines",
    )
    render.add_argument(
        "--repository", required=True, help="owner/name, or the origin path"
    )
    render.add_argument("--pull-request", help="its URL, where one was opened")
    render.add_argument("--stopped", help="what remains, on a stopped run")
    render.add_argument("--resumed", action="store_true")
    render.set_defaults(handler=render_report)

    body = subparsers.add_parser(
        "pr-body",
        parents=[recorded],
        help="fill the payload's pull-request template from the records",
    )
    body.add_argument("--repository", required=True, help="owner/name")
    body.set_defaults(handler=render_pr_body)
    return parser


def fail(message: str, status: int = 2) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}, indent=2), file=sys.stderr)
    raise SystemExit(status)


def main() -> int:
    arguments = build_parser().parse_args()
    record = getattr(arguments, "record", None)
    if record == "hosted-apply":
        # Read before the unlink, for the one step that builds on its own
        # earlier record: `hosted apply` run again later in the same flow.
        # One the sweep postdates belongs to a finished run, and an unreadable
        # one, left by an interrupted write, counts as none.
        earlier = record_path(arguments.records, f"{record}.json")
        sweep = record_path(arguments.records, "sweep.json")
        swept = (
            earlier.is_file()
            and sweep.is_file()
            and sweep.stat().st_mtime >= earlier.stat().st_mtime
        )
        try:
            arguments.previous = {} if swept else load(arguments.records, record)
        except (ValueError, PreflightError):
            arguments.previous = {}
    if record:
        # A step that fails leaves no record, so the renderers never read an
        # earlier run's result as this one's.
        record_path(arguments.records, f"{record}.json").unlink(missing_ok=True)
    try:
        result = arguments.handler(arguments)
    except PreflightError as error:
        fail(str(error))
    output = json.dumps(
        {"ok": True, "schema_version": SCHEMA_VERSION, **result},
        indent=2,
        sort_keys=True,
    )
    if record:
        record_path(arguments.records, f"{record}.json").write_text(output + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
