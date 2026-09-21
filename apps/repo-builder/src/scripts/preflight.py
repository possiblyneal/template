#!/usr/bin/env python3
"""Validate and describe repo-builder generate, update, adopt, and retrofit inputs."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NoReturn
from urllib.parse import urlparse

SCHEMA_VERSION = 1
FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
VALID_MODES = {"managed", "product"}
ADDON_PAIRS = {
    "CONTRIBUTORS.md": ".all-contributorsrc",
    ".all-contributorsrc": "CONTRIBUTORS.md",
    "CHANGELOG.md": ".claude/rules/changelog.md",
    ".claude/rules/changelog.md": "CHANGELOG.md",
    # One-directional, unlike the two above. AUTHORS lists the copyright
    # holders that the notices in the source tree point at, and a copyright
    # notice with no license beside it grants nothing. LICENSE without AUTHORS
    # is the ordinary case, so the reverse entry would be wrong.
    "AUTHORS": "LICENSE",
}
# The inverse: adopting both is the defect. `.nojekyll` turns off the Jekyll
# processor `_config.yml` exists to configure, and neither file complains --
# the site builds and its configuration is simply never read.
ADDON_EXCLUSIVE = {
    "_config.yml": ".nojekyll",
    ".nojekyll": "_config.yml",
}


class PreflightError(Exception):
    """An input failed a repo-builder safety check."""


@dataclass(frozen=True)
class OwnershipRule:
    path: str
    mode: str
    index: int


def run_git(
    repository: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=check,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise PreflightError("git is required but was not found") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or "git command failed"
        raise PreflightError(detail) from error


def git_output(repository: Path, *arguments: str) -> str:
    return run_git(repository, *arguments).stdout.strip()


def require_git_repository(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise PreflightError(
            f"{label} does not exist or is not a directory: {resolved}"
        )
    result = run_git(resolved, "rev-parse", "--git-dir", check=False)
    if result.returncode != 0:
        raise PreflightError(f"{label} is not a Git repository: {resolved}")
    return resolved


def resolve_commit(repository: Path, reference: str) -> str:
    commit = git_output(repository, "rev-parse", "--verify", f"{reference}^{{commit}}")
    if not FULL_COMMIT.fullmatch(commit):
        raise PreflightError(f"reference did not resolve to a full commit: {reference}")
    return commit


def require_subtree(repository: Path, commit: str, subtree: str) -> None:
    normalized = normalize_relative_path(subtree, "template subtree")
    result = run_git(
        repository, "cat-file", "-e", f"{commit}:{normalized}", check=False
    )
    if result.returncode != 0:
        raise PreflightError(
            f"template subtree does not exist at {commit}: {normalized}"
        )
    kind = git_output(repository, "cat-file", "-t", f"{commit}:{normalized}")
    if kind != "tree":
        raise PreflightError(
            f"template subtree is not a directory at {commit}: {normalized}"
        )


def branch_tips(repository: Path, branch: str) -> list[tuple[str, str]]:
    """Every ref a branch name legitimately means in a clone, remote first.

    A clone is fetched far more often than it is checked out, so `main` and
    `origin/main` routinely name different commits and neither is the wrong
    answer. Reading only the local ref refuses a commit newer than the last
    checkout, and refuses outright in a clone that fetched the branch without
    ever checking it out -- neither of which is a commit off the mainline.
    Reading only the remote ref would refuse a commit not yet pushed. Both are
    offered, and the caller accepts a commit on either.

    A plain branch name is the whole of the input, narrower than the arbitrary
    rev an earlier `resolve_commit` call took: `origin/main`, a tag, and `HEAD`
    are all refused here. A generate records its source as the base every later
    update diffs from, and an update targets a branch, so a tag or a detached
    `HEAD` names no lineage an update could follow back.
    """
    tips: list[tuple[str, str]] = []
    for reference in (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}"):
        result = run_git(
            repository, "rev-parse", "--verify", f"{reference}^{{commit}}", check=False
        )
        tip = result.stdout.strip()
        if result.returncode == 0 and FULL_COMMIT.fullmatch(tip):
            tips.append((reference, tip))
    return tips


def require_on_branch(repository: Path, commit: str, branch: str) -> str:
    """Refuse a source commit that is not on the template's own branch.

    A generate records the source as `template.commit`, and that commit is the
    base every later update diffs from -- `update` requires the recorded commit
    be a strict ancestor of the requested target. Pinning a generate to a commit
    off the template's mainline is therefore not a smaller mistake caught later:
    it is a repository that can never be updated, because no mainline target has
    the recorded commit in its history. Nothing in the generated repository says
    so, and the failure surfaces months on, in a flow that cannot repair it.
    """
    tips = branch_tips(repository, branch)
    if not tips:
        raise PreflightError(
            f"template branch {branch} resolves to no ref in {repository}; "
            "fetch it before generating"
        )
    declined: list[str] = []
    for reference, tip in tips:
        ancestry = run_git(
            repository, "merge-base", "--is-ancestor", commit, tip, check=False
        )
        if ancestry.returncode == 0:
            return tip
        # Exit 1 is the answer "no"; anything else is git declining to answer,
        # and reporting that as a commit off the branch sends the operator to
        # re-pin a commit when the repository is what needs attention. The
        # refusal waits until every ref has been tried: one ref git cannot read
        # is not a reason to ignore another that answers.
        if ancestry.returncode != 1:
            detail = ancestry.stderr.strip() or "git could not determine ancestry"
            declined.append(f"{reference}: {detail}")
    if declined:
        raise PreflightError(
            f"git could not determine whether {commit} is on {branch} in "
            f"{repository}: {'; '.join(declined)}"
        )
    resolved = ", ".join(f"{reference} {tip}" for reference, tip in tips)
    raise PreflightError(
        f"source commit {commit} is not on {branch} ({resolved}); a generate records "
        "it as the base every later update diffs from, so a commit off the "
        "template's own branch generates a repository no update can reach"
    )


def sibling_of_subtree(subtree: str, name: str) -> str:
    head = subtree.rsplit("/", 1)
    parent = head[0] if len(head) == 2 else ""
    return f"{parent}/{name}" if parent else name


def addon_manifest_files(
    repository: Path, commit: str, subtree: str
) -> dict[str, object]:
    """Read `addon-adoption.json`'s file map at a commit.

    The manifest is the only list of what the template holds back, so every
    flow asking which paths are addons asks it rather than carrying a copy
    that goes stale the next time an addon is added.
    """
    manifest_rel = sibling_of_subtree(subtree, "addon-adoption.json")
    existence = run_git(
        repository, "cat-file", "-e", f"{commit}:{manifest_rel}", check=False
    )
    if existence.returncode != 0:
        raise PreflightError(
            f"addon manifest does not exist at {commit}: {manifest_rel}"
        )
    raw = git_output(repository, "show", f"{commit}:{manifest_rel}")
    try:
        index = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PreflightError(
            f"addon manifest is invalid JSON at {commit}: {error.msg}"
        ) from error
    files = index.get("files") if isinstance(index, dict) else None
    if not isinstance(files, dict):
        raise PreflightError(
            f"addon manifest has no files object at {commit}: {manifest_rel}"
        )
    return files


def addons_already_held(present: set[str], addons: Iterable[str]) -> list[str]:
    """Name every addon-shaped path the destination already holds.

    A finding and never a decision. A retrofit adopts no addon, so what this
    answers is whether the operator already solved by hand what adopt would
    have offered; sorted so two runs over the same destination report the
    same line.

    Read from the paths git lists rather than from the filesystem, as every
    other retrofit finding is. An addon is a file the destination holds, and
    a bare existence test answers yes for a directory that shares the name,
    which is not an addon anyone wrote.
    """
    return sorted(addon for addon in addons if addon in present)


def require_addon(
    repository: Path, commit: str, subtree: str, addon: str
) -> dict[str, object]:
    addons_root = sibling_of_subtree(subtree, "repository-addons")
    blob = f"{addons_root}/{addon}"
    existence = run_git(repository, "cat-file", "-e", f"{commit}:{blob}", check=False)
    if existence.returncode != 0:
        raise PreflightError(f"addon does not exist at {commit}: {blob}")
    kind = git_output(repository, "cat-file", "-t", f"{commit}:{blob}")
    if kind != "blob":
        raise PreflightError(f"addon is not a file at {commit}: {blob}")
    files = addon_manifest_files(repository, commit, subtree)
    if addon not in files:
        raise PreflightError(f"addon has no addon-adoption.json entry: {addon}")
    entry = files[addon]
    if not isinstance(entry, dict):
        raise PreflightError(f"addon-adoption.json entry for {addon} must be an object")
    return entry


def normalize_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{label} must be a non-empty string")
    path = value.strip().replace("\\", "/").strip("/")
    if (
        not path
        or path == "."
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise PreflightError(f"{label} must be a normalized repository-relative path")
    return path


def require_string(mapping: dict[str, object], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def require_mapping(
    mapping: dict[str, object], key: str, label: str
) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise PreflightError(f"{label}.{key} must be an object")
    return value


def validate_overrides(manifest: dict[str, object]) -> dict[str, str]:
    """Read `generation.overrides` into path -> reason, refusing a malformed entry.

    The record is optional: a destination that has resolved no collision has
    no key at all, and that is not the same as an empty decision. What is
    refused is an entry nobody can act on later -- a path with no reason is
    not a decision anyone can review, and two entries for one path leave the
    next update with no single answer to read.
    """
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        raise PreflightError("manifest.generation must be an object")
    raw_overrides = generation.get("overrides")
    if raw_overrides is None:
        return {}
    if not isinstance(raw_overrides, list):
        raise PreflightError("manifest.generation.overrides must be an array")

    reasons: dict[str, str] = {}
    for index, raw_override in enumerate(raw_overrides):
        field = f"manifest.generation.overrides[{index}]"
        if not isinstance(raw_override, dict):
            raise PreflightError(f"{field} must be an object")
        override_path = normalize_relative_path(
            raw_override.get("path"), f"{field}.path"
        )
        reason = raw_override.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise PreflightError(f"{field}.reason must be a non-empty string")
        if override_path in reasons:
            raise PreflightError(
                f"manifest.generation.overrides contains duplicate path: {override_path}"
            )
        reasons[override_path] = reason
    return reasons


def require_managed_overrides(
    overrides: dict[str, str], rules: list[OwnershipRule]
) -> None:
    """Refuse an override on a path the ownership rules resolve as product.

    An override records that a *managed* collision was settled in the
    destination's favour, so an entry on a product path asserts nothing the
    rules did not already grant. It is not merely redundant: an overridden
    path leaves the product tally as well as the managed one, so the delta
    summary would under-report the destination's own files with no way for a
    reader to see why. Ownership resolves here exactly as it does in the
    delta, unmatched path included, so the two cannot disagree about which
    entries are legal.
    """
    for override_path in sorted(overrides):
        mode, rule = classify_path(override_path, rules)
        if mode == "managed":
            continue
        matched = (
            f"ownership rule {rule} (product)"
            if rule is not None
            else "no ownership rule, so it is product-owned"
        )
        raise PreflightError(
            f"manifest.generation.overrides names a product-owned path: "
            f"{override_path}, matched by {matched}; an override settles a "
            "managed collision, and a product path is the destination's already"
        )


REPLACED_OUTRIGHT_PATHS = (".gitignore",)
"""Payload paths the flows replace outright, under `lifecycle.md`'s Overridden
paths, so none can be an override."""


def refuse_replaced_outright_overrides(overrides: dict[str, str]) -> None:
    """Refuse an override on a path the flows replace outright.

    Separate from `require_managed_overrides` because ownership cannot settle
    it: `.gitignore` is managed, so the rules admit the entry and the mistake
    survives ownership alone.
    """
    for replaced_path in REPLACED_OUTRIGHT_PATHS:
        if replaced_path not in overrides:
            continue
        raise PreflightError(
            f"manifest.generation.overrides names a path the flows replace "
            f"outright: {replaced_path}; the payload's version lands and the "
            "destination's own rules are reported rather than re-added, so "
            "this is a merge to raise at the next update, not an override"
        )


def validate_manifest(
    path: Path,
) -> tuple[dict[str, object], list[OwnershipRule], dict[str, str]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PreflightError(f"manifest does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise PreflightError(
            f"manifest is invalid JSON at line {error.lineno}: {error.msg}"
        ) from error

    if not isinstance(manifest, dict):
        raise PreflightError("manifest root must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PreflightError(f"manifest schema_version must be {SCHEMA_VERSION}")

    template = require_mapping(manifest, "template", "manifest")
    destination = require_mapping(manifest, "destination", "manifest")
    require_string(template, "repository", "manifest.template")
    template["subtree"] = normalize_relative_path(
        template.get("subtree"), "manifest.template.subtree"
    )
    commit = require_string(template, "commit", "manifest.template")
    if not FULL_COMMIT.fullmatch(commit):
        raise PreflightError(
            "manifest.template.commit must be a full lowercase 40-character Git commit"
        )
    require_string(destination, "repository", "manifest.destination")
    require_string(destination, "default_branch", "manifest.destination")
    overrides = validate_overrides(manifest)

    raw_rules = manifest.get("ownership")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise PreflightError("manifest.ownership must be a non-empty array")
    rules: list[OwnershipRule] = []
    seen: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise PreflightError(f"manifest.ownership[{index}] must be an object")
        pattern = normalize_relative_path(
            raw_rule.get("path"), f"manifest.ownership[{index}].path"
        )
        mode = raw_rule.get("mode")
        if mode not in VALID_MODES:
            raise PreflightError(
                f"manifest.ownership[{index}].mode must be one of: {', '.join(sorted(VALID_MODES))}"
            )
        if pattern in seen:
            raise PreflightError(
                f"manifest.ownership contains duplicate path: {pattern}"
            )
        seen.add(pattern)
        rules.append(OwnershipRule(pattern, str(mode), index))
    require_managed_overrides(overrides, rules)
    refuse_replaced_outright_overrides(overrides)
    return manifest, rules, overrides


def host_repository_identity(host: str, path: str) -> str:
    normalized_path = path.strip("/")
    if host.lower() == "github.com":
        return normalized_path.lower()
    return f"{host.lower()}/{normalized_path}"


def normalize_repository_identity(value: str) -> str:
    candidate = value.strip().rstrip("/")
    candidate = candidate.removesuffix(".git")
    if candidate.startswith("git@") and ":" in candidate:
        host, path = candidate[4:].split(":", 1)
        return host_repository_identity(host, path)
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        return host_repository_identity(parsed.hostname or parsed.netloc, parsed.path)
    path = Path(candidate).expanduser()
    if path.is_absolute() or candidate.startswith(("./", "../")):
        return str(path.resolve())
    return candidate.lower()


def repository_identity(repository: Path) -> str:
    origin = run_git(repository, "remote", "get-url", "origin", check=False)
    if origin.returncode == 0 and origin.stdout.strip():
        return normalize_repository_identity(origin.stdout.strip())
    return normalize_repository_identity(str(repository))


def path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    return fnmatch.fnmatchcase(path, pattern)


def classify_path(path: str, rules: list[OwnershipRule]) -> tuple[str, str | None]:
    matches = [rule for rule in rules if path_matches(path, rule.path)]
    if not matches:
        return "product", None
    selected = max(matches, key=lambda rule: (len(rule.path), -rule.index))
    return selected.mode, selected.path


def parse_name_status(
    output: str, subtree: str, rules: list[OwnershipRule]
) -> list[dict[str, object]]:
    fields = output.split("\0") if output else []
    changes: list[dict[str, object]] = []
    index = 0
    prefix = f"{subtree.rstrip('/')}/"
    while index < len(fields) and fields[index]:
        status = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            old_source, new_source = fields[index], fields[index + 1]
            index += 2
        else:
            old_source = fields[index]
            new_source = old_source
            index += 1
        old_path = old_source.removeprefix(prefix)
        new_path = new_source.removeprefix(prefix)
        candidate_path = old_path if status.startswith("D") else new_path
        mode, rule = classify_path(candidate_path, rules)
        change: dict[str, object] = {
            "status": status,
            "path": candidate_path,
            "ownership": mode,
            "ownership_rule": rule,
        }
        if status.startswith(("R", "C")):
            change["old_path"] = old_path
            change["new_path"] = new_path
        changes.append(change)
    return changes


def mark_destination_state(
    changes: list[dict[str, object]],
    destination: Path,
    template_repo: Path,
    recorded: str,
    subtree: str,
) -> None:
    """Say whether the destination still holds the payload's old version.

    Every one of update's four reconciliation rules turns on this question,
    and without an answer here the flow reads the old payload, the new
    payload, and the destination in full for every delta path to settle it.
    It is a blob comparison: `unmodified` means the destination never touched
    the file, so the new payload version applies and no content needs
    reading at all. Only `modified` earns that read.

    The old path is what both sides are read at. A rename has not happened in
    the destination yet, so it holds the old name, and the payload's old
    version is under that name too. A path the payload adds has no old blob,
    which is why a destination file found there reads `modified`: it is
    content the payload did not ship, and deciding a collision needs the read.

    A path the record already settled is skipped: step 4 gives it none of the
    four rules, so computing a state for it is two git calls nothing reads.
    """
    prefix = subtree.rstrip("/")
    for change in changes:
        if change.get("overridden"):
            continue
        path = str(change.get("old_path", change["path"]))
        destination_file = destination / path
        if not destination_file.is_file():
            change["destination_state"] = "absent"
            continue
        destination_blob = git_output(
            destination, "hash-object", "--", str(destination_file)
        )
        old = run_git(
            template_repo,
            "rev-parse",
            "--verify",
            "--quiet",
            f"{recorded}:{prefix}/{path}",
            check=False,
        )
        old_blob = old.stdout.strip() if old.returncode == 0 else ""
        state = (
            "unmodified" if old_blob and old_blob == destination_blob else "modified"
        )
        # A rename carries a second destination path the rules weigh. An
        # untouched old name reads `unmodified` on its own, and step 3 takes
        # that as leave to apply the move without a read -- over whatever the
        # destination already keeps at the new name. Any entry there blocks the
        # move, a directory included, which is why this asks `exists` where the
        # old name asks `is_file`: that one is read as a blob and this one is
        # only in the way.
        new_path = change.get("new_path")
        if (
            state == "unmodified"
            and new_path
            and (destination / str(new_path)).exists()
        ):
            state = "modified"
        change["destination_state"] = state


def mark_overridden(
    changes: list[dict[str, object]],
    overrides: dict[str, str],
    destination_paths: set[str],
) -> None:
    """Mark each delta path the record already settled, reading both names.

    A path settled once against the payload is not a change to reconcile
    again, and marking it is what keeps it out of the managed tally the flow
    works through; lifecycle.md "Overridden paths" is the rule. A rename
    carries two names and the record was written against the one the
    destination already held, so a rename's source counts as well: matching
    the new path alone would re-raise a collision settled under the old one.
    The fallback reads a second name rather than a status, so it holds only
    while the diff detects renames alone: a copy's source still exists, and
    inheriting its entry would protect a file nothing is replacing.

    An entry whose path the destination no longer holds is expired, and
    expiry is decided here as well as in `unmatched_overrides` because the
    payload is as free to change an expired path as to leave it alone:
    marking such a delta path overridden would skip the payload's copy on
    behalf of a destination file that is gone. So it is marked expired
    instead, which leaves it an ordinary managed change to apply while
    naming the entry this update drops.
    """
    for change in changes:
        path = str(change["path"])
        reason = overrides.get(path)
        recorded_path = path
        if reason is None and "old_path" in change:
            recorded_path = str(change["old_path"])
            reason = overrides.get(recorded_path)
        if reason is None:
            continue
        if recorded_path in destination_paths:
            change["overridden"] = True
        else:
            change["override_expired"] = True
        change["override_reason"] = reason


def unmatched_overrides(
    changes: list[dict[str, object]],
    overrides: dict[str, str],
    destination_paths: set[str],
) -> list[dict[str, str]]:
    """Report each recorded override the bounded delta does not reach.

    An entry the delta touches is the ordinary case and is marked on the
    change itself, overridden or expired as `mark_overridden` reads it.
    What is left is an entry this update has nothing to say about, and the two reasons for that are worth telling apart, because only
    one of them ends the entry: `expired` where the destination no longer
    holds the path, so the record is settling a collision that cannot recur
    and the payload's version should land like any other managed delta;
    `unreached` where the file is still there and this delta simply passed it
    by. Both are settled from git alone -- the destination's tracked paths --
    so neither asks the flow to re-read the manifest by hand.

    A rename carries two names, and the record holds the one the destination
    had, so both are read here for the same reason `mark_overridden` reads
    them.
    """
    reached: set[str] = set()
    for change in changes:
        reached.add(str(change["path"]))
        if "old_path" in change:
            reached.add(str(change["old_path"]))
    return [
        {
            "path": override_path,
            "reason": reason,
            "state": "unreached" if override_path in destination_paths else "expired",
        }
        for override_path, reason in sorted(overrides.items())
        if override_path not in reached
    ]


def summarize_changes(changes: list[dict[str, object]]) -> dict[str, int]:
    """Count the delta three ways, each path in exactly one bucket.

    Overridden wins over ownership, so a settled path leaves the tally the
    flow works through rather than being counted twice. The three add up to
    `total`, and a reader treating `managed` as the work left depends on that.
    """
    return {
        "total": len(changes),
        "managed": sum(
            change["ownership"] == "managed" and not change.get("overridden")
            for change in changes
        ),
        "product": sum(
            change["ownership"] == "product" and not change.get("overridden")
            for change in changes
        ),
        "overridden": sum(bool(change.get("overridden")) for change in changes),
    }


def ensure_clean(repository: Path) -> None:
    dirty = git_output(repository, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        first = dirty.splitlines()[0]
        raise PreflightError(
            f"destination worktree must be clean; first change: {first}"
        )


def origin_identity(destination: Path) -> str:
    result = run_git(destination, "remote", "get-url", "origin", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise PreflightError("destination must have an origin remote")
    return normalize_repository_identity(result.stdout.strip())


@dataclass(frozen=True)
class Provenance:
    destination: Path
    template_repo: Path
    recorded: str
    subtree: str
    rules: list[OwnershipRule]
    overrides: dict[str, str]
    template_identity: str
    destination_identity: str
    destination_config: dict[str, object]


def load_provenance(arguments: argparse.Namespace) -> Provenance:
    """Load and verify the shared manifest provenance for update and adopt.

    A clean destination worktree, a schema-valid manifest, the recorded template
    commit and its subtree, and both recorded identities matching reality.
    """
    destination = require_git_repository(arguments.destination, "destination")
    ensure_clean(destination)
    manifest_path = destination / arguments.manifest
    manifest, rules, overrides = validate_manifest(manifest_path)
    template = require_mapping(manifest, "template", "manifest")
    destination_config = require_mapping(manifest, "destination", "manifest")

    template_repo = require_git_repository(
        arguments.template_repo, "template repository"
    )
    recorded = resolve_commit(
        template_repo, require_string(template, "commit", "manifest.template")
    )
    subtree = normalize_relative_path(
        template.get("subtree"), "manifest.template.subtree"
    )
    require_subtree(template_repo, recorded, subtree)

    recorded_template_identity = normalize_repository_identity(
        require_string(template, "repository", "manifest.template")
    )
    actual_template_identity = repository_identity(template_repo)
    if recorded_template_identity != actual_template_identity:
        raise PreflightError(
            "template repository identity differs from the manifest: "
            f"recorded {recorded_template_identity!r}, actual {actual_template_identity!r}"
        )

    recorded_destination_identity = normalize_repository_identity(
        require_string(destination_config, "repository", "manifest.destination")
    )
    actual_destination_identity = origin_identity(destination)
    if recorded_destination_identity != actual_destination_identity:
        raise PreflightError(
            "destination origin differs from the manifest: "
            f"recorded {recorded_destination_identity!r}, actual {actual_destination_identity!r}"
        )

    return Provenance(
        destination=destination,
        template_repo=template_repo,
        recorded=recorded,
        subtree=subtree,
        rules=rules,
        overrides=overrides,
        template_identity=recorded_template_identity,
        destination_identity=actual_destination_identity,
        destination_config=destination_config,
    )


def generation_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    template_repo = require_git_repository(
        arguments.template_repo, "template repository"
    )
    target = resolve_commit(template_repo, arguments.target)
    subtree = normalize_relative_path(arguments.subtree, "template subtree")
    require_subtree(template_repo, target, subtree)
    branch_tip = require_on_branch(template_repo, target, arguments.template_branch)
    return {
        "operation": "generate",
        "template": {
            "repository": repository_identity(template_repo),
            "subtree": subtree,
            "commit": target,
            "branch": arguments.template_branch,
            "branch_tip": branch_tip,
        },
        "destination": {
            "repository": arguments.destination_repository,
            "default_branch": arguments.default_branch,
        },
        "remote_actions_performed": False,
    }


def update_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    provenance = load_provenance(arguments)
    destination = provenance.destination
    template_repo = provenance.template_repo
    recorded = provenance.recorded
    subtree = provenance.subtree
    rules = provenance.rules
    destination_config = provenance.destination_config

    target = resolve_commit(template_repo, arguments.target)
    require_subtree(template_repo, target, subtree)

    ancestry = run_git(
        template_repo, "merge-base", "--is-ancestor", recorded, target, check=False
    )
    if ancestry.returncode == 1:
        raise PreflightError(
            f"recorded template commit {recorded} is not an ancestor of target {target}; "
            "choose a descendant target or establish a new baseline explicitly"
        )
    if ancestry.returncode != 0:
        detail = ancestry.stderr.strip() or "git could not determine ancestry"
        raise PreflightError(detail)

    diff = run_git(
        template_repo,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        recorded,
        target,
        "--",
        subtree,
    ).stdout
    changes = parse_name_status(diff, subtree, rules)
    destination_paths = set(listed_paths(destination))
    mark_overridden(changes, provenance.overrides, destination_paths)
    mark_destination_state(changes, destination, template_repo, recorded, subtree)
    return {
        "operation": "update",
        "template": {
            "repository": provenance.template_identity,
            "subtree": subtree,
            "recorded_commit": recorded,
            "target_commit": target,
            "recorded_is_ancestor": True,
        },
        "destination": {
            "path": str(destination),
            "repository": provenance.destination_identity,
            "default_branch": require_string(
                destination_config, "default_branch", "manifest.destination"
            ),
            "clean": True,
        },
        "changes": changes,
        "summary": summarize_changes(changes),
        "unmatched_overrides": unmatched_overrides(
            changes, provenance.overrides, destination_paths
        ),
        "remote_actions_performed": False,
    }


def adopt_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    provenance = load_provenance(arguments)
    destination = provenance.destination
    template_repo = provenance.template_repo
    recorded = provenance.recorded
    subtree = provenance.subtree
    rules = provenance.rules
    destination_config = provenance.destination_config

    requested: list[str] = []
    seen: set[str] = set()
    for raw_addon in arguments.addon:
        addon = normalize_relative_path(raw_addon, "addon")
        if addon not in seen:
            seen.add(addon)
            requested.append(addon)

    for addon in requested:
        pair = ADDON_PAIRS.get(addon)
        # Satisfied by the destination as well as by this run. The two-way
        # pairs are adopted together, but a one-way pair is acquired in
        # sequence -- AUTHORS arrives long after LICENSE did -- and requesting
        # the pair again is itself rejected below as already present. Reading
        # only `seen` makes that second adopt unreachable by either route.
        if pair and pair not in seen and not (destination / pair).exists():
            raise PreflightError(f"addon {addon} must be adopted with its pair {pair}")
        exclusive = ADDON_EXCLUSIVE.get(addon)
        if exclusive and exclusive in seen:
            raise PreflightError(f"addon {addon} cannot be adopted with {exclusive}")

    addons: list[dict[str, object]] = []
    for addon in requested:
        entry = require_addon(template_repo, recorded, subtree, addon)
        if (destination / addon).exists():
            raise PreflightError(f"addon already present in destination: {addon}")
        exclusive = ADDON_EXCLUSIVE.get(addon)
        # The same check across runs. One-at-a-time is the realistic sequence
        # for occasion-gated addons, and the second adopt is the harmful one:
        # taking .nojekyll into a repository already publishing through
        # _config.yml turns Jekyll off, and the exclude list stops applying to
        # a site that keeps building.
        if exclusive and (destination / exclusive).exists():
            raise PreflightError(
                f"addon {addon} cannot be adopted into a destination holding {exclusive}"
            )
        mode, rule = classify_path(addon, rules)
        addons.append(
            {
                "path": addon,
                "ownership": mode,
                "ownership_rule": rule,
                "adoption": entry,
            }
        )

    return {
        "operation": "adopt",
        "template": {
            "repository": provenance.template_identity,
            "subtree": subtree,
            "recorded_commit": recorded,
        },
        "destination": {
            "path": str(destination),
            "repository": provenance.destination_identity,
            "default_branch": require_string(
                destination_config, "default_branch", "manifest.destination"
            ),
            "clean": True,
        },
        "addons": addons,
        "summary": {
            "total": len(addons),
            "managed": sum(addon["ownership"] == "managed" for addon in addons),
            "product": sum(addon["ownership"] == "product" for addon in addons),
        },
        "remote_actions_performed": False,
    }


def require_named_origin(destination: Path, named: str) -> str:
    """Refuse a destination whose origin is not the repository that was named.

    Origin alone would do if a clone's directory always matched its repository,
    and it does not: a retrofit is run against a checkout an operator already
    had, under whatever name they gave it. Requiring the repository as an
    argument and agreeing it with origin is what settles which repository is
    about to be written to, before anything is written.
    """
    actual = origin_identity(destination)
    expected = normalize_repository_identity(named)
    if actual != expected:
        raise PreflightError(
            "destination origin differs from the named repository: "
            f"named {expected!r}, origin {actual!r}"
        )
    return actual


def require_tracked_clean(destination: Path) -> None:
    """Refuse a destination holding uncommitted edits to tracked files.

    Retrofit's own rule rather than `ensure_clean`, which counts untracked
    files too. A destination that has been developed in normally keeps
    untracked work deliberately -- a data directory, a scratch folder -- and
    refusing those refuses the ordinary case. An edit to a tracked file is the
    one that a retrofit's own writes would become indistinguishable from.
    """
    dirty = git_output(destination, "status", "--porcelain=v1", "--untracked-files=no")
    if dirty:
        first = dirty.splitlines()[0]
        raise PreflightError(
            f"destination has uncommitted changes to tracked files; first: {first}"
        )
    require_no_operation_in_progress(destination)


# A paused operation is named by a path git keeps rather than by anything
# `status --porcelain` prints, so `rev-parse --git-path` is what finds it.
# `rebase-merge` covers an interactive rebase, `rebase-apply` a `git am` or a
# non-interactive one.
IN_PROGRESS_PATHS = {
    "MERGE_HEAD": "a merge",
    "CHERRY_PICK_HEAD": "a cherry-pick",
    "REVERT_HEAD": "a revert",
    "rebase-merge": "a rebase",
    "rebase-apply": "a rebase or patch application",
}


def require_no_operation_in_progress(destination: Path) -> None:
    """Refuse a destination holding a paused merge, rebase, cherry-pick, or revert.

    A rebase stopped at an `edit` step has a clean index, so the tracked-files
    check above passes it. The operator's sequence is still half-applied, and a
    retrofit's commits would land inside it -- work that has to be unpicked
    from someone else's rebase rather than dropped with a branch.
    """
    for name, operation in IN_PROGRESS_PATHS.items():
        located = run_git(destination, "rev-parse", "--git-path", name, check=False)
        if located.returncode != 0:
            continue
        path = Path(located.stdout.strip())
        if not path.is_absolute():
            path = destination / path
        if path.exists():
            raise PreflightError(
                f"destination has {operation} in progress ({name} is present); "
                "finish or abort it before retrofitting"
            )


def nul_fields(repository: Path, *arguments: str) -> list[str]:
    """Read a `-z` listing without touching the paths it holds.

    `git_output` strips the whole output, which eats a leading space off the
    first path and a trailing one off the last. Only the empty field after the
    final separator is dropped here, so a path that is itself whitespace
    survives -- and a path git cannot name is a path a collision check must
    still see.
    """
    output = run_git(repository, *arguments).stdout
    return [entry for entry in output.split("\0") if entry]


def tree_paths(repository: Path, commit: str, subtree: str) -> list[str]:
    entries = nul_fields(
        repository, "ls-tree", "-r", "--name-only", "-z", commit, "--", subtree
    )
    prefix = f"{subtree.rstrip('/')}/"
    return sorted(entry.removeprefix(prefix) for entry in entries)


def listed_paths(destination: Path, *arguments: str) -> list[str]:
    return nul_fields(destination, "ls-files", "-z", *arguments)


def default_branch(destination: Path) -> str:
    """The branch a clone treats as its default, not the one it is sitting on.

    A retrofit runs against a checkout the operator already had, so HEAD is
    routinely a feature branch and reading it reports a rename is required for
    a repository whose default branch is already the wanted one. `origin/HEAD`
    is the local record of what the remote's default is. Only a clone writes
    it, so a destination built with `git init` and given its remote afterwards
    carries no such ref, and there the checked-out branch is the only answer
    available.
    """
    symbolic = run_git(
        destination, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False
    )
    recorded = symbolic.stdout.strip()
    if symbolic.returncode == 0 and recorded.startswith("origin/"):
        return recorded.removeprefix("origin/")
    return git_output(destination, "rev-parse", "--abbrev-ref", "HEAD")


def collision(
    path: str, present: set[str], tracked: set[str]
) -> dict[str, object] | None:
    """What a payload path would overwrite in the destination, if anything.

    A payload file does not only collide with a destination file of the same
    name. `ls-files` names neither a directory nor anything inside a submodule,
    so both escape a membership test and reach a retrofit that the preflight
    called safe: the directory fails the write outright, and the submodule
    takes it into a foreign repository. Both are the operator's to settle.
    """
    if path in present:
        return {"path": path, "tracked": path in tracked}
    for parent in PurePosixPath(path).parents:
        ancestor = str(parent)
        if ancestor in present:
            return {"path": path, "tracked": ancestor in tracked}
    under = [entry for entry in present if entry.startswith(f"{path}/")]
    if under:
        return {"path": path, "tracked": any(entry in tracked for entry in under)}
    return None


# The payload ships a placeholder unit for a generate to rename into the
# application's own name. A retrofit derives its units from what the
# destination already delivers, so it has no use for one -- and left in the
# payload list it is overlaid, because it is genuinely absent, and no later
# step retires it. Nothing downstream catches that: it is a well-formed empty
# unit, so the layout audit, the unit-declaration check and the unit-facts
# check all pass it, and the retrofitted repository ships a second unit
# delivering nothing, forever.
#
# Held out here rather than in the flow's prose because one list is both the
# absent set the overlay writes and the denominator of the copy proof. A
# retrofit skipping the path in one and counting it in the other reports a
# delivery gap against a path it declined to land on purpose.
PLACEHOLDER_UNIT_PREFIX = "apps/app-name/"


def retrofit_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    """Prove locally whether a destination can be retrofitted, and name the collisions.

    Every check here reaches git and nothing else. A retrofit's hosted writes
    are confirmed at the flow's own gate, where a failure can still be acted
    on; a preflight that contacted GitHub would be reporting on state it cannot
    hold still anyway.
    """
    template_repo = require_git_repository(
        arguments.template_repo, "template repository"
    )
    target = resolve_commit(template_repo, arguments.target)
    subtree = normalize_relative_path(arguments.subtree, "template subtree")
    require_subtree(template_repo, target, subtree)

    destination = require_git_repository(arguments.destination, "destination")
    destination_identity = require_named_origin(
        destination, arguments.destination_repository
    )

    manifest = normalize_relative_path(arguments.manifest, "manifest")
    if (destination / manifest).exists():
        raise PreflightError(
            f"destination already carries a template record at {manifest}; "
            "a repository with a record is updated rather than retrofitted"
        )

    require_tracked_clean(destination)

    payload = [
        path
        for path in tree_paths(template_repo, target, subtree)
        if not path.startswith(PLACEHOLDER_UNIT_PREFIX)
    ]
    tracked = set(listed_paths(destination))
    # Ignored files are untracked for this purpose: git cannot restore one
    # either, so landing the payload over it is the same unrecoverable
    # overwrite. They stay out of the untracked finding below, which is about
    # work the operator kept deliberately rather than build output.
    present = tracked | set(listed_paths(destination, "--others"))

    branch = default_branch(destination)
    return {
        "operation": "retrofit",
        "template": {
            "repository": repository_identity(template_repo),
            "subtree": subtree,
            "commit": target,
        },
        "destination": {
            "path": str(destination),
            "repository": destination_identity,
            "default_branch": branch,
            "rename_required": branch != arguments.default_branch,
            "path_count": len(tracked),
        },
        # --no-empty-directory keeps a directory holding nothing but ignored
        # files out of the finding. It is not work the operator kept, and
        # reporting it sends them to look at build output.
        "untracked": listed_paths(
            destination,
            "--others",
            "--exclude-standard",
            "--directory",
            "--no-empty-directory",
        ),
        # The delivery check has nothing else deterministic to verify against,
        # and absence has no runner: a payload file that never landed produces
        # a green run unless something holds the list it should have landed.
        "payload_paths": payload,
        # Findings only, and never a stop. Addons live in a sibling tree
        # rather than under the payload subtree, so a destination's own
        # readme never reaches `collisions` and nothing here is a path the
        # retrofit intends to land: the retrofit adopts no addon.
        "addons_present": addons_already_held(
            present, addon_manifest_files(template_repo, target, subtree)
        ),
        # Evidence, never a decision. Which side of a collision wins is read
        # from ownership rules that live in a record a retrofit writes at the
        # end, so there is nothing here to read them from.
        "collisions": [
            found
            for found in (collision(path, present, tracked) for path in payload)
            if found is not None
        ],
        "remote_actions_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="validate a generation source and destination plan"
    )
    generate.add_argument("--template-repo", type=Path, required=True)
    generate.add_argument("--target", required=True, help="template ref or commit")
    generate.add_argument("--subtree", required=True)
    generate.add_argument("--destination-repository", required=True, help="owner/name")
    generate.add_argument("--default-branch", default="main")
    generate.add_argument(
        "--template-branch",
        default="main",
        help="the template's own branch the source commit must be on (default: main)",
    )
    generate.set_defaults(handler=generation_preflight)

    update = subparsers.add_parser(
        "update", help="validate an update and classify its template delta"
    )
    update.add_argument("--template-repo", type=Path, required=True)
    update.add_argument(
        "--target", required=True, help="descendant template ref or commit"
    )
    update.add_argument("--destination", type=Path, required=True)
    update.add_argument(
        "--manifest", default=".repo-template.json", help="path relative to destination"
    )
    update.set_defaults(handler=update_preflight)

    adopt = subparsers.add_parser(
        "adopt",
        help="validate adopting a held-back repository addon at the recorded commit",
    )
    adopt.add_argument("--template-repo", type=Path, required=True)
    adopt.add_argument("--destination", type=Path, required=True)
    adopt.add_argument(
        "--addon",
        action="append",
        required=True,
        help="destination-relative addon path; repeat for each",
    )
    adopt.add_argument(
        "--manifest", default=".repo-template.json", help="path relative to destination"
    )
    adopt.set_defaults(handler=adopt_preflight)

    retrofit = subparsers.add_parser(
        "retrofit",
        help="validate retrofitting a repository that was never generated",
    )
    retrofit.add_argument("--template-repo", type=Path, required=True)
    retrofit.add_argument("--target", required=True, help="template ref or commit")
    retrofit.add_argument("--subtree", required=True)
    retrofit.add_argument("--destination", type=Path, required=True)
    retrofit.add_argument(
        "--destination-repository",
        required=True,
        help="owner/name; cross-checked against the destination's origin",
    )
    retrofit.add_argument("--default-branch", default="main")
    retrofit.add_argument(
        "--manifest", default=".repo-template.json", help="path relative to destination"
    )
    retrofit.set_defaults(handler=retrofit_preflight)
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
    print(json.dumps({"ok": True, **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
