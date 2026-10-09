#!/usr/bin/env python3
"""Keep the payload CLAUDE.md's Template Contract true to the payload's code.

The contract is the only description of the layout a generated repository's
agent reads, and it restates lists that `scripts/structure` holds as code. When
one changes without the other, the agent is told a rule the gate does not
enforce, or is never told one it does, and learns it by failing the commit.

Only the enumerations are checked: the root folders, the root files, the
scoped folders, the deploy technologies, the unit declaration's vocabulary, and
that every command named exists. Whether a sentence describes its rule well is
not decidable here; whether its list matches the code is.

STDLIB ONLY, matching the other tests in this directory.
"""

import json
import os
import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
PAYLOAD = REPOSITORY_ROOT / "apps/github-repository-template/src/base-repo"
CONTRACT = PAYLOAD / "CLAUDE.md"
STRUCTURE = PAYLOAD / "scripts/structure"

CODE_SPAN = re.compile(r"`([^`]+)`")


def bash_array(name):
    """The words of `name=( ... )` in scripts/structure, comments dropped."""
    match = re.search(
        rf"^{name}=\((.*?)\)", STRUCTURE.read_text(), re.MULTILINE | re.DOTALL
    )
    if match is None:
        raise AssertionError(f"scripts/structure defines no {name} array")
    words = []
    for line in match.group(1).splitlines():
        words += line.split("#", 1)[0].split()
    return set(words)


def json_list(name):
    """The JSON list assigned to `name='[...]'` in scripts/structure."""
    match = re.search(rf"^{name}='(\[.*?\])'", STRUCTURE.read_text(), re.MULTILINE)
    if match is None:
        raise AssertionError(f"scripts/structure defines no {name} list")
    return set(json.loads(match.group(1)))


def contract_line(prefix):
    """The one contract line starting with `prefix`, as its code spans."""
    lines = [
        line for line in CONTRACT.read_text().splitlines() if line.startswith(prefix)
    ]
    if len(lines) != 1:
        raise AssertionError(
            f"expected one contract line starting {prefix!r}, found {len(lines)}"
        )
    return CODE_SPAN.findall(lines[0])


def section(heading):
    """The text under `heading` up to the next heading of any level."""
    text = CONTRACT.read_text()
    start = text.index(f"{heading}\n")
    end = re.compile(r"^#", re.MULTILINE).search(text, start + len(heading))
    return text[start : end.start() if end else len(text)]


class TemplateContractTest(unittest.TestCase):
    def test_root_folders_match_the_audit(self):
        named = {span.rstrip("/") for span in contract_line("- Root holds only")}
        self.assertEqual(named, bash_array("root_folders"))

    def test_named_root_files_are_permitted(self):
        named = set(contract_line("- Root files are permitted by name"))
        self.assertLessEqual(named, bash_array("root_files"))

    def test_scoped_folders_match_the_audit(self):
        spans = contract_line("- A root, unit, or domain may hold its own")
        named = {span.rstrip("/") for span in spans if span != "src/"}
        self.assertEqual(named, bash_array("scoped_folders"))

    def test_deploy_folders_match_the_audit(self):
        spans = contract_line("- `deploy/` holds only")[1:]
        self.assertEqual(
            {span.rstrip("/") for span in spans}, bash_array("deploy_folders")
        )

    def test_run_values_match_the_audit(self):
        named = set(contract_line("- `run`:")) - {"run"}
        self.assertEqual(named, json_list("unit_runs"))

    def test_ships_values_match_the_audit(self):
        named = set(contract_line("- `ships.kind`:")) - {"ships.kind", "ships.targets"}
        self.assertEqual(named, json_list("unit_kinds") | json_list("unit_targets"))

    def test_example_declaration_is_valid(self):
        example = re.search(r"```json\n(.*?)\n```", CONTRACT.read_text(), re.DOTALL)
        if example is None:
            self.fail("the contract shows no .unit.json example")
        declaration = json.loads(example.group(1))
        self.assertIn(declaration["run"], json_list("unit_runs"))
        self.assertIn(declaration["ships"]["kind"], json_list("unit_kinds"))
        self.assertLessEqual(
            set(declaration["ships"].get("targets", [])), json_list("unit_targets")
        )

    def test_every_named_command_exists(self):
        commands = section("### Commands")
        names = {
            span.split()[0].removeprefix("scripts/")
            for span in CODE_SPAN.findall(commands)
            if span.startswith("scripts/")
        }
        such_as = re.search(r"`ls scripts/` lists the rest, such as (.*)\.", commands)
        if such_as is None:
            self.fail("the Commands section lost its `ls scripts/` line")
        names |= set(CODE_SPAN.findall(such_as.group(1)))
        self.assertTrue(names, "the Commands section names no command")
        for name in sorted(names):
            script = PAYLOAD / "scripts" / name
            with self.subTest(command=name):
                self.assertTrue(script.is_file(), f"scripts/{name} does not exist")
                self.assertTrue(
                    os.access(script, os.X_OK), f"scripts/{name} is not executable"
                )


if __name__ == "__main__":
    unittest.main()
