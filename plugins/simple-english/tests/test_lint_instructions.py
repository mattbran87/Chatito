"""The lint instructions in the 2 skill files, and the hook text they name, stay in step."""

import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SKILL_FILES = (
    PLUGIN / "skills" / "simple-english-docs" / "SKILL.md",
    PLUGIN / "skills" / "simple-english" / "references" / "documents.md",
)
HOOK = PLUGIN / "hooks" / "register.ts"

RULES = (
    "write it to a file before you show it",
    "If a `simple-english lint` message follows your write",
    "Lint: ste_lint.py ran on <file> — <n> errors fixed, <m> review hits kept.",
    "Lint: did not run — <reason>.",
    "The reply's `Lint:` line shows the user whether the check ran.",
)


class LintInstructionsTest(unittest.TestCase):
    def test_both_skill_files_carry_every_rule(self):
        for path in SKILL_FILES:
            text = path.read_text(encoding="utf-8")
            for rule in RULES:
                with self.subTest(file=path.name, rule=rule):
                    self.assertIn(rule, text)

    def test_the_hook_writes_the_text_the_skills_name(self):
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn("simple-english lint, pass ", source)
        self.assertIn("simple-english lint did not run: ", source)


if __name__ == "__main__":
    unittest.main()
