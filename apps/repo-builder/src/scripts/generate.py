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
    WriteLog,
    hook_types,
    install_hooks,
    load_required,
    prior_hooks,
    record_path,
    write_labels,
    write_log_path,
)
from update import MANIFEST, copy_proof

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
