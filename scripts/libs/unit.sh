# shellcheck shell=bash
# Which unit a command acts on, and what that unit declared.
#
# Source this after libs/detect.sh; do not execute it. Two commands take an
# optional unit name, cd into that unit, and dispatch on a fact the unit stated
# about itself -- scripts/run on how it runs, scripts/package on what it ships.
# Resolving and reading live here once rather than in two scripts that would
# drift, which is the failure libs/detect.sh already exists to prevent.
#
# The values are not validated here. scripts/structure checks every declared
# value against a fixed enum on every commit, so a second copy of the enums
# would be a second answer to the same question.

# Every unit under apps/, one per line. A unit is a directory directly under
# apps/, which is the shape scripts/structure enforces.
unit_names() {
  local entry
  for entry in apps/*/; do
    [[ -d "$entry" ]] || continue
    basename "$entry"
  done
}

# The units a caller could have named, as the command line that names them.
# $1 is the script's own name, so the listing is a line to copy rather than a
# hint to translate.
unit_list() {
  local command="$1" name
  local -a names=()
  mapfile -t names < <(unit_names)

  if (( ${#names[@]} == 0 )); then
    echo "apps/ has no entries yet."
    return
  fi

  echo "Available:"
  for name in "${names[@]}"; do
    echo "  scripts/$command $name"
  done
}

# The unit this invocation acts on, printed on stdout. $1 is the name given on
# the command line and may be empty; $2 is the calling script's own name.
#
# Empty output means apps/ holds no units at all, which is not an error: a
# repository can have work to run before it has anything to deploy, and the
# caller falls back to the repository root. One unit needs no naming; several
# do, because picking one would act on the wrong program as often as the right
# one.
unit_resolve() {
  local requested="$1" command="$2"
  local -a names=()
  mapfile -t names < <(unit_names)

  if [[ -n "$requested" ]]; then
    if [[ ! -d "apps/$requested" ]]; then
      echo "No apps/$requested directory." >&2
      unit_list "$command" >&2
      return 1
    fi
    echo "$requested"
    return 0
  fi

  case "${#names[@]}" in
    0) return 0 ;;
    1) echo "${names[0]}" ;;
    *)
      echo "apps/ holds several units, so which one has to be said." >&2
      unit_list "$command" >&2
      return 1
      ;;
  esac
}

# What the unit in the current directory declared, as the variables the
# capability adapters read. Call after cd'ing into the unit.
#
# jq rather than a shell parse, for the reason scripts/structure gives: reading
# a structured format by hand is how a check comes to accept one of several
# valid spellings and call the rest wrong.
unit_run=""
unit_ships=""
unit_targets=()

# The three are read by the run and package adapters in libs/detect.sh, which is
# a separate file, so nothing in this one uses them.
# shellcheck disable=SC2034
unit_read() {
  local file=.unit.json

  if [[ ! -s "$file" ]]; then
    echo "No $PWD/$file. A unit declares how it runs and what it ships, and" >&2
    echo "scripts/structure requires the file on every unit." >&2
    return 1
  fi

  if ! command -v jq > /dev/null 2>&1; then
    echo "jq is needed to read $file. scripts/doctor names it." >&2
    return 1
  fi

  unit_run="$(jq -r '.run' "$file")"
  unit_ships="$(jq -r '.ships.kind' "$file")"
  mapfile -t unit_targets < <(jq -r '.ships.targets // [] | .[]' "$file")
}
