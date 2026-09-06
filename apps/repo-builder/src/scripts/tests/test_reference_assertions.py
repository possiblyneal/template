#!/usr/bin/env python3
"""Fail when a repo-builder reference asserts payload content that is not there.

The references are prose about a tree they do not live in. Nothing links the
two, so an edit to the payload leaves every sentence describing the old shape
still reading as instruction -- and the skill acts on instruction. The failure
mode is not a stale doc a reader shrugs at: a generate follows the reference,
looks for what it was told is there, and improvises when it is missing.

Only mechanical claims are checked. Whether a sentence is *right* about a file
is not decidable here; whether the file exists is.

STDLIB ONLY, for the same reason test_addon_adoption.py is: this runs under
pytest and standalone from a pre-commit hook that resolves no dependencies.
"""

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
PAYLOAD = REPOSITORY_ROOT / "apps/github-repository-template/src/base-repo"
ADDONS = REPOSITORY_ROOT / "apps/github-repository-template/src/repository-addons"
SKILL = REPOSITORY_ROOT / "apps/repo-builder/src"

# Prefixes whose meaning is unambiguous: a reference naming one of these is
# naming a destination path, never a path in this repository. `scripts/` and
# `libs/` are deliberately absent -- both trees have them, and a reference
# naming `scripts/preflight.py` means this unit's copy.
DESTINATION_PREFIXES = ("docs/agents/", "docs/adrs/", ".github/")

# Paths a reference names as arriving at a destination without the payload
# shipping them. Each needs a reason; a path with no reason is a defect, not an
# entry.
NOT_SHIPPED = {
    # Written by the payload's own adr-index hook during a generate's checks,
    # never copied. generate.md step 9 is where it appears.
    "docs/adrs/index.md",
}

HEADING = re.compile(r"`(#{1,6} [^`]+)`")
PATH = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*)`")


def reference_files():
    files = sorted(SKILL.glob("references/*.md")) + [SKILL / "SKILL.md"]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise AssertionError(f"expected reference files at {missing}")
    return files


class ReferenceAssertions(unittest.TestCase):
    def test_named_destination_paths_ship(self):
        """A destination path a reference names must be shipped or adoptable.

        The payload ships it, or repository-addons/ holds it for the occasion
        that calls for it. A path in neither is one the skill will look for in
        a tree that has never had it.
        """
        unshipped = []
        for reference in reference_files():
            for line_number, line in enumerate(
                reference.read_text().splitlines(), start=1
            ):
                for token in PATH.findall(line):
                    if not token.startswith(DESTINATION_PREFIXES):
                        continue
                    if token.endswith("/") or token in NOT_SHIPPED:
                        continue
                    if (PAYLOAD / token).exists() or (ADDONS / token).exists():
                        continue
                    unshipped.append(f"{reference.name}:{line_number} {token}")
        self.assertEqual(
            unshipped, [], f"references name paths no tree holds: {unshipped}"
        )

    def test_named_payload_headings_exist(self):
        """A Markdown heading a reference quotes must exist in the payload.

        A reference quoting `## Foo` is telling the skill to find, preserve, or
        rewrite that block. When the payload drops the heading the instruction
        does not become a no-op -- it becomes a search that fails partway
        through an operation.
        """
        headings = set()
        for path in PAYLOAD.rglob("*.md"):
            headings.update(
                line.strip()
                for line in path.read_text().splitlines()
                if line.startswith("#")
            )
        absent = []
        for reference in reference_files():
            for line_number, line in enumerate(
                reference.read_text().splitlines(), start=1
            ):
                for token in HEADING.findall(line):
                    if token not in headings:
                        absent.append(f"{reference.name}:{line_number} {token}")
        self.assertEqual(
            absent, [], f"references quote headings the payload lacks: {absent}"
        )


if __name__ == "__main__":
    unittest.main()
