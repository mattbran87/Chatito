"""The idiom rule and its check step read the same in all 3 copies of the rules."""

import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
STYLE = PLUGIN / "output-styles" / "simple-english.md"
SKILLS = (
    PLUGIN / "skills" / "simple-english" / "SKILL.md",
    PLUGIN / "skills" / "simple-english-docs" / "SKILL.md",
)
COPIES = (STYLE,) + SKILLS

# The lead-in and the 5 pairs, which must sit together in this order.
RULE_HEAD = "\n".join((
    '- **Use the literal word, not a picture.** If a word makes the reader picture something that is not there, '
    'write what the thing does or what state it is in:',
    '  - "the old key is dead" → "the old key no longer works"',
    '  - "leaves the old price live" → "the old price still shows"',
    '  - "ran clean for hours" → "ran for 3 hours with no errors"',
    '  - "Browsers check back on each visit" → "The browser sends a new request on each visit"',
    '  - "out of the box" → "by default"',
))
EXCEPTION = ('  A term that is the field\'s name for a thing stays, even when it began as a picture: '
             '"race condition," "bottleneck," "cache lifetime." An ordinary word that you put on a technical noun '
             'as a description does not stay, even when the field uses it in another term.')
REASON = "A figurative word makes a reader who learned English as a second language guess."
CHECK = ("Read each verb and adjective that describes a technical noun as a reader who translates word by word. "
         "If the literal meaning is wrong for that noun, replace the word.")
OLD = ("Use the literal phrase, not an idiom", "No idioms.", "Check for idioms")


class RuleCopiesTest(unittest.TestCase):
    def test_every_copy_carries_the_rule(self):
        for path in COPIES:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(PLUGIN))):
                self.assertIn(RULE_HEAD, text)
                self.assertIn(EXCEPTION, text)

    def test_every_copy_carries_the_check_step(self):
        for path in COPIES:
            with self.subTest(file=str(path.relative_to(PLUGIN))):
                self.assertIn(CHECK, path.read_text(encoding="utf-8"))

    def test_both_skills_carry_the_reason(self):
        for path in SKILLS:
            with self.subTest(file=str(path.relative_to(PLUGIN))):
                self.assertIn(EXCEPTION + " " + REASON, path.read_text(encoding="utf-8"))

    def test_no_copy_keeps_the_old_wording(self):
        for path in COPIES:
            text = path.read_text(encoding="utf-8")
            for old in OLD:
                with self.subTest(file=str(path.relative_to(PLUGIN)), old=old):
                    self.assertNotIn(old, text)


if __name__ == "__main__":
    unittest.main()
