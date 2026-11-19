"""Isolates every test's git from the operator's user and system config.

The suite scaffolds throwaway repositories and commits in them, and each
commit otherwise runs whatever the operator's global config names, such as a
core.hooksPath attribution hook: a fixture then reads state from outside the
repository, and the suite spent about a sixth of its time in that hook. This is
the isolation scripts/tests/libs/harness.sh gives the shell suites, and what a
CI runner has anyway. A test that needs a global config sets GIT_CONFIG_GLOBAL
in the environment it passes, which overrides this one.
"""

import os

os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
os.environ["GIT_CONFIG_SYSTEM"] = os.devnull
