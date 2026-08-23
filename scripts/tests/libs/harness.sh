# shellcheck shell=bash
# Assertion counting shared by scripts/tests/*-test.
#
# Sourced, never executed: no shebang, no executable bit, a .sh extension so
# linters recognize it. The same rule libs/detect.sh follows, for the same
# reason -- pre-commit reads a shebang only on an executable file, so a file
# carrying one without the bit is skipped in silence.
#
# Fixtures are deliberately not here. Each suite scaffolds a different world --
# manifests, a stubbed gh, a docs/adrs directory -- and the one thing they share
# is how an assertion is recorded. A fixture() forced into this file would take
# a parameter per suite and be read in three places to understand one.
#
# Tearing one down is the other way round: every suite builds its world in a
# mktemp directory and removes it the same way, so cleanup() lives here and the
# suites trap it. A suite needing more than this defines its own after sourcing
# -- capabilities-test does, because it cd's into the directory it is deleting.
#
# Callers use `set -uo pipefail` without -e: a failing assertion is recorded and
# the remaining cases still run, so one break does not hide the rest.

# Every suite here scaffolds throwaway Git repositories, and a fixture inherits
# the operator's global config unless told not to. One setting breaks them
# outright: a machine-wide core.hooksPath, set for an unrelated purpose such as
# an editor's Git integration or another agent's attribution hook, redirects
# every fixture's hooks away from .git/hooks. `pre-commit install` still reports
# success and the hook then never fires, so a suite asserting that a hook blocks
# a commit watches the commit succeed and reports the operator's config as a
# defect in this repository.
#
# Neutralize it by isolating the fixtures from user and system config entirely
# rather than by unsetting the one key. A fixture reading anything from outside
# the repository is the bug in general, and the empty-string override for this
# key specifically is a trap: `git config core.hooksPath ""` satisfies
# pre-commit's refusal check and installs, and the hook still does not run.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

passed=0
failed=0
current=""

# The scaffolding directory the current case is using, and empty between cases.
work=""

# Guarded on /tmp/* as well as on being set: this runs from an EXIT trap, where
# an rm -rf reached by an unexpected path has nothing left to stop it.
cleanup() {
  [[ -n "$work" && "$work" == /tmp/* ]] && rm -rf "$work"
  work=""
}

fail() {
  echo "  FAIL  $current: $1"
  failed=$((failed + 1))
}

pass() {
  passed=$((passed + 1))
}

# Prints the tally and returns the suite's exit status, so a caller ends with
# `report` as its last line and the script's status is the suite's result.
report() {
  echo
  echo "$passed passed, $failed failed"
  (( failed == 0 ))
}
