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
    nul_fields,
    repository_identity,
    require_git_repository,
    require_subtree,
    resolve_commit,
    run_git,
    sibling_of_subtree,
    tree_paths,
    validate_manifest,
)
from retrofit import (
    HOSTED_WRITES,
    PULL_REQUEST_TRIGGER,
    Outcome,
    Refusal,
    Report,
    Slot,
    WriteLog,
    command_result,
    failing,
    hook_types,
    install_hooks,
    joined,
    load,
    load_required,
    orca_line,
    prior_hooks,
    read_summary,
    record_path,
    required_record,
    run_tool,
    setting_line,
    write_labels,
    write_log_path,
    write_merge_settings,
    write_push_protection,
    write_ruleset,
    write_toggle,
)
from update import SLOT, copy_proof

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
        "subtree": subtree,
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
    recorded = recorded if isinstance(recorded, dict) else {}
    merged = {**recorded, **features}
    # One role's label never replaces the roles step 6 already respelled.
    earlier, later = recorded.get("triage_labels"), features.get("triage_labels")
    if isinstance(earlier, dict) and isinstance(later, dict):
        merged["triage_labels"] = {**earlier, **later}
    generation["features"] = merged
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


# The `main` ruleset every generated repository starts with. Its required
# contexts are the job `name:` of each job in the payload's ci.yml and
# security.yml and of codeql.yml's `scanning`, which test_generate.py holds it
# to: a check run reports the job's `name:`, not its id, so a context spelled
# any other way stays pending and leaves the default branch never mergeable.
# An analyze leg is one context per language and release.yml never runs on a
# pull request, so neither is required.
# The writes a plan or visibility can withhold. The host refuses them with 403
# or 422 then, which is a measurement rather than a failure.
PLAN_GATED = ("push-protection", "ruleset")


def ruleset_body(
    records: Path, materialized: dict[str, object], template: Path
) -> Path:
    """Write the ruleset body as it stands beside the payload at the source commit.

    Read at the commit, as `ownership_rules` is, so the required contexts are
    the job names of the workflows being generated rather than of whatever the
    template checkout holds now.
    """
    commit = str(materialized["commit"])
    location = sibling_of_subtree(str(materialized["subtree"]), "ruleset.json")
    shown = run_git(template, "show", f"{commit}:{location}", check=False)
    if shown.returncode != 0:
        raise PreflightError(f"ruleset body does not exist at {commit}: {location}")
    body = record_path(records, "ruleset.json")
    body.write_text(shown.stdout)
    return body


