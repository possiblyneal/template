#!/usr/bin/env python3
"""Validate and describe repo-builder generation and update inputs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import NoReturn
from urllib.parse import urlparse

SCHEMA_VERSION = 1
FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
VALID_MODES = {"managed", "product"}


class PreflightError(Exception):
    """An input failed a repo-builder safety check."""


@dataclass(frozen=True)
class OwnershipRule:
    path: str
    mode: str
    index: int


def run_git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
        raise PreflightError(f"{label} does not exist or is not a directory: {resolved}")
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
    result = run_git(repository, "cat-file", "-e", f"{commit}:{normalized}", check=False)
    if result.returncode != 0:
        raise PreflightError(f"template subtree does not exist at {commit}: {normalized}")
    kind = git_output(repository, "cat-file", "-t", f"{commit}:{normalized}")
    if kind != "tree":
        raise PreflightError(f"template subtree is not a directory at {commit}: {normalized}")


def normalize_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{label} must be a non-empty string")
    path = value.strip().replace("\\", "/").strip("/")
    if not path or path == "." or any(part in {"", ".", ".."} for part in path.split("/")):
        raise PreflightError(f"{label} must be a normalized repository-relative path")
    return path


def require_string(mapping: dict[str, object], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def require_mapping(mapping: dict[str, object], key: str, label: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise PreflightError(f"{label}.{key} must be an object")
    return value


def validate_manifest(path: Path) -> tuple[dict[str, object], list[OwnershipRule]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PreflightError(f"manifest does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise PreflightError(f"manifest is invalid JSON at line {error.lineno}: {error.msg}") from error

    if not isinstance(manifest, dict):
        raise PreflightError("manifest root must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PreflightError(f"manifest schema_version must be {SCHEMA_VERSION}")

    template = require_mapping(manifest, "template", "manifest")
    destination = require_mapping(manifest, "destination", "manifest")
    require_string(template, "repository", "manifest.template")
    template["subtree"] = normalize_relative_path(template.get("subtree"), "manifest.template.subtree")
    commit = require_string(template, "commit", "manifest.template")
    if not FULL_COMMIT.fullmatch(commit):
        raise PreflightError("manifest.template.commit must be a full lowercase 40-character Git commit")
    require_string(destination, "repository", "manifest.destination")
    require_string(destination, "default_branch", "manifest.destination")
    if not isinstance(manifest.get("generation"), dict):
        raise PreflightError("manifest.generation must be an object")

    raw_rules = manifest.get("ownership")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise PreflightError("manifest.ownership must be a non-empty array")
    rules: list[OwnershipRule] = []
    seen: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise PreflightError(f"manifest.ownership[{index}] must be an object")
        pattern = normalize_relative_path(raw_rule.get("path"), f"manifest.ownership[{index}].path")
        mode = raw_rule.get("mode")
        if mode not in VALID_MODES:
            raise PreflightError(
                f"manifest.ownership[{index}].mode must be one of: {', '.join(sorted(VALID_MODES))}"
            )
        if pattern in seen:
            raise PreflightError(f"manifest.ownership contains duplicate path: {pattern}")
        seen.add(pattern)
        rules.append(OwnershipRule(pattern, str(mode), index))
    return manifest, rules


def host_repository_identity(host: str, path: str) -> str:
    normalized_path = path.strip("/")
    if host.lower() == "github.com":
        return normalized_path.lower()
    return f"{host.lower()}/{normalized_path}"


def normalize_repository_identity(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
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


def parse_name_status(output: str, subtree: str, rules: list[OwnershipRule]) -> list[dict[str, object]]:
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
        old_path = old_source[len(prefix):] if old_source.startswith(prefix) else old_source
        new_path = new_source[len(prefix):] if new_source.startswith(prefix) else new_source
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


def ensure_clean(repository: Path) -> None:
    dirty = git_output(repository, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        first = dirty.splitlines()[0]
        raise PreflightError(f"destination worktree must be clean; first change: {first}")


def origin_identity(destination: Path) -> str:
    result = run_git(destination, "remote", "get-url", "origin", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise PreflightError("destination must have an origin remote")
    return normalize_repository_identity(result.stdout.strip())


def generation_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    template_repo = require_git_repository(arguments.template_repo, "template repository")
    target = resolve_commit(template_repo, arguments.target)
    subtree = normalize_relative_path(arguments.subtree, "template subtree")
    require_subtree(template_repo, target, subtree)
    return {
        "operation": "generate",
        "template": {
            "repository": repository_identity(template_repo),
            "subtree": subtree,
            "commit": target,
        },
        "destination": {
            "repository": arguments.destination_repository,
            "default_branch": arguments.default_branch,
        },
        "remote_actions_performed": False,
    }


def update_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    destination = require_git_repository(arguments.destination, "destination")
    ensure_clean(destination)
    manifest_path = destination / arguments.manifest
    manifest, rules = validate_manifest(manifest_path)
    template = require_mapping(manifest, "template", "manifest")
    destination_config = require_mapping(manifest, "destination", "manifest")

    template_repo = require_git_repository(arguments.template_repo, "template repository")
    recorded = resolve_commit(template_repo, require_string(template, "commit", "manifest.template"))
    target = resolve_commit(template_repo, arguments.target)
    subtree = normalize_relative_path(template.get("subtree"), "manifest.template.subtree")
    require_subtree(template_repo, recorded, subtree)
    require_subtree(template_repo, target, subtree)

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

    ancestry = run_git(template_repo, "merge-base", "--is-ancestor", recorded, target, check=False)
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
    return {
        "operation": "update",
        "template": {
            "repository": recorded_template_identity,
            "subtree": subtree,
            "recorded_commit": recorded,
            "target_commit": target,
            "recorded_is_ancestor": True,
        },
        "destination": {
            "path": str(destination),
            "repository": actual_destination_identity,
            "default_branch": require_string(destination_config, "default_branch", "manifest.destination"),
            "clean": True,
        },
        "changes": changes,
        "summary": {
            "total": len(changes),
            "managed": sum(change["ownership"] == "managed" for change in changes),
            "product": sum(change["ownership"] == "product" for change in changes),
        },
        "remote_actions_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="validate a generation source and destination plan")
    generate.add_argument("--template-repo", type=Path, required=True)
    generate.add_argument("--target", required=True, help="template ref or commit")
    generate.add_argument("--subtree", required=True)
    generate.add_argument("--destination-repository", required=True, help="owner/name")
    generate.add_argument("--default-branch", default="main")
    generate.set_defaults(handler=generation_preflight)

    update = subparsers.add_parser("update", help="validate an update and classify its template delta")
    update.add_argument("--template-repo", type=Path, required=True)
    update.add_argument("--target", required=True, help="descendant template ref or commit")
    update.add_argument("--destination", type=Path, required=True)
    update.add_argument("--manifest", default=".repo-template.json", help="path relative to destination")
    update.set_defaults(handler=update_preflight)
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
