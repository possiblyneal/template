#!/usr/bin/env python3
"""Keep src/addon-adoption.json honest about src/repository-addons/.

The manifest is what lets the repo-builder skill walk an operator through the
regions of an adopted addon that must be edited. A manifest that has drifted
from the directory is worse than none: the walkthrough is silent about the file
it missed, and silence reads as "nothing to do here".

STDLIB ONLY, and that constraint is load-bearing rather than stylistic. This
file runs two ways -- under

    uv run --with pytest python -m pytest .claude/skills/repo-builder/scripts/tests/

and standalone from the addon-adoption pre-commit hook, which resolves no
dependencies at all. A pytest-only idiom added later still passes the first and
silently breaks the second.
"""

import json
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
ADDONS = REPOSITORY_ROOT / "apps/github-repository-template/src/repository-addons"
MANIFEST = REPOSITORY_ROOT / "apps/github-repository-template/src/addon-adoption.json"

# .gitkeep exists to make an empty directory survive Git, and is never adopted.
IGNORED = {".gitkeep"}


def addon_paths():
    """Every adoptable file, as a path relative to the addons directory."""
    return {
        str(path.relative_to(ADDONS))
        for path in ADDONS.rglob("*")
        if path.is_file() and path.name not in IGNORED
    }


def manifest_entries():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


class AddonAdoptionManifest(unittest.TestCase):
    def test_every_addon_has_an_entry(self):
        """A new addon without an entry is invisible to the walkthrough."""
        missing = sorted(addon_paths() - manifest_entries().keys())
        self.assertEqual(
            missing, [], f"addons with no entry in {MANIFEST.name}: {missing}"
        )

    def test_every_entry_names_a_real_addon(self):
        """`git rm` of an addon leaves an entry describing nothing."""
        orphaned = sorted(manifest_entries().keys() - addon_paths())
        self.assertEqual(
            orphaned, [], f"entries in {MANIFEST.name} with no such addon: {orphaned}"
        )

    def test_declared_slot_tokens_are_present_in_their_file(self):
        """An entry describing a token that was since edited away sends the
        operator looking for a string that is not there.

        This is deliberately one-directional. The reverse -- scanning for
        placeholder-shaped tokens the manifest does not declare -- cannot work
        here: CONTRIBUTORS.md contains the literal strings REPO-OWNER and
        ALL-CONTRIBUTORS-LIST:START inside prose *describing* them, so such a
        check fires on documentation about tokens. Any heuristic needs a
        suppression list, which is one more thing that drifts. File granularity
        plus declared-token presence is the honest ceiling.
        """
        for name, entry in sorted(manifest_entries().items()):
            path = ADDONS / name
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for slot in entry.get("slots", []):
                with self.subTest(addon=name, token=slot["token"]):
                    # assertTrue rather than assertIn: assertIn appends the
                    # entire haystack to the message, and this haystack is a
                    # whole file being printed into a pre-commit hook's output.
                    self.assertTrue(
                        slot["token"] in content,
                        f"{name} declares slot {slot['token']!r}, which is not in the file",
                    )

    def test_authored_on_adoption_files_ship_empty(self):
        """The flag means "you write this one". A populated file carrying it is
        claiming to be a blank the operator must fill, and hides real content."""
        for name, entry in sorted(manifest_entries().items()):
            if entry.get("authored_on_adoption"):
                with self.subTest(addon=name):
                    path = ADDONS / name
                    self.assertEqual(
                        path.stat().st_size if path.is_file() else 0,
                        0,
                        f"{name} is flagged authored_on_adoption but ships content",
                    )


if __name__ == "__main__":
    unittest.main()
