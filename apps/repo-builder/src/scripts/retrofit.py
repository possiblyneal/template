#!/usr/bin/env python3
"""Run the fixed steps of a retrofit and report each as JSON.

`preflight.py` is read-only by contract and only authorizes the next stage.
The steps here act on the candidate, the operator's clone, or the host, so
they live beside it rather than in it, and reuse its git helpers by import.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NoReturn

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
    for stage, path in (
        ("hooks_dir", arguments.hooks_dir),
        ("resume_record", arguments.resume_record),
        ("write_log", arguments.write_log),
    ):
        if path is None:
            continue
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
        requests = pull_requests(clone, arguments.repository, name)
        if requests is None:
            findings.append(f"could not read the pull requests for {name}")
        left.append({"branch": name, "reason": reason, "pull_requests": requests})

    return {
        "operation": "sweep",
        "clone": {"path": str(clone), "default_branch": default},
        "candidate": {"path": str(candidate), "branch": branch},
        "scratch": {
            stage: str(path)
            for stage, path in (
                ("hooks_dir", arguments.hooks_dir),
                ("resume_record", arguments.resume_record),
                ("write_log", arguments.write_log),
            )
            if path is not None
        },
        "stages": stages,
        "left_for_the_operator": left,
        "findings": findings,
    }


MERGE_SETTINGS = {
    "allow_merge_commit": True,
    "allow_squash_merge": False,
    "allow_rebase_merge": False,
    "delete_branch_on_merge": True,
}
UPGRADE_MESSAGE = "Upgrade to GitHub"
HOSTED_WRITES = (
    "merge-settings",
    "labels",
    "dependabot-alerts",
    "security-updates",
    "push-protection",
    "ruleset",
    "runner-variable",
)


class Refusal(Exception):
    """The host answered a request with an error rather than a body."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(f"{message} (HTTP {status})")
        self.status = status
        self.message = message

    @property
    def outcome(self) -> str:
        """An upgrade message means the plan lacks the feature; any other 403
        means this credential does, which is a different finding."""
        if self.status == "403" and self.message.startswith(UPGRADE_MESSAGE):
            return "not offered"
        if self.status == "403":
            return "permissions gap"
        return "refused"


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


def gh_or_refusal(*arguments: str) -> object:
    """A reading, or the refusal's outcome in its place."""
    try:
        return gh(*arguments)
    except Refusal as refusal:
        return {"refused": refusal.outcome, "detail": str(refusal)}


def enabled_by_status(endpoint: str) -> object:
    """An endpoint that answers 204 when a feature is on and 404 when it is off."""
    try:
        gh("api", endpoint)
    except Refusal as refusal:
        if refusal.status == "404":
            return False
        return {"refused": refusal.outcome, "detail": str(refusal)}
    return True


def runner_status(repository: str) -> object:
    name = f"dev-{repository.split('/', 1)[1]}"
    runners = gh_or_refusal("api", f"repos/{repository}/actions/runners")
    if not isinstance(runners, dict) or "refused" in runners:
        return runners
    for runner in runners.get("runners", []):
        if runner.get("name") == name:
            return runner.get("status")
    return "absent"


