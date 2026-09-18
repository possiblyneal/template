#!/usr/bin/env python3
"""Fail when a repo-builder reference asserts payload content that is not there.

The references are prose about a tree they do not live in. Nothing links the
two, so an edit to the payload leaves every sentence describing the old shape
still reading as instruction -- and the skill acts on instruction. The failure
mode is not a stale doc a reader shrugs at: a generate follows the reference,
looks for what it was told is there, and improvises when it is missing.

Only mechanical claims are checked -- a named destination path exists, a cited
decision record exists, a quoted heading exists, and every path the payload
ships is reached by an ownership rule. Whether a sentence is *right* about a
file it names is not decidable here; whether the file exists is.

The fourth claim reads two ownership manifests rather than the references --
this repository's `.repo-template.json` and the example in lifecycle.md -- and
belongs here for the same reason as the rest: the rule the references state is
that an unmatched path is product-owned, so a payload path no rule reaches
sits outside every update with nothing anywhere saying so.

STDLIB ONLY, for the same reason test_addon_adoption.py is: this runs under
pytest and standalone from a pre-commit hook that resolves no dependencies.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
PAYLOAD = REPOSITORY_ROOT / "apps/github-repository-template/src/base-repo"
ADDONS = REPOSITORY_ROOT / "apps/github-repository-template/src/repository-addons"
SKILL = REPOSITORY_ROOT / "apps/repo-builder/src"

# Prefixes whose meaning is unambiguous: a reference naming one of these is
# naming a destination path, never a path in this repository. `scripts/` and
# `libs/` are deliberately absent -- both trees have them, and a reference
# naming `scripts/preflight.py` means this unit's copy. So is `docs/adrs/`:
# the payload ships only the template there, and a reference citing a record
# is citing one of this repository's, checked separately below.
DESTINATION_PREFIXES = ("docs/agents/", ".github/")

# This repository's own decision records, cited by the references for the
# reasoning behind a rule rather than described as payload content.
ADR = re.compile(r"^docs/adrs/\d{4}-[a-z0-9-]+\.md$")

HEADING = re.compile(r"`(#{1,6} [^`]+)`")
PATH = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*)`")


def reaches(path, pattern):
    """preflight.py's path_matches, for the one shape the manifests use.

    A `/**` suffix reaches the directory and everything under it; anything
    else is the path itself. Kept here rather than imported for the
    stdlib-only reason above, and it must stay in step with `path_matches`.

    The `/**` branch is identical to `path_matches`; the fallback is where
    they diverge, since `path_matches` globs it and this compares it. That is
    what keeps this the narrower of the two while the manifests hold literal
    paths and `/**` alone. A rule in any other shape -- `.github/*.yml` --
    stops matching here, and the shipped paths under it are then reported
    unreached, which is a false alarm rather than a silent pass.
    """
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    return path == pattern


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
                    if token.endswith("/"):
                        continue
                    if (PAYLOAD / token).exists() or (ADDONS / token).exists():
                        continue
                    unshipped.append(f"{reference.name}:{line_number} {token}")
        self.assertEqual(
            unshipped, [], f"references name paths no tree holds: {unshipped}"
        )

    def test_cited_decision_records_exist(self):
        """A decision record a reference cites must be in this repository.

        The references carry the rules; docs/adrs/ carries why each rule is the
        way it is. A citation is the whole link between them, so a renamed or
        renumbered record leaves the rule with no reasoning behind it and
        nothing else notices.
        """
        absent = []
        for reference in reference_files():
            for line_number, line in enumerate(
                reference.read_text().splitlines(), start=1
            ):
                for token in PATH.findall(line):
                    if ADR.match(token) and not (REPOSITORY_ROOT / token).is_file():
                        absent.append(f"{reference.name}:{line_number} {token}")
        self.assertEqual(
            absent, [], f"references cite records that do not exist: {absent}"
        )

    def test_named_headings_exist(self):
        """A Markdown heading a reference quotes must exist somewhere readable.

        A reference quoting `## Foo` is telling the skill to find, preserve, or
        rewrite that block. When the block is gone the instruction does not
        become a no-op -- it becomes a search that fails partway through an
        operation.

        Two trees answer, because a quoted heading is one of two claims. A
        payload heading is content the flow acts on. A reference heading is an
        address one reference cites in another -- `generate.md`'s steps are
        headings so that a flow needing one step can extract it rather than
        read 30 KB, and a reference citing a step that no longer exists is the
        same broken search. Neither tree alone covers both.
        """
        headings = set()
        for path in list(PAYLOAD.rglob("*.md")) + reference_files():
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
            absent,
            [],
            f"references quote headings no payload or reference file holds: {absent}",
        )

    def test_every_shipped_path_is_reached_by_an_ownership_rule(self):
        """A shipped path no rule reaches is product-owned by default.

        Product is the safe default for a path the template does not ship and
        the wrong one for a path it does: the path sits outside every update,
        so a fix the template later makes to it arrives nowhere and the update
        reports success. A file at the repository root is where this bites,
        because no directory pattern reaches one.

        Both lists are checked. This repository's own manifest governs this
        repository, and lifecycle.md's is what a reader builds a destination's
        from -- an illustration that misses a shipped path teaches the miss.
        """
        shipped = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z", "--", str(PAYLOAD)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split("\0")
        prefix = f"{PAYLOAD.relative_to(REPOSITORY_ROOT)}/"
        paths = sorted(
            path.removeprefix(prefix) for path in shipped if path.startswith(prefix)
        )
        self.assertNotEqual(paths, [], "the payload ships nothing")

        for source, rules in self._ownership_lists().items():
            with self.subTest(manifest=source):
                unreached = [
                    path
                    for path in paths
                    if not any(reaches(path, pattern) for pattern in rules)
                ]
                self.assertEqual(
                    unreached,
                    [],
                    f"{source} reaches none of these shipped paths: {unreached}",
                )

    def _ownership_lists(self):
        """The two ownership lists, each as the set of its patterns.

        lifecycle.md's is read out of the fenced manifest rather than by
        importing preflight: this file is stdlib-only and runs standalone from
        a pre-commit hook, the same reason the rest of it is.
        """
        manifest = json.loads((REPOSITORY_ROOT / ".repo-template.json").read_text())
        lifecycle = (SKILL / "references/lifecycle.md").read_text()
        block = re.search(r"```json\n(\{.*?\n\})\n```", lifecycle, re.DOTALL)
        if block is None:
            raise AssertionError("lifecycle.md holds no fenced manifest example")
        example = json.loads(block.group(1))
        return {
            ".repo-template.json": [rule["path"] for rule in manifest["ownership"]],
            "lifecycle.md": [rule["path"] for rule in example["ownership"]],
        }


if __name__ == "__main__":
    unittest.main()