def ruleset_contexts(body: Path) -> list[str]:
    document = json.loads(body.read_text())
    return [
        check["context"]
        for rule in document["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    ]


def probe(candidate: Path, branch: str) -> dict[str, str]:
    """Push an empty commit straight to the default branch and require GH013.

    Creation answers 201 whether or not a ruleset binds, so only a refused
    push proves it. The commit is built with `commit-tree` on the remote tip
    and pushed by name, so no local ref moves and there is nothing to rewind:
    the candidate's untracked payload and anything already staged stay out of
    it, where `commit --allow-empty` would carry the index and `reset --hard`
    would take the working tree. An accepted push leaves the commit on the
    remote default branch; removing it is a force-push, which is a gate's
    decision, so the command stops and names it.
    """
    parent = git_output(candidate, "rev-parse", "--verify", f"refs/heads/{branch}")
    commit = git_output(
        candidate,
        "commit-tree",
        f"{parent}^{{tree}}",
        "-p",
        parent,
        "-m",
        "chore: ruleset probe",
    )
    pushed = run_git(
        candidate, "push", "origin", f"{commit}:refs/heads/{branch}", check=False
    )
    if pushed.returncode == 0:
        raise PreflightError(
            f"the ruleset does not bind: probe commit {commit} was accepted onto "
            f"origin's {branch} and is still there; removing it needs a force-push "
            "approved at a gate"
        )
    detail = pushed.stderr.strip()
    if "GH013" not in detail:
        raise PreflightError(
            f"the probe push was refused without GH013, so the ruleset is unproven: "
            f"{detail}"
        )
    return {"commit": commit, "outcome": "refused", "detail": detail}


def settings(arguments: argparse.Namespace) -> dict[str, object]:
    """Step 5's writes in order, then the probe where the ruleset was created.

    The writers are retrofit's: the merge settings go as one PATCH under
    REST's field names, each write is logged with its reverse before it is
    sent, and one an earlier run logged is not repeated. A 403 or 422 on a
    plan-gated write is `not offered`, never a disabled setting; on any other
    write it keeps retrofit's reading, since those are offered on every plan.
    The probe runs after a 201, and again on a rerun that finds the ruleset
    logged: on a refused ruleset an unprotected branch would take the probe
    commit with nothing proved.
    """
    repository = arguments.repository
    repository_name(repository)
    materialized = load_required(arguments.records, "materialize")
    candidate = Path(str(materialized["candidate"]))
    template = require_git_repository(arguments.template_repo, "template repository")
    body = ruleset_body(arguments.records, materialized, template)
    log = WriteLog(write_log_path(arguments.records))
    writes = {
        "merge-settings": lambda: write_merge_settings(repository, log),
        "dependabot-alerts": lambda: write_toggle(
            "dependabot-alerts", f"repos/{repository}/vulnerability-alerts", log
        ),
        "security-updates": lambda: write_toggle(
            "security-updates", f"repos/{repository}/automated-security-fixes", log
        ),
        "push-protection": lambda: write_push_protection(repository, log),
        "ruleset": lambda: write_ruleset(repository, body, None, log),
    }
    outcomes: dict[str, Outcome] = {}
    reasons: dict[str, str] = {}
    for name, perform in writes.items():
        if log.logged(name):
            outcomes[name] = Outcome.LOGGED
            continue
        try:
            outcomes[name] = perform()
        except Refusal as refusal:
            plan_limited = name in PLAN_GATED and refusal.status in ("403", "422")
            outcomes[name] = Outcome.NOT_OFFERED if plan_limited else refusal.outcome
            reasons[name] = str(refusal)
    # A ruleset an earlier run created is probed again: that run's record is
    # gone, so nothing shows its probe was refused, and a rerun is what follows
    # a probe that failed.
    probed = (
        probe(candidate, arguments.default_branch)
        if outcomes["ruleset"] in (Outcome.DONE, Outcome.LOGGED)
        else None
    )
    return {
        "operation": "settings",
        "repository": repository,
        "default_branch": arguments.default_branch,
        "writes": outcomes,
        "reasons": reasons,
        "required_contexts": ruleset_contexts(body),
        "probe": probed,
        "write_log": {"path": str(log.path), "entries": log.entries},
    }


def publish(arguments: argparse.Namespace) -> dict[str, object]:
    """Push the candidate's branch and open its pull request with the rendered body.

    A body still holding a slot is refused before anything leaves the machine,
    since the host would publish the marker as the reviewer's text.
    """
    body = required_record(arguments.records, "pr-body.md")
    if SLOT in body.read_text(encoding="utf-8"):
        raise PreflightError(f"{body} still holds a {SLOT} slot; fill it first")
    candidate, materialized = materialized_candidate(arguments.records)
    base = materialized["default_branch"]
    branch = git_output(candidate, "branch", "--show-current")
    if branch in ("", base):
        raise PreflightError(
            f"the candidate is on {branch or 'no branch'}; publish from a branch off {base}"
        )
    pushed = run_git(candidate, "push", "-q", "-u", "origin", branch, check=False)
    if pushed.returncode != 0:
        raise PreflightError(f"push of {branch} refused: {pushed.stderr.strip()}")
    created = run_tool(
        candidate,
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        branch,
        "--title",
        git_output(candidate, "log", "-1", "--format=%s"),
        "--body-file",
        str(body),
    )
    if created.returncode != 0:
        raise PreflightError(f"gh pr create failed: {created.stderr.strip()}")
    return {
        "operation": "publish",
        "branch": branch,
        "pull_request": created.stdout.strip(),
    }


# The judgements no record settles, left as `[[FILL: ...]]` slots for the
# session to write by hand before the body is published or the report shown.
SLOTS = {
    "boundaries": Slot(
        "one line per deployable, `<name>: choke point <constraint> -> <language>, "
        "<how it was selected>`, then the Wayfinding line"
    ),
    "addons": Slot(
        "each addon taken and its slots filled or OUTSTANDING, then those offered "
        "and not taken on one line"
    ),
    "default-branch": Slot(
        "the check-suite result of the default branch's run after the bootstrap merge"
    ),
    "pending-action": Slot("the exact decision or authorization needed"),
    "tickets": Slot("the open ticket count, then the first with no open blocker"),
    "first-manifest": Slot(
        "the declarations the selected language owes, from lifecycle.md "
        '"Tools the first manifest must declare", or none, <language> declares no tools'
    ),
}
ROOT_MANIFEST_STATE = (
    'the absent root manifest, which scripts/check reports as "No project manifest '
    "found, so there is nothing to check yet. Every check becomes required as soon "
    'as a manifest is added."'
)


def tracker_of(manifested: dict) -> str | None:
    tracker = manifested.get("features", {}).get("issue_tracker")
    return str(tracker) if tracker else None


def labels_line(labelled: dict, tracker: str | None) -> str:
    if tracker:
        return f"none created (the tracker is {tracker}, not GitHub Issues)"
    kept = {item["label"]: item["reason"] for item in labelled["kept"]}
    parts = []
    if labelled["created"]:
        parts.append(f"created ({', '.join(labelled['created'])})")
    if labelled["renamed"]:
        renames = ", ".join(
            f"{item['from']} -> {item['to']}" for item in labelled["renamed"]
        )
        parts.append(
            f"renamed to the spelling in force ({renames}; label search is "
            "case-sensitive, so anything pinned to the old string stops matching)"
        )
    if labelled["existing"]:
        present = [
            f"{name} ({kept[name]})" if name in kept else name
            for name in labelled["existing"]
        ]
        parts.append(f"already present ({', '.join(present)})")
    return "; ".join(parts)


def settings_lines(configured: dict) -> list[str]:
    """One line per write `settings` sent, the ruleset's carrying its probe."""
    writes, reasons = configured["writes"], configured["reasons"]
    lines = []
    for write in HOSTED_WRITES:
        if write.setting is None or write.name not in writes:
            continue
        outcome = writes[write.name]
        line = setting_line(write.setting, outcome, reasons.get(write.name), True, None)
        if write.name == "ruleset" and outcome in (Outcome.DONE, Outcome.LOGGED):
            line += (
                "; probe refused with GH013"
                if configured["probe"]
                else "; not probed (written by an earlier run)"
            )
            line += f"; requires {', '.join(configured['required_contexts'])}"
        lines.append(line)
    return lines


def hooks_line(hooked: dict) -> str:
    if hooked["outcome"] == "not-applicable":
        return (
            "- Hooks: none installed, because the candidate carries no "
            "`.pre-commit-config.yaml` to read hook types from"
        )
    if hooked["outcome"] != "installed":
        return (
            f"- Hooks: NOT installed into {hooked['hooks_path']}: "
            f"{joined(hooked['findings'])}"
        )
    prior = hooked["prior_hooks"]
    chained = [
        f"{item['hook']} {item['disposition']}"
        + (f" as {item['as']}" if item.get("as") else "")
        for item in hooked["chained"]
    ]
    return (
        f"- Hooks: installed at local scope into {hooked['hooks_path']}; prior "
        f"hooks: {prior['path']} ({prior['scope']}), chained: {joined(chained)}"
    )


def copy_line(listed: dict) -> str:
    copy = listed["copy"]
    return (
        f"- Copied paths byte-identical to their source: {copy['identical']}/"
        f"{copy['total']}; the rest are the authored surface, under File list"
    )


def unrun_workflows(template: Path, listed: dict) -> list[str]:
    """Payload workflows no `pull_request` trigger reaches, at the source commit.

    Read from the template rather than the candidate, which is swept by the
    time the report renders.
    """
    commit, subtree = listed["template"]["commit"], listed["template"]["subtree"]
    folder = f"{subtree}/.github/workflows"
    names = nul_fields(template, "ls-tree", "-z", "--name-only", f"{commit}:{folder}")
    return [
        f".github/workflows/{name}"
        for name in sorted(names)
        if name.endswith((".yml", ".yaml"))
        and not PULL_REQUEST_TRIGGER.search(
            git_output(template, "show", f"{commit}:{folder}/{name}")
        )
    ]


def render_report(arguments: argparse.Namespace) -> dict[str, object]:
    """Render a generate's final report from the records its steps wrote.

    The shape is reporting.md's Final report less what an empty destination
    never has: Reconciliation, the drift and merge-settings-overwritten lines,
    and Resumption. Step 14's handover follows Pending action. Every count,
    setting and outcome is read from a record; only judgement is a slot.
    """
    prefix = arguments.records
    materialized = load_required(prefix, "materialize")
    # Read for its presence: the empty root it pushed is what the merge lands on.
    load_required(prefix, "bootstrap")
    configured = load_required(prefix, "settings")
    manifested = load_required(prefix, "manifest")
    tracker = tracker_of(manifested)
    labelled = {} if tracker else load_required(prefix, "labels")
    hooked = load_required(prefix, "hooks")
    listed = load_required(prefix, "filelist")
    orca = load_required(prefix, "orca")
    rows = read_summary(required_record(prefix, "check.txt"))
    template = require_git_repository(arguments.template_repo, "template repository")
    published = load(prefix, "publish")
    stopped = arguments.stopped

    report = Report({}, SLOTS)
    fill = report.fill
    report.add(
        "## Repo Builder Result",
        "",
        f"- Status: stopped ({stopped})" if stopped else "- Status: finished",
        "- Operation: generate",
        f"- Pull request: {published.get('pull_request') or 'not created'}",
        f"- Template: not previously generated -> {materialized['commit']}",
        f"- Destination: {arguments.repository}",
        f"- Orca: {orca_line(orca)}",
    )
    report.section("### Application boundaries")
    adrs = [path for path in listed["additions"] if ADR.match(path)]
    report.add(fill("boundaries"), f"- ADRs written: {joined(adrs)}")

    report.section("### File list")
    report.add(
        f"- Payload paths: {listed['payload_paths']}, the first application in "
        f"apps/app-name/'s place; tracked: {listed['tracked_paths']}; missing: "
        f"{joined(listed['missing'])}; strays: {joined(listed['strays'])}; held "
        f"ignored on disk: {joined(listed['ignored_present'])}; ignored but "
        f"tracked: {joined(listed['ignored_tracked'])}; additions: "
        f"{joined(listed['additions'])}",
        f"- Authored surface: {joined(listed['copy']['authored'])}",
    )
    report.section("### Addon adoption")
    report.add(fill("addons"))

    report.section("### Repository settings")
    default = "GitHub Issues via gh (the default)"
    recorded = tracker and f"{tracker}, recorded in generation.features.issue_tracker"
    report.add(
        *settings_lines(configured),
        f"- Issue tracker: {recorded or default}; labels: "
        f"{labels_line(labelled, tracker)}",
    )

    report.section("### Verification")
    report.add(f"- `scripts/check`: {command_result(rows)}")
    for row in failing(rows):
        report.add(*(f"  - {row.check}: {finding}" for finding in row.findings))
    report.add(
        hooks_line(hooked),
        copy_line(listed),
        "- Workflows the pull-request event never ran: "
        f"{joined(unrun_workflows(template, listed))}",
        "- Code review: skipped, as reporting.md's Reviewing the pull request directs",
        f"- Default branch after merge: {fill('default-branch')}",
    )

    report.section("### Cleanup")
    candidate = Path(materialized["candidate"])
    if not candidate.exists():
        fate = f"removed from {candidate}"
    elif stopped:
        fate = f"left standing at {candidate}, because the flow stopped and resumes from it"
    else:
        fate = f"left standing at {candidate}, not swept"
    report.add(
        f"- Candidate: {fate}",
        f"- Scratch outside the candidate: {prefix}.*: kept, because this report "
        "is rendered from them",
        f"- Left for the operator: {joined(hooked['findings'])}",
    )
    report.section("### Pending action")
    report.add(fill("pending-action") if stopped else "none")
    if not stopped:
        handover(report, arguments, orca, tracker)

    output = record_path(prefix, "report.md")
    output.write_text("\n".join(report.lines) + "\n", encoding="utf-8")
    return {"operation": "report", "path": str(output), "slots": report.slots}


def handover(
    report: Report, arguments: argparse.Namespace, orca: dict, tracker: str | None
) -> None:
    """Step 14's first prompt, for the session that opens the new clone."""
    clone = orca.get("repository") if orca.get("registered") else None
    expected = [ROOT_MANIFEST_STATE]
    if arguments.visibility != "public":
        expected.append(
            f"the skipped CodeQL detect and analyze legs on a {arguments.visibility} "
            'destination, per lifecycle.md "Code scanning lands everywhere and '
            'decides at run time"'
        )
    report.section("### First prompt")
    report.add(
        "",
        "Copy this into the first session opened in a clone of the new repository:",
        "",
        "```text",
        f"Work {arguments.repository} in {clone or 'a fresh clone'}.",
        "Install the hooks there: `pre-commit install`, or, if that refuses because "
        "a `core.hooksPath` is already set on this machine, `pre-commit "
        "init-templatedir` into a directory of its own with `core.hooksPath` pointed "
        "at it. Nothing else installs them, and without them commits land "
        "unattributed and unchecked. Then read the root `CLAUDE.md` before touching "
        "anything.",
        "",
        f"The plan of record is {tracker or 'GitHub Issues'}, not this message. "
        f"{report.fill('tickets')}. Start there.",
        "",
        f"Expected initial state, not defects: {'; '.join(expected)}.",
        "",
        "The first root manifest owes the checks their tools: "
        f"{report.fill('first-manifest')}. An undeclared tool reports `unavailable`, "
        "which fails the run.",
        "",
        "Branch before you commit; a commit made on `main` is refused at the hook.",
        "```",
    )


def render_pr_body(arguments: argparse.Namespace) -> dict[str, object]:
    """Fill the candidate's pull-request template from the records.

    Headings are the template's `## ` lines in order, which the host would
    have rendered had the base carried one. What the records settle is
    written; a heading they do not cover becomes a `[[FILL: <name>]]` slot.
    """
    prefix = arguments.records
    materialized = load_required(prefix, "materialize")
    manifested = load_required(prefix, "manifest")
    configured = load_required(prefix, "settings")
    hooked = load_required(prefix, "hooks")
    listed = load_required(prefix, "filelist")
    check = required_record(prefix, "check.txt").read_text(encoding="utf-8")
    template_file = arguments.tree / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not template_file.is_file():
        raise PreflightError(f"missing {template_file}")
    headings = [
        line
        for line in template_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    template = require_git_repository(arguments.template_repo, "template repository")
    copy = listed["copy"]
    report = Report({}, SLOTS)
    applications = manifested.get("applications") or []
    sections = {
        "## Intent": [
            (
                "Generates this repository from the repository template at "
                f"{materialized['commit'][:12]}, recorded in `.repo-template.json`, onto "
                f"the empty root commit, with the applications {joined(applications)}."
            )
        ],
        "## Read first": [
            *(f"- `{path}`" for path in copy["authored"]),
            "",
            (
                f"The other {copy['identical']} copied paths are byte-identical to the "
                "payload at that commit and safe to skim."
            ),
        ],
        "## Decisions": [report.fill("boundaries")],
        "## Out of scope": [
            (
                "- The root manifest: wayfinding selects a language, not a package "
                "manager, version or layout, so the first real commit brings it."
            )
        ],
        "## Verified": [
            "`scripts/check` on the candidate:",
            "",
            "```",
            check.rstrip(),
            "```",
            "",
            copy_line(listed),
            hooks_line(hooked),
            *settings_lines(configured),
        ],
        "## Not verified": [
            (
                "- Code review skipped: the copied lines were reviewed in the template "
                "repository and the copy proof stands in for it; the authored surface "
                "is under Read first."
            ),
            (
                "- Workflows with no `pull_request` trigger, which this pull request "
                f"never ran: {joined(unrun_workflows(template, listed))}"
            ),
            "- The default branch's own run, which starts only once this merges.",
        ],
        "## Merge danger": [
            (
                "**Door:** two-way: a revert restores the tree; the settings, ruleset "
                "and labels were written before this pull request and stay either way"
            ),
            "",
            (
                "**Blast radius:** a new repository whose default branch holds only the "
                "empty root commit; nothing else reads it yet"
            ),
        ],
    }
    lines: list[str] = []
    for heading in headings:
        body = sections.get(heading)
        if body is None:
            name = heading[3:].lower()
            report.slots.append(name)
            body = [f"[[FILL: {name}]]"]
        lines += [heading, "", *body, ""]
    output = record_path(prefix, "pr-body.md")
    output.write_text("\n".join(lines), encoding="utf-8")
    return {"operation": "pr-body", "path": str(output), "slots": report.slots}


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

    def template_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--template-repo",
            type=Path,
            default=Path("."),
            help="the template checkout (default: the working directory)",
        )

    configured = subparsers.add_parser(
        "settings",
        parents=[recorded],
        help="apply step 5's settings and ruleset, then probe the ruleset",
    )
    configured.add_argument("--repository", required=True, help="owner/name")
    configured.add_argument("--default-branch", default="main")
    template_argument(configured)
    configured.set_defaults(handler=settings, record="settings")

    body = subparsers.add_parser(
        "pr-body",
        parents=[recorded],
        help="fill the candidate's pull-request template from the records",
    )
    body.add_argument("--tree", type=Path, required=True, help="the candidate")
    template_argument(body)
    body.set_defaults(handler=render_pr_body)

    published = subparsers.add_parser(
        "publish",
        parents=[recorded],
        help="push the candidate's branch and open its pull request",
    )
    published.set_defaults(handler=publish, record="publish")

    rendered = subparsers.add_parser(
        "report",
        parents=[recorded],
        help="render the final report and step 14's handover from the records",
    )
    rendered.add_argument("--repository", required=True, help="owner/name")
    rendered.add_argument(
        "--visibility", required=True, choices=["public", "private", "internal"]
    )
    rendered.add_argument("--stopped", help="what remains, on a stopped run")
    template_argument(rendered)
    rendered.set_defaults(handler=render_report)
    return parser


def fail(message: str, status: int = 2) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}, indent=2), file=sys.stderr)
    raise SystemExit(status)


def main() -> int:
    arguments = build_parser().parse_args()
    # A renderer writes Markdown, not a record of its own.
    name = getattr(arguments, "record", None)
    record = record_path(arguments.records, f"{name}.json") if name else None
    # A step that fails leaves no record, so a renderer never reads an earlier
    # run's result as this one's.
    if record:
        record.unlink(missing_ok=True)
    try:
        result = arguments.handler(arguments)
    except PreflightError as error:
        fail(str(error))
    # A step that ran and found defects sets `ok` false: recorded, exit 1.
    reported = {"ok": True, "schema_version": SCHEMA_VERSION, **result}
    output = json.dumps(reported, indent=2, sort_keys=True)
    if record:
        record.write_text(output + "\n")
    print(output)
    return 0 if reported["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