def hosted_read(arguments: argparse.Namespace) -> dict[str, object]:
    """Everything the hosted-write gate's question is built from, in one call."""
    repository = arguments.repository
    try:
        repo = gh("api", f"repos/{repository}")
    except Refusal as refusal:
        raise PreflightError(f"{repository} cannot be read: {refusal}") from refusal
    assert isinstance(repo, dict)
    analysis = repo.get("security_and_analysis") or {}
    # Absent for a plan that does not offer it, "unavailable" for one that
    # offers it only on another visibility; only an admin is shown the key.
    push_protection = analysis.get("secret_scanning_push_protection", {}).get(
        "status", "not offered" if repo.get("permissions", {}).get("admin") else None
    )
    labels = gh_or_refusal("api", "--paginate", f"repos/{repository}/labels")
    rulesets = gh_or_refusal("api", f"repos/{repository}/rulesets")
    return {
        "operation": "hosted read",
        "repository": repository,
        "visibility": repo.get("visibility"),
        "admin": repo.get("permissions", {}).get("admin"),
        "default_branch": repo.get("default_branch"),
        "merge_settings": {field: repo.get(field) for field in MERGE_SETTINGS},
        "labels": [label["name"] for label in labels]
        if isinstance(labels, list)
        else labels,
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
            {key: ruleset.get(key) for key in ("id", "name", "target", "enforcement")}
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
    for field, value in values.items():
        flagged += ["-F", f"{field}={json.dumps(value)}"]
    return flagged


def write_merge_settings(repository: str, log: WriteLog) -> str:
    """The four in one PATCH: sent apart, the host can refuse the second after
    the first has landed, and refuses outright to leave no merge method."""
    repo = gh("api", f"repos/{repository}")
    assert isinstance(repo, dict)
    before = {field: repo.get(field) for field in MERGE_SETTINGS}
    if before == MERGE_SETTINGS:
        return "already set"
    gh("api", "-X", "PATCH", f"repos/{repository}", *flags(MERGE_SETTINGS))
    log.append(
        "merge-settings",
        before,
        MERGE_SETTINGS,
        ["gh", "api", "-X", "PATCH", f"repos/{repository}", *flags(before)],
    )
    return "done"


def write_labels(
    repository: str, names: list[str], rename: bool, log: WriteLog
) -> dict[str, list[Any]]:
    """Create what is missing; the host matches names case-insensitively, so a
    case variant is renamed to the given spelling, or kept where `rename` is off
    because the destination's own vocabulary file is the one in force."""
    listed = gh("api", "--paginate", f"repos/{repository}/labels")
    assert isinstance(listed, list)
    existing = {label["name"].casefold(): label["name"] for label in listed}
    outcome: dict[str, list[Any]] = {
        "created": [],
        "renamed": [],
        "skipped": [],
        "refused": [],
    }
    for name in names:
        try:
            write_label(repository, name, existing, rename, log, outcome)
        except Refusal as refusal:
            # Stop at the first: what landed before it is kept in the outcome.
            outcome["refused"].append(
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
    outcome: dict[str, list[Any]],
) -> None:
    """One label, its outcome recorded in `outcome` as it lands."""
    write = f"label:{name}"
    present = existing.get(name.casefold())
    if log.logged(write) or present == name:
        outcome["skipped"].append({"label": name, "reason": "exists"})
    elif present is not None and not rename:
        outcome["skipped"].append(
            {"label": name, "reason": f"exists as {present}, kept"}
        )
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
        outcome["renamed"].append({"from": present, "to": name})
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
        outcome["created"].append(name)


def write_toggle(repository: str, write: str, endpoint: str, log: WriteLog) -> str:
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
        return "already set"
    gh("api", "-X", "PUT", endpoint)
    log.append(write, False, True, ["gh", "api", "-X", "DELETE", endpoint])
    return "done"


def write_push_protection(repository: str, log: WriteLog) -> str:
    field = "security_and_analysis[secret_scanning_push_protection][status]"
    repo = gh("api", f"repos/{repository}")
    assert isinstance(repo, dict)
    before = (
        (repo.get("security_and_analysis") or {})
        .get("secret_scanning_push_protection", {})
        .get("status")
    )
    if before == "enabled":
        return "already set"
    # As in hosted_read: only an admin is shown the key at all.
    if before is None and not repo.get("permissions", {}).get("admin"):
        raise Refusal("403", "push protection status is not shown to this credential")
    if before in (None, "unavailable"):
        raise Refusal("403", f"{UPGRADE_MESSAGE}: push protection is not offered")
    gh("api", "-X", "PATCH", f"repos/{repository}", "-f", f"{field}=enabled")
    log.append(
        "push-protection",
        before,
        "enabled",
        ["gh", "api", "-X", "PATCH", f"repos/{repository}", "-f", f"{field}={before}"],
    )
    return "done"


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
) -> str:
    """Create the ruleset, or repair the destination's own in place.

    The body is the flow's to compose from the references, since which contexts
    it requires and which branch it names are judgements this command does not
    make. A ruleset replaced keeps its before-state beside the log, because the
    command that restores it needs the whole document as its input.
    """
    if replaces is None:
        created = gh(
            "api", "-X", "POST", f"repos/{repository}/rulesets", "--input", str(body)
        )
        assert isinstance(created, dict)
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
        return "done"
    endpoint = f"repos/{repository}/rulesets/{replaces}"
    before = gh("api", endpoint)
    assert isinstance(before, dict)
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
    return "done"


