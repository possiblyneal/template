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
    Outcome,
    Refusal,
    WriteLog,
    load_required,
    record_path,
    write_log_path,
    write_merge_settings,
    write_push_protection,
    write_ruleset,
    write_toggle,
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


# The `main` ruleset every generated repository starts with. Its required
# contexts are the job `name:` of each job in the payload's ci.yml and
# security.yml and of codeql.yml's `scanning`, which test_generate.py holds it
# to: a check run reports the job's `name:`, not its id, so a context spelled
# any other way stays pending and leaves the default branch never mergeable.
# An analyze leg is one context per language and release.yml never runs on a
# pull request, so neither is required.
RULESET = (
    Path(__file__).resolve().parents[3]
    / "github-repository-template"
    / "src"
    / "ruleset.json"
)
# The writes a plan or visibility can withhold. The host refuses them with 403
# or 422 then, which is a measurement rather than a failure.
PLAN_GATED = ("push-protection", "ruleset")


def ruleset_contexts() -> list[str]:
    body = json.loads(RULESET.read_text())
    return [
        check["context"]
        for rule in body["rules"]
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
    The probe runs only after a 201: on a refused ruleset an unprotected branch
    would take the probe commit with nothing proved.
    """
    repository = arguments.repository
    repository_name(repository)
    candidate = Path(load_required(arguments.records, "materialize")["candidate"])
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
        "ruleset": lambda: write_ruleset(repository, RULESET, None, log),
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
    probed = (
        probe(candidate, arguments.default_branch)
        if outcomes["ruleset"] == Outcome.DONE
        else None
    )
    return {
        "operation": "settings",
        "repository": repository,
        "default_branch": arguments.default_branch,
        "writes": outcomes,
        "reasons": reasons,
        "required_contexts": ruleset_contexts(),
        "probe": probed,
        "write_log": {"path": str(log.path), "entries": log.entries},
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

    configured = subparsers.add_parser(
        "settings",
        parents=[recorded],
        help="apply step 5's settings and ruleset, then probe the ruleset",
    )
    configured.add_argument("--repository", required=True, help="owner/name")
    configured.add_argument("--default-branch", default="main")
    configured.set_defaults(handler=settings, record="settings")
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
