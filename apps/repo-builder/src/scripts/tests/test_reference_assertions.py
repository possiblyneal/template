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
import shutil
import subprocess
import tempfile
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


# `](path.md#anchor)`, `](../path.md#anchor)` or a bare `](#anchor)`. A target
# with a scheme is somebody else's page and is left alone.
ANCHOR_LINK = re.compile(r"\]\(((?:[^)#\s:]*/)?[^)#\s:/]*)#([^)\s]+)\)")
CODE_SPAN = re.compile(r"`([^`]+)`")
FENCE = ("```", "~~~")


def unfenced_lines(path):
    """`(line number, line)` for every line outside a fenced code block.

    A fence may be indented, so the opener and closer are matched after
    stripping leading space.
    """
    fenced = False
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
        elif not fenced:
            yield number, line


def headings(path):
    """`(level, anchor, line number)` for a file's headings, as GitHub anchors them.

    Lowercase, drop everything but letters (any script), digits, underscores,
    spaces and hyphens, then turn each space into a hyphen -- so ` — ` becomes
    two hyphens. A heading whose anchor repeats gets `-1`, `-2`, ... in order.
    """
    seen = {}
    found = []
    for number, line in unfenced_lines(path):
        heading = re.match(r"(#{1,6}) +(.*)", line)
        if heading is None:
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading.group(2))
        anchor = re.sub(r"[^\w -]", "", text.replace("`", "").strip().lower())
        anchor = anchor.replace(" ", "-")
        count = seen.get(anchor, 0)
        seen[anchor] = count + 1
        found.append(
            (
                len(heading.group(1)),
                anchor if count == 0 else f"{anchor}-{count}",
                number,
            )
        )
    return found


def heading_slugs(path):
    return {anchor for _, anchor, _ in headings(path)}


def section(path, anchor):
    """The text from a heading to the next one of its level or higher, or None."""
    found = headings(path)
    lines = path.read_text().splitlines()
    for index, (level, name, number) in enumerate(found):
        if name != anchor:
            continue
        end = next(
            (n for lv, _, n in found[index + 1 :] if lv <= level), len(lines) + 1
        )
        return "\n".join(lines[number - 1 : end - 1])
    return None


def broken_anchor_links(files):
    """Every `path#anchor` link in `files` whose target or heading is absent."""
    slugs = {}
    broken = []
    for path in files:
        for line_number, line in unfenced_lines(path):
            for target, anchor in ANCHOR_LINK.findall(line):
                resolved = (path.parent / target).resolve() if target else path
                where = f"{path.name}:{line_number} {target}#{anchor}"
                if resolved.suffix != ".md":
                    continue
                if not resolved.is_file():
                    broken.append(f"{where} (no such file)")
                    continue
                if resolved not in slugs:
                    slugs[resolved] = heading_slugs(resolved)
                if anchor not in slugs[resolved]:
                    broken.append(where)
    return broken


def extract_mismatches(extract, source):
    """Code spans in `extract`'s bullets that the `source` section they link lacks."""
    missing = []
    for number, line in unfenced_lines(extract):
        anchors = [
            anchor
            for target, anchor in ANCHOR_LINK.findall(line)
            if target == source.name
        ]
        if not line.startswith("- ") or not anchors:
            continue
        sections = [section(source, anchor) or "" for anchor in anchors]
        for span in CODE_SPAN.findall(line):
            if not any(span in text for text in sections):
                missing.append(f"{extract.name}:{number} `{span}`")
    return missing


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

    def test_anchor_links_resolve(self):
        """A link to `file.md#anchor` must name a heading that file holds.

        A retrofit reads one lifecycle section through an anchor rather than
        the whole file, so a renamed heading leaves the step pointing at a
        section that is not there and nothing else notices. A path resolves
        against the directory of the file the link sits in, and a bare
        `(#anchor)` against that file itself. A link inside fenced code is an
        example, not a link.
        """
        broken = broken_anchor_links(reference_files())
        self.assertEqual(broken, [], f"links to headings that do not exist: {broken}")

    def test_inline_extracts_quote_their_source(self):
        """Every code span in a `retrofit.md` bullet is in the section it links.

        `retrofit.md` states lifecycle rules inline so a retrofit never opens
        `lifecycle.md`, and #230 asked that any extract a script can check
        stays in step with the source. What is mechanical is that each
        backticked span in a bullet linking `lifecycle.md#<anchor>` occurs
        verbatim in that section, heading line included; the prose around the
        spans is a paraphrase and is not compared.
        """
        missing = extract_mismatches(
            SKILL / "references/retrofit.md", SKILL / "references/lifecycle.md"
        )
        self.assertEqual(
            missing, [], f"extract spans the linked section does not hold: {missing}"
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


class AnchorHelpers(unittest.TestCase):
    """The link and extract checks, run over files built to break them."""

    def _tree(self, files):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        for name, text in files.items():
            (directory / name).parent.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(text)
        return directory

    def test_relative_links_resolve_against_the_linking_files_directory(self):
        root = self._tree(
            {
                "x.md": "# A\n",
                "sub/x.md": "# B\n",
                "sub/deep/y.md": "[ok](../x.md#b) [bad](../x.md#a) [up](../../x.md#a)\n",
                "z.md": "[ok](sub/x.md#b) [bad](sub/x.md#a) [gone](sub/nope.md#a)\n",
            }
        )
        broken = broken_anchor_links([root / "sub/deep/y.md", root / "z.md"])
        self.assertEqual(
            broken,
            [
                "y.md:1 ../x.md#a",
                "z.md:1 sub/x.md#a",
                "z.md:1 sub/nope.md#a (no such file)",
            ],
        )

    def test_duplicate_headings_take_numbered_anchors(self):
        root = self._tree({"a.md": "# Step\n\n## Step\n\n### Step\n"})
        self.assertEqual(heading_slugs(root / "a.md"), {"step", "step-1", "step-2"})

    def test_non_ascii_letters_stay_in_an_anchor(self):
        root = self._tree({"a.md": "## Café — Über `x`\n"})
        self.assertEqual(heading_slugs(root / "a.md"), {"café--über-x"})

    def test_links_and_headings_inside_fences_are_ignored(self):
        root = self._tree(
            {
                "a.md": (
                    "# Real\n\n- item\n  ```\n  # Fake\n  [x](#nowhere)\n  ```\n"
                    "~~~\n[y](#nowhere)\n~~~\n[z](#real)\n"
                )
            }
        )
        self.assertEqual(heading_slugs(root / "a.md"), {"real"})
        self.assertEqual(broken_anchor_links([root / "a.md"]), [])

    def test_an_extract_span_the_source_section_lacks_is_reported(self):
        root = self._tree(
            {
                "lifecycle.md": "## One\n\nUse `alpha`.\n\n## Two\n\n`beta`\n",
                "retrofit.md": (
                    "- Quotes [`## One`](lifecycle.md#one): `alpha`, `beta`.\n"
                    "- Prose with `gamma` and no link.\n"
                ),
            }
        )
        self.assertEqual(
            extract_mismatches(root / "retrofit.md", root / "lifecycle.md"),
            ["retrofit.md:1 `beta`"],
        )


if __name__ == "__main__":
    unittest.main()
