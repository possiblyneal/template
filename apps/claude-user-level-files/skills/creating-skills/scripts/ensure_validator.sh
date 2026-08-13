#!/usr/bin/env bash
#
# Ensure skill-validator is installed, and report when a newer release exists.
#
#   bash scripts/ensure_validator.sh              install if missing, else check for drift
#   bash scripts/ensure_validator.sh --upgrade    install the latest release now
#   bash scripts/ensure_validator.sh --check      only report drift, never install
#
# Installs a release tarball from github.com/agent-ecosystem/skill-validator into
# ~/.local/bin. Every download is verified against the release checksums file
# before anything is extracted or run.
#
# Drift checks are rate-limited by a stamp file so normal runs cost no network.
# When a newer release exists this reports it and exits 0 -- it never upgrades on
# its own, because new validator versions add new checks, and a skill that was
# clean should not start failing without you choosing that.

set -euo pipefail

REPO="agent-ecosystem/skill-validator"
BIN_DIR="${HOME}/.local/bin"
BIN="${BIN_DIR}/skill-validator"
STATE_DIR="${HOME}/.local/share/skill-validator"
STAMP="${STATE_DIR}/last-check"
TTL_SECONDS=$((7 * 24 * 60 * 60))

MODE="ensure"
case "${1:-}" in
    --upgrade) MODE="upgrade" ;;
    --check)   MODE="check" ;;
    "")        ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

die() { echo "error: $*" >&2; exit 1; }

for tool in curl tar sha256sum uname; do
    command -v "$tool" >/dev/null 2>&1 || die "required tool not found: $tool"
done

# Map this machine to a release asset name.
detect_platform() {
    local os arch
    case "$(uname -s)" in
        Linux)  os="linux" ;;
        Darwin) os="darwin" ;;
        *) die "unsupported OS: $(uname -s). Install manually from https://github.com/${REPO}/releases" ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64)  arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
        *) die "unsupported architecture: $(uname -m). Install manually from https://github.com/${REPO}/releases" ;;
    esac
    echo "${os}_${arch}"
}

latest_tag() {
    curl -fsSL --max-time 20 "https://api.github.com/repos/${REPO}/releases/latest" \
        | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
        | head -1
}

installed_version() {
    [ -x "$BIN" ] || return 1
    "$BIN" --version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1
}

install_release() {
    local tag="$1" platform version tmp tarball sums
    platform="$(detect_platform)"
    version="${tag#v}"

    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' RETURN

    local asset="skill-validator_${version}_${platform}.tar.gz"
    local base="https://github.com/${REPO}/releases/download/${tag}"
    tarball="${tmp}/${asset}"
    sums="${tmp}/checksums.txt"

    echo "Downloading ${asset} (${tag})..."
    curl -fsSL --max-time 120 -o "$tarball" "${base}/${asset}" \
        || die "download failed: ${base}/${asset}"
    curl -fsSL --max-time 30 -o "$sums" "${base}/skill-validator_${version}_checksums.txt" \
        || die "could not fetch checksums for ${tag}; refusing to install unverified binary"

    # Verify before extracting. A mismatch is fatal with no fallback path:
    # this binary is about to be executed.
    local expected actual
    expected="$(awk -v a="$asset" '$2 == a { print $1 }' "$sums")"
    [ -n "$expected" ] || die "no checksum listed for ${asset}; refusing to install"
    actual="$(sha256sum "$tarball" | awk '{print $1}')"
    if [ "$expected" != "$actual" ]; then
        die "checksum mismatch for ${asset}
  expected: ${expected}
  actual:   ${actual}
Refusing to install. Report this at https://github.com/${REPO}/issues"
    fi
    echo "Checksum verified: ${actual}"

    tar -xzf "$tarball" -C "$tmp"
    local extracted
    extracted="$(find "$tmp" -type f -name skill-validator -perm -u+x | head -1)"
    [ -n "$extracted" ] || die "skill-validator binary not found inside ${asset}"

    mkdir -p "$BIN_DIR"
    install -m 0755 "$extracted" "$BIN"
    echo "Installed ${tag} to ${BIN}"

    mkdir -p "$STATE_DIR"
    date +%s > "$STAMP"
}

stamp_is_fresh() {
    [ -f "$STAMP" ] || return 1
    local last now
    last="$(cat "$STAMP" 2>/dev/null || echo 0)"
    now="$(date +%s)"
    [ $((now - last)) -lt "$TTL_SECONDS" ]
}

# --upgrade: always fetch the latest, regardless of stamp or current version.
if [ "$MODE" = "upgrade" ]; then
    tag="$(latest_tag)" || die "could not reach the GitHub releases API"
    [ -n "$tag" ] || die "could not determine the latest release tag"
    install_release "$tag"
    exit 0
fi

current="$(installed_version || true)"

# Not installed: install it, unless the caller only wanted a report.
if [ -z "$current" ]; then
    if [ "$MODE" = "check" ]; then
        echo "skill-validator is not installed. Run: bash scripts/ensure_validator.sh"
        exit 0
    fi
    tag="$(latest_tag)" || die "could not reach the GitHub releases API"
    [ -n "$tag" ] || die "could not determine the latest release tag"
    install_release "$tag"
    exit 0
fi

# Installed. Skip the network entirely while the stamp is fresh.
if [ "$MODE" = "ensure" ] && stamp_is_fresh; then
    exit 0
fi

# Past the TTL: compare against the latest release. A network failure here is
# not fatal -- a working local binary matters more than a version check.
tag="$(latest_tag 2>/dev/null || true)"
mkdir -p "$STATE_DIR"
date +%s > "$STAMP"

if [ -z "$tag" ]; then
    echo "skill-validator ${current} installed (could not reach GitHub to check for updates)."
    exit 0
fi

if [ "$tag" != "$current" ]; then
    echo "skill-validator ${current} installed; ${tag} available."
    echo "Run: bash scripts/ensure_validator.sh --upgrade"
else
    echo "skill-validator ${current} is current."
fi
