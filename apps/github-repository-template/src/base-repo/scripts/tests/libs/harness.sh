# shellcheck shell=bash
# Assertion counting shared by scripts/tests/*-test.
#
# Sourced, never executed: no shebang, no executable bit, a .sh extension so
# linters recognize it. The same rule libs/detect.sh follows, for the same
# reason -- pre-commit reads a shebang only on an executable file, so a file
# carrying one without the bit is skipped in silence.
#
# Fixtures are deliberately not here. Each suite scaffolds a different world --
# manifests, a stubbed gh, a docs/adr directory -- and the one thing they share
# is how an assertion is recorded. A fixture() forced into this file would take
# a parameter per suite and be read in three places to understand one.
#
# Callers use `set -uo pipefail` without -e: a failing assertion is recorded and
# the remaining cases still run, so one break does not hide the rest.

passed=0
failed=0
current=""

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