def write_runner_variable(repository: str, log: WriteLog) -> str:
    """Set only where the repository is private and its runner reads online,
    both read here rather than trusted from the gate's snapshot."""
    repo = gh("api", f"repos/{repository}")
    assert isinstance(repo, dict)
    if repo.get("visibility") != "private":
        return f"not offered: the repository is {repo.get('visibility')}"
    runner = runner_status(repository)
    if runner != "online":
        return f"not offered: the dev runner is {runner}"
    try:
        current = gh("api", f"repos/{repository}/actions/variables/RUNNER")
        before = current.get("value") if isinstance(current, dict) else None
    except Refusal as refusal:
        if refusal.status != "404":
            raise
        before = None
    if before == "self-hosted":
        return "already set"
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
    return "done"


def hosted_apply(arguments: argparse.Namespace) -> dict[str, object]:
    """Perform the writes the gate approved, in the gate's order, and no others.

    There is no default-branch write here: the rename is a hard stop when
    declined and repairs every clone, so it stays a step the flow runs itself.
    """
    repository, approved = arguments.repository, set(arguments.approve)
    if "labels" in approved and not arguments.label:
        raise PreflightError("labels approved with no --label to create")
    if "ruleset" in approved and arguments.ruleset is None:
        raise PreflightError("ruleset approved with no --ruleset body")
    log = WriteLog(arguments.write_log)
    writes: dict[str, object] = {}
    findings: list[str] = []
    performers = {
        "merge-settings": lambda: write_merge_settings(repository, log),
        "labels": lambda: write_labels(
            repository, arguments.label, not arguments.keep_case_variants, log
        ),
        "dependabot-alerts": lambda: write_toggle(
            repository,
            "dependabot-alerts",
            f"repos/{repository}/vulnerability-alerts",
            log,
        ),
        "security-updates": lambda: write_toggle(
            repository,
            "security-updates",
            f"repos/{repository}/automated-security-fixes",
            log,
        ),
        "push-protection": lambda: write_push_protection(repository, log),
        "ruleset": lambda: write_ruleset(
            repository, arguments.ruleset, arguments.replace_ruleset, log
        ),
        "runner-variable": lambda: write_runner_variable(repository, log),
    }
    for write in HOSTED_WRITES:
        if write not in approved:
            continue
        if write != "labels" and log.logged(write):
            writes[write] = "logged"
            continue
        try:
            outcome = performers[write]()
        except Refusal as refusal:
            outcome = refusal.outcome
            if refusal.outcome != "not offered":
                findings.append(f"{write}: {refusal}")
        if isinstance(outcome, dict):
            findings.extend(
                f"{write}: {item['reason']}"
                for item in outcome["refused"]
                if item["outcome"] != "not offered"
            )
        writes[write] = outcome
    return {
        "operation": "hosted apply",
        "repository": repository,
        "writes": writes,
        "write_log": {"path": str(arguments.write_log), "entries": log.entries},
        "findings": findings,
    }


SUMMARY_ROW = re.compile(
    r"^([A-Za-z0-9_-]+) +(pass|not-applicable|unavailable|FAIL|would-run)(?: +(.*))?$"
)
# `scripts/summarize`'s line for a non-zero exit with no failing row.
UNLISTED_FAILURE = re.compile(r"^(.+ exited \d+) with no failing result line")
SETTING_WRITES = {
    "merge-settings": "Merge settings (merge commit only, head branches deleted)",
    "dependabot-alerts": "Dependabot alerts",
    "security-updates": "Dependabot security updates",
    "push-protection": "Push protection",
    "ruleset": "Branch ruleset",
    "runner-variable": "Runner variable",
}


