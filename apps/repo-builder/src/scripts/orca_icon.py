#!/usr/bin/env python3
"""Register a clone in Orca and give it an emoji icon, keeping one it already has."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

# Orca's runtime rejects an emoji longer than this, without saying so: the
# update succeeds and the icon is simply dropped.
EMOJI_MAX_LENGTH = 16
TIMEOUT_SECONDS = 10


class OrcaUnavailable(Exception):
    """The runtime could not be reached; the icon is unset, not wrong."""


def user_data_path() -> Path:
    # Mirrors the orca CLI's getDefaultUserDataPath, so this reaches the same
    # runtime `orca repo add` just registered the repository with.
    if override := os.environ.get("ORCA_USER_DATA_PATH"):
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "orca"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "orca"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "orca"


def call(method: str, params: dict[str, object]) -> dict[str, Any]:
    """Send one request over the runtime's unix socket and return its response.

    The orca CLI has no flag for a repository icon, so this speaks the
    newline-delimited JSON protocol the CLI itself uses.
    """
    metadata_path = user_data_path() / "orca-runtime.json"
    try:
        metadata = json.loads(metadata_path.read_text())
    except (OSError, ValueError) as error:
        raise OrcaUnavailable(f"cannot read {metadata_path}: {error}") from error
    endpoint = next(
        (
            t["endpoint"]
            for t in metadata.get("transports", [])
            if t.get("kind") == "unix"
        ),
        None,
    )
    if endpoint is None:
        raise OrcaUnavailable(f"{metadata_path} lists no unix transport")
    request = {
        "id": str(uuid.uuid4()),
        "authToken": metadata.get("authToken"),
        "method": method,
        "params": params,
    }
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(TIMEOUT_SECONDS)
            connection.connect(endpoint)
            connection.sendall(json.dumps(request).encode() + b"\n")
            buffer = b""
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    raise OrcaUnavailable(
                        "runtime closed the connection without answering"
                    )
                buffer += chunk
                *lines, buffer = buffer.split(b"\n")
                for line in lines:
                    response = json.loads(line)
                    # The runtime interleaves keepalive frames with the answer.
                    if not response.get("_keepalive"):
                        return response
    except OSError as error:
        raise OrcaUnavailable(
            f"cannot reach the runtime at {endpoint}: {error}"
        ) from error


def register(repository: Path) -> tuple[str, dict[str, Any]]:
    """Add the clone to Orca unless it is there, returning how and its record."""
    response = call("repo.show", {"repo": f"path:{repository}"})
    if response.get("ok"):
        return "already", response["result"]["repo"]
    if (response.get("error") or {}).get("code") != "repo_not_found":
        raise ValueError(f"runtime refused the lookup: {response.get('error')}")
    response = call("repo.add", {"path": str(repository)})
    if not response.get("ok"):
        raise ValueError(f"runtime refused the add: {response.get('error')}")
    return "added", response["result"]["repo"]


def utf16_length(text: str) -> int:
    """Length as Orca's validator counts it: UTF-16 code units, not code points."""
    return len(text.encode("utf-16-le")) // 2


def update_icon(repository: Path, emoji: str) -> dict[str, Any]:
    """Store `emoji` as the clone's icon, failing unless the runtime kept it."""
    response = call(
        "repo.update",
        {
            "repo": f"path:{repository}",
            "updates": {"repoIcon": {"type": "emoji", "emoji": emoji}},
        },
    )
    if not response.get("ok"):
        raise ValueError(f"runtime refused the update: {response.get('error')}")
    icon = response["result"]["repo"].get("repoIcon")
    if icon != {"type": "emoji", "emoji": emoji}:
        raise ValueError(f"runtime answered ok but stored {icon!r}")
    return icon


def set_icon(repository: Path, emoji: str) -> dict[str, Any]:
    """Register the clone and give it `emoji`, unless it already has an emoji.

    An emoji already there was chosen by someone, so it stays. Any other icon,
    such as the owner avatar Orca fills in for a GitHub remote, is replaced.
    A failure after registering returns rather than raises, so the result still
    says the clone was registered.
    """
    emoji = emoji.strip()
    if not emoji or utf16_length(emoji) > EMOJI_MAX_LENGTH:
        raise ValueError(
            f"emoji must be 1-{EMOJI_MAX_LENGTH} UTF-16 units, got {emoji!r}"
        )
    # Orca normalizes `path:` selectors without following symlinks.
    repository = Path(os.path.abspath(repository))
    registered, repo = register(repository)
    result = {"repository": str(repository), "registered": registered}
    existing = repo.get("repoIcon")
    if isinstance(existing, dict) and existing.get("type") == "emoji":
        return {**result, "ok": True, "status": "kept", "icon": existing}
    try:
        icon = update_icon(repository, emoji)
    except OrcaUnavailable as error:
        return {**result, "ok": False, "status": "unavailable", "error": str(error)}
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        return {**result, "ok": False, "status": "failed", "error": str(error)}
    return {**result, "ok": True, "status": "set", "icon": icon}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path, help="the clone")
    parser.add_argument("--emoji", required=True)
    parser.add_argument(
        "--records",
        type=Path,
        help="a retrofit's records prefix; the result is also written to <records>.orca.json",
    )
    arguments = parser.parse_args()
    record = (
        arguments.records.with_name(f"{arguments.records.name}.orca.json")
        if arguments.records
        else None
    )
    if record:
        record.unlink(missing_ok=True)
    result: dict[str, Any]
    try:
        result = set_icon(arguments.repository, arguments.emoji)
        status = 0 if result["ok"] else 3 if result["status"] == "unavailable" else 2
    except OrcaUnavailable as error:
        result, status = {"ok": False, "status": "unavailable", "error": str(error)}, 3
    # An answer of an unexpected shape is a refusal too, so the record is written.
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        result, status = {"ok": False, "status": "failed", "error": str(error)}, 2
    output = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if record:
        record.write_text(output + "\n")
    print(output)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
