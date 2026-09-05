#!/usr/bin/env python3
"""Keep src/addon-adoption.json honest about src/repository-addons/.

The manifest is what lets the repo-builder skill walk an operator through the
regions of an adopted addon that must be edited. A manifest that has drifted
from the directory is worse than none: the walkthrough is silent about the file
it missed, and silence reads as "nothing to do here".

STDLIB ONLY, and that constraint is load-bearing rather than stylistic. This
file runs two ways -- under

    uv run --with pytest python -m pytest apps/repo-builder/src/scripts/tests/

and standalone from the addon-adoption pre-commit hook, which resolves no
dependencies at all. A pytest-only idiom added later still passes the first and
silently breaks the second.
"""

import json
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
ADDONS = REPOSITORY_ROOT / "apps/github-repository-template/src/repository-addons"
PAYLOAD = REPOSITORY_ROOT / "apps/github-repository-template/src/base-repo"
MANIFEST = REPOSITORY_ROOT / "apps/github-repository-template/src/addon-adoption.json"

# Payload-side only. A .gitkeep there holds an empty directory open for a
# generated repository to fill, and a shadowed one would overwrite a placeholder
# with a placeholder. On the addon side it is not ignored: an addon is a file
# someone copies by hand, a placeholder is not worth copying, and ignoring it
# here would exempt it from every check below -- entry coverage, payload
# shadowing, and the empty-file rule a one-byte placeholder already slips past.
PAYLOAD_IGNORED = {".gitkeep"}


def files_under(directory, ignore=frozenset()):
    """Every file in a tree, as a path relative to that tree's root.

    Raises rather than returning an empty set when the directory is missing: a
    moved or renamed tree would otherwise turn every comparison below into a
    comparison against nothing, and pass.
    """
    if not directory.is_dir():
        raise AssertionError(f"expected a directory at {directory}")
    return {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path.name not in ignore
    }


def addon_paths():
    """Every adoptable file, as a path relative to the addons directory."""
    return files_under(ADDONS)


def payload_paths():
    """Every file the payload ships, as a path relative to the subtree."""
    return files_under(PAYLOAD, PAYLOAD_IGNORED)


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

    def test_no_addon_shadows_a_payload_path(self):
        """An addon at a path the payload already ships overwrites that file
        instead of adding one, and every reader of the directory -- the
        walkthrough, the structure doc, an operator copying by hand -- reads it
        as an addition. Nothing else here would notice: the overwriting file is
        valid, the file it replaced was valid, and the difference only shows up
        as a setting that silently stopped applying in the generated repository.

        Adopting an addon is a copy into a tree that already has the payload in
        it, so the two namespaces have to stay disjoint. Guidance about a path
        the payload ships belongs in that payload file, commented out, the way
        .github/dependabot.yml carries the ecosystem entry to copy when a real
        manifest arrives.
        """
        shadowed = sorted(addon_paths() & payload_paths())
        self.assertEqual(
            shadowed, [], f"addons at a path the payload already ships: {shadowed}"
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

    def test_no_addon_ships_empty(self):
        """Every addon is a template, and a zero-byte file teaches nothing.

        An addon arrives at a destination as a copy someone reads before they
        edit it, and each carries its own guidance -- comments where the format
        has them, prose where it does not -- because the person adopting by hand
        has no manifest to read. A blank file gives them a name and a path and
        nothing else, and reads as a file whose content is still to come.

        This scans the directory rather than the manifest, and skips nothing:
        a placeholder holding an empty directory open is exactly the blank file
        this rule is about. An addon directory earns its place by holding
        something worth copying. Nothing here is ignored on the addon side --
        see PAYLOAD_IGNORED -- so a placeholder with a byte in it still has to
        earn an entry in the manifest.
        """
        blank = sorted(
            str(path.relative_to(ADDONS))
            for path in ADDONS.rglob("*")
            if path.is_file() and path.stat().st_size == 0
        )
        self.assertEqual(blank, [], f"addons shipping no content: {blank}")


if __name__ == "__main__":
    unittest.main()