class Report:
    """The final report's lines, with every judgement left as a marked slot."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.slots: list[str] = []

    def slot(self, what: str) -> str:
        self.slots.append(what)
        return f"[[FILL: {what}]]"

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)

    def section(self, heading: str) -> None:
        self.lines += ["", heading]


def read_summary(path: Path) -> list[dict[str, Any]]:
    """`scripts/summarize` rows: a state line, then the findings indented under it.

    A command that exited non-zero with every row passing fails as a row of its
    own, since the saved summary is the only place its exit status survives.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        matched = SUMMARY_ROW.match(line)
        unlisted = UNLISTED_FAILURE.match(line)
        if matched:
            check, state, detail = matched.groups()
            rows.append(
                {"check": check, "state": state, "detail": detail or "", "findings": []}
            )
        elif unlisted:
            rows.append(
                {
                    "check": "exit-status",
                    "state": "FAIL",
                    "detail": unlisted.group(1),
                    "findings": [f"{unlisted.group(1)} outside the Result table"],
                }
            )
        elif line[:1].isspace() and line.strip() and rows:
            rows[-1]["findings"].append(line.strip())
    return rows


def failing(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["state"] in ("FAIL", "unavailable")]


def command_result(rows: list[dict[str, Any]]) -> str:
    failed = [row["check"] for row in rows if row["state"] == "FAIL"]
    if failed:
        return f"fail ({', '.join(map(str, failed))})"
    unavailable = [f"{row['check']}: {row['detail']}" for row in failing(rows)]
    if unavailable:
        return f"unavailable ({'; '.join(unavailable)})"
    return "pass"


