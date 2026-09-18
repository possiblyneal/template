# shellcheck shell=bash
# Which manifests Dependabot is watching, and which tracked ones it is not.
# Sourced by scripts/doctor, which reports the gap.
#
# Sourced, never executed: no shebang, no executable bit, a .sh extension so
# linters recognize it. The same rule libs/detect.sh follows, for the same
# reason.
#
# This is not in libs/detect.sh. That module owns language-specific decisions
# and is dispatched by language_capabilities, which answers whether a language
# is present from its *root* manifest. The question here is a different one --
# where every manifest sits, including the nested ones a root workspace file
# points at -- and the answer is a path rather than a yes.
#
# The gap this closes is silent. Dependabot's security half reads the
# dependency graph and needs no entry, so a dependency with an advisory still
# gets a pull request; a dependency with nothing yet wrong with it never does,
# and ages until something is. Nothing else reports it: the file is valid YAML,
# CI is green, and the only visible symptom is a bump that never arrives.

# The manifest filenames Dependabot reads, and the package-ecosystem each one
# earns: dependabot_ecosystem_of <basename>, empty for anything else.
#
# Deliberately the same six languages the rest of the template detects. A
# seventh recognized here and nowhere else is a shape no other check can see,
# so a manifest outside this list is reported as unwatched rather than mapped.
#
# go.work and settings.gradle.kts are absent on purpose. They are workspace
# files: they say where the modules are, and the modules are what Dependabot
# reads. An entry pointed at a workspace file's directory names no manifest and
# fails the whole run with dependency_file_not_found.
dependabot_ecosystem_of() {
  case "$1" in
    package.json) printf 'npm\n' ;;
    pyproject.toml) printf 'pip\n' ;;
    go.mod) printf 'gomod\n' ;;
    Cargo.toml) printf 'cargo\n' ;;
    build.gradle.kts) printf 'gradle\n' ;;
    Package.swift) printf 'swift\n' ;;
    *) return 0 ;;
  esac
}

# The (ecosystem, directory) pairs the config watches, one per line, tab
# separated. A `directories` list contributes one pair per member.
#
# Parsed rather than grepped, for the reason libs/precommit.sh gives at length:
# both the singular and plural keys are valid, and a hand-edit or a formatter
# turns one into the other. Reading only `directory:` misses every entry
# written the other way and reports its manifest unwatched, which is a check
# inventing a gap rather than finding one.
#
# A comment is stripped before the line is read, so the prose at the top of the
# file -- which names every ecosystem, including the ones no entry lists --
# cannot be mistaken for configuration.
dependabot_watched_pairs() {
  local config="$1"
  local line ecosystem="" in_directories=0

  [[ -s "$config" ]] || return 0

  while IFS= read -r line; do
    line="${line%%#*}"

    if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*package-ecosystem:[[:space:]]*(.+)$ ]]; then
      ecosystem="${BASH_REMATCH[1]//[[:space:]]/}"
      ecosystem="${ecosystem//\"/}"
      ecosystem="${ecosystem//\'/}"
      in_directories=0
      continue
    fi

    if [[ "$line" =~ ^[[:space:]]*directory:[[:space:]]*(.+)$ ]]; then
      in_directories=0
      _dependabot_emit_pair "$ecosystem" "${BASH_REMATCH[1]}"
      continue
    fi

    if [[ "$line" =~ ^[[:space:]]*directories:[[:space:]]*$ ]]; then
      in_directories=1
      continue
    fi

    if (( in_directories )); then
      if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*(.+)$ ]]; then
        _dependabot_emit_pair "$ecosystem" "${BASH_REMATCH[1]}"
        continue
      fi
      in_directories=0
    fi
  done < "$config"

  return 0
}

_dependabot_emit_pair() {
  local ecosystem="$1" directory="$2"

  directory="${directory//[[:space:]]/}"
  directory="${directory//\"/}"
  directory="${directory//\'/}"

  [[ -n "$ecosystem" && -n "$directory" ]] || return 0
  printf '%s\t%s\n' "$ecosystem" "$directory"
}

# Every tracked manifest with no entry watching it, one path per line.
#
# Tracked files rather than a search of the working tree. What Dependabot reads
# is the pushed tree, so `git ls-files` is not an approximation of the right
# answer, it is the right answer -- and a pruned search is not: DETECT_PRUNE_DIRS
# was written for root-manifest detection and names no agent or tool directory,
# so a gitignored checkout of this same repository sitting in one contributes
# manifests that are not in the repository at all.
#
# The directory is matched as a glob, because `directories` accepts one:
# /.github/actions/* is how the shipped github-actions entry reaches the
# composite actions, and a literal comparison would read that entry as watching
# a directory named "*".
dependabot_unwatched_manifests() {
  local config="$1"
  local manifest directory ecosystem pair watched_ecosystem watched_directory
  local -a pairs=()

  [[ -s "$config" ]] || return 0

  mapfile -t pairs < <(dependabot_watched_pairs "$config")

  while IFS= read -r manifest; do
    [[ -n "$manifest" ]] || continue

    ecosystem="$(dependabot_ecosystem_of "${manifest##*/}")"
    [[ -n "$ecosystem" ]] || continue

    directory="/${manifest%/*}"
    [[ "$manifest" == */* ]] || directory="/"

    for pair in ${pairs[@]+"${pairs[@]}"}; do
      IFS=$'\t' read -r watched_ecosystem watched_directory <<< "$pair"
      [[ "$watched_ecosystem" == "$ecosystem" ]] || continue
      # shellcheck disable=SC2053  # the right-hand side is a glob on purpose
      if [[ "$directory" == $watched_directory ]]; then
        continue 2
      fi
    done

    printf '%s\n' "$manifest"
  done < <(git ls-files 2>/dev/null)

  return 0
}