def joined(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def load(path: Path | None) -> Any:
    return json.loads(path.read_text()) if path is not None else {}


# The candidate branch's sweep stage, as the Cleanup line reads it.
BRANCH_FATES = {
    "kept": "kept for the pull request still open",
    "absent": "already absent",
    "refused": "standing, because `branch -d` refused it",
    "skipped": "standing, because the containment test could not run",
}


def ruleset_enforcement(
    outcome: object, pull_request: str | None, slot: Callable[[str], str]
) -> str:
    """Step 8 proves nothing here; step 9's reading of the pull request does."""
    if outcome not in ("done", "logged"):
        return "n/a (no ruleset written)"
    if pull_request is None:
        return "not yet proven at the gate, and no pull request opened to prove it"
    return slot("step 9's mergeable/mergeStateStatus reading of the pull request")


def render_report(arguments: argparse.Namespace) -> dict[str, object]:
    """Render the deterministic lines of a retrofit's final report.

    The shape is reporting.md's Final report with retrofit.md's Report
    additions in place. Every count, setting, write, check result and cleanup
    outcome is read from the JSON the other subcommands wrote; everything the
    flow decided or judged is a `[[FILL: ...]]` slot for the session to fill.
    """
    proofs = load(arguments.proofs)
    hooks_result = load(arguments.hooks)
    swept = load(arguments.sweep)
    hosted_state = load(arguments.hosted_read)
    applied = load(arguments.hosted_apply)
    summaries = [
        (command, read_summary(Path(path))) for command, path in arguments.summary
    ]
    report = Report()
    r = report.slot

    copy = proofs["copy"]
    purity = proofs["rename_purity"]
    moves = purity["moves"]
    writes = applied.get("writes", {})
    entries = applied.get("write_log", {}).get("entries", [])
    bar_failures = [
        (command, row) for command, rows in summaries for row in failing(rows)
    ]

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

    report.section("### Reconciliation")
    report.add(
        f"- Applied: {r('payload paths written because they were absent, or none')}",
        f"- Preserved: {r('paths kept as the destination had them, or none')}",
        f"- Renamed/deleted: {r('paths, or none')}",
        f"- Conflicted: {r('paths and competing intents, or none')}",
        f"- Superseded: {r('each superseded path, what it did and what carries it now, or none')}",
        f"- Partially covered, not cut: {r('script paths and the parts already covered, or none')}",
        f"- Overridden: {r('each overridden path and its recorded reason, or none')}",
    )
    if moves:
        report.add(
            *(f"- Layout plan: {move['from']} -> {move['to']}: moved" for move in moves)
        )
    report.add(
        f"- Layout plan: {r('each move the operator corrected or declined, or delete this line')}"
        if moves
        else "- Layout plan: none",
        f"- Unmovable: {r('each path that could not move and why, or none')}",
        f"- References repaired: {r('each file and the moved path rewritten in it, or none')}",
        f"- References reported, not rewritten: {r('each file and the prose describing the old structure, or none')}",
        f"- Ignore rules the payload does not cover: {r('each rule and what it ignored, or none')}",
    )

    report.section("### Application boundaries")
    report.add(
        f"- ADRs written: {r('paths, or none')}",
        f"- Unit map: {r('one line per unit, in the Report additions shape')}",
        f"- Ships nothing for want of an adapter: {r('unit and language, or none')}",
        f"- Declared but not built: {r('deployable, its descriptor and owning unit, or none')}",
    )

    authored = [f"{item['path']} ({item['class']})" for item in copy["differing"]]
    authored += list(proofs["authored"])
    authored += [
        f"{move['to']} (moved from {move['from']}, +{move['added']}/-{move['removed']})"
        for move in moves
        if not move["identical"]
    ]
    report.section("### File list")
    report.add(
        f"- {r('payload paths accounted for, and every difference named as intended or as a defect')}",
        f"- Authored surface: {joined(authored)}",
    )

    report.section("### Addon adoption")
    report.add(
        f"- Already held: {r('addon-shaped paths the destination brought with it, or none')}"
    )

    report.section("### Repository settings")
    report.add(
        f"- Destination visibility: {hosted_state.get('visibility') or r('public or private, read from the API')}"
    )
    for write, name in SETTING_WRITES.items():
        outcome = writes.get(write)
        if outcome in ("done", "already set", "logged"):
            report.add(f"- {name}: enabled")
        elif outcome is None:
            report.add(f"- {name}: not requested")
        elif str(outcome).startswith("not offered:"):
            report.add(
                f"- {name}: unavailable ({str(outcome).removeprefix('not offered: ')})"
            )
        elif outcome == "not offered":
            report.add(f"- {name}: unavailable (not offered for the plan)")
        else:
            report.add(f"- {name}: unavailable ({outcome})")
    labels = writes.get("labels")
    if isinstance(labels, dict):
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
        label_line = "; ".join(parts)
    else:
        label_line = f"none created ({r('reason no labels were created')})"
    report.add(
        f"- Issue tracker: {r('tracker, recorded in docs/agents/issue-tracker.md, shipped by the payload or kept from the destination')}; labels: {label_line}"
    )

    report.section("### Hosted writes, reversible")
    for entry in entries:
        report.add(
            f"- {entry['write']}: was {json.dumps(entry['before'])} -> "
            f"{json.dumps(entry['after'])}; reverse with `{shlex.join(entry['reverse_command'])}`"
        )
    report.add(
        f"- {r('each write the operator declined, with the reason, recorded in generation.features; or delete this line')}"
    )
    if not entries:
        report.add("- none performed")

    gaps = [
        finding
        for finding in applied.get("findings", [])
        if writes.get(str(finding).split(":", 1)[0]) == "permissions gap"
    ]
    if isinstance(labels, dict):
        gaps += [
            f"labels: {item['reason']}"
            for item in labels.get("refused", [])
            if item["outcome"] == "permissions gap"
        ]
    report.section("### Hosted writes, irreversible")
    report.add(
        f"- {r('each irreversible write, its before-state, applied value and cost; or none')}",
        f"- Ruleset enforcement: {ruleset_enforcement(writes.get('ruleset'), arguments.pull_request, r)}",
        f"- Permissions gap: {'; '.join(gaps) if gaps else 'none'}",
    )

    report.section("### Verification")
    for command, rows in summaries:
        report.add(f"- `{command}`: {command_result(rows)}")
        for row in failing(rows):
            report.add(
                *(f"  - {row['check']}: {finding}" for finding in row["findings"])
            )
    report.add(
        f"- Hooks: installed at worktree scope into {swept.get('scratch', {}).get('hooks_dir') or r('the candidate hooks directory')}; "
        f"`extensions.worktreeConfig` set on {swept.get('clone', {}).get('path') or r('the clone')} and left set",
        f"- Copied paths byte-identical to their source: {copy['identical']}/{copy['total']}; "
        "the rest are the authored surface, under File list. An overridden path is "
        "in neither count, under Reconciliation instead",
        f"- Workflows the pull-request event never ran: {r('names, or none')}",
        f"- Code review: {r('the axes that ran over the authored surface, the findings corrected or recorded as incorrectly identified, and the Reviewed-Head sha, or why no sign-off was written')}",
        f"- Default branch after merge: {r('check-suite result')}"
        if hooks_result
        else "- Default branch after merge: n/a (nothing merged)",
        f"- Moved paths byte-identical to their pre-move blob: {purity['identical']}/{purity['total']}",
        f"- Directories emptied by a move: {r('each directory and whether it is gone, or none')}",
        f"- Untracked at the bar: {r('none, or the paths and how they were disposed')}",
        f"- Declared facts executed: {r('per unit, the scripts/package and scripts/run results')}",
        f"- Tool declaration: {r('per manifest, what was added, kept or declined')}",
        f"- Configuration boundary: {r('one row per language')}",
        f"- Autofix: {r('what scripts/fix cleared, and in which commit')}",
        f"- Autofix settings resolution: {r('every tool resolved inside the candidate, or SKIPPED and why')}",
        f"- Payload paths the autofix rewrote: {r('each path and the rule that rewrote it, or none')}",
    )
    if bar_failures:
        unmet = "; ".join(
            f"{row['check']}: {'fail' if row['state'] == 'FAIL' else 'unavailable'}"
            + (f" ({row['detail']})" if row["state"] == "unavailable" else "")
            for _, row in bar_failures
        )
        report.add(
            f"- Bar: UNMET: {unmet}; stopped before the pull request, zero hosted writes performed",
            f"- Destination fix prepared: {r('the unmet-bar outcome, in the Report additions shape')}",
            f"- Destination fix published: {r('the unmet-bar outcome, in the Report additions shape')}",
        )
    else:
        report.add("- Bar: met")
    if hooks_result:
        moved_aside = [
            f"{item['from']} -> {item['to']}" for item in hooks_result["moved_aside"]
        ]
        linked = [
            f"{item['hook']} {item['disposition']}"
            + (f" as {item['as']}" if item.get("as") else "")
            for item in hooks_result["global_hooks"]
        ]
        checks = hooks_result["checks"]
        observed = [name for name, held in checks.items() if held]
        failed = [name for name, held in checks.items() if not held]
        report.add(
            f"- Destination hooks after merge: shims in {hooks_result['hooks_path']}, "
            f"`core.hooksPath` pinned local to it, moved aside: {joined(moved_aside)}, "
            f"global hooks: {joined(linked)}, verified by {joined(observed)}"
            + (f"; NOT observed: {', '.join(failed)}" if failed else "")
        )
    elif arguments.stopped:
        report.add(
            "- Destination hooks after merge: n/a (stopped before the merge was offered)"
        )
    else:
        report.add("- Destination hooks after merge: n/a (merge declined)")

    report.section("### Cleanup")
    stages = swept.get("stages", {})
    if not swept:
        report.add(
            f"- Candidate: left standing at {r('candidate path')}, because the flow stopped and resumes from it"
        )
    else:
        candidate = swept["candidate"]
        if (
            stages.get("worktree") in ("done", "absent")
            and stages.get("branch") == "deleted"
        ):
            report.add(
                f"- Candidate: removed from {candidate['path']}, branch {candidate['branch']} deleted"
            )
        elif stages.get("worktree") in ("done", "absent"):
            report.add(
                f"- Candidate: worktree removed from {candidate['path']}, branch "
                f"{candidate['branch']} {BRANCH_FATES[stages.get('branch')]}"
            )
        else:
            report.add(
                f"- Candidate: left standing at {candidate['path']}, because its removal was refused"
            )
        scratch = [
            f"{path}: {stages.get(stage)}"
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
    left += [str(finding) for finding in hooks_result.get("findings", [])]
    report.add(f"- Left for the operator: {joined(left)}")
    report.add(
        f"- Left for the operator: {r('any other path left in place and why; or delete this line')}"
    )

    if arguments.resumed:
        logged = [write for write, outcome in writes.items() if outcome == "logged"]
        report.section("### Resumption")
        report.add(
            f"- Re-observed as already done: {r('what live state showed complete')}",
            f"- Taken from the resume record: hosted writes {joined(logged)}; {r('the issues and decisions read back')}",
            f"- Redone: {r('anything performed again and why, or none')}",
            f"- Retries: {r('transient failures retried and their outcomes, or none')}",
        )

    report.section("### Pending action")
    report.add(
        r("the exact decision or authorization needed") if arguments.stopped else "none"
    )

    arguments.output.write_text("\n".join(report.lines) + "\n")
    return {"operation": "report", "path": str(arguments.output), "slots": report.slots}


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

    teardown = subparsers.add_parser(
        "sweep", help="remove what the flow created, forcing nothing"
    )
    teardown.add_argument("--clone", type=Path, required=True)
    teardown.add_argument("--candidate", type=Path, required=True)
    teardown.add_argument("--branch", required=True, help="the retrofit branch")
    teardown.add_argument("--default-branch", required=True)
    teardown.add_argument("--repository", required=True, help="owner/name")
    teardown.add_argument("--hooks-dir", type=Path, help="the candidate's own")
    teardown.add_argument("--resume-record", type=Path)
    teardown.add_argument("--write-log", type=Path, help="hosted apply's")
    teardown.set_defaults(handler=sweep)

    hosted = subparsers.add_parser(
        "hosted", help="read the gate's snapshot, or perform the approved writes"
    )
    hosted_commands = hosted.add_subparsers(dest="hosted_command", required=True)
    read = hosted_commands.add_parser("read", help="snapshot the hosted state")
    read.add_argument("--repository", required=True, help="owner/name")
    read.set_defaults(handler=hosted_read)
    apply = hosted_commands.add_parser("apply", help="perform the approved writes")
    apply.add_argument("--repository", required=True, help="owner/name")
    apply.add_argument(
        "--approve", action="append", choices=HOSTED_WRITES, default=[], required=True
    )
    apply.add_argument(
        "--write-log", type=Path, required=True, help="beside the candidate"
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
    apply.set_defaults(handler=hosted_apply)

    render = subparsers.add_parser(
        "report", help="render the final report's deterministic lines"
    )
    render.add_argument("--repository", required=True, help="owner/name")
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--proofs", type=Path, required=True)
    render.add_argument(
        "--summary",
        nargs=2,
        action="append",
        default=[],
        required=True,
        metavar=("COMMAND", "FILE"),
        help="a check command and the file holding its scripts/summarize output",
    )
    render.add_argument(
        "--hooks", type=Path, help="absent where the merge was declined"
    )
    render.add_argument("--sweep", type=Path, help="absent on a stopped run")
    render.add_argument("--hosted-read", type=Path)
    render.add_argument("--hosted-apply", type=Path)
    render.add_argument("--pull-request", help="its URL, where one was opened")
    render.add_argument("--stopped", help="what remains, on a stopped run")
    render.add_argument("--resumed", action="store_true")
    render.set_defaults(handler=render_report)
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
