import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
LINTER = PLUGIN / "skills" / "simple-english" / "scripts" / "ste_lint.py"
DOCS_LINTER = PLUGIN / "skills" / "simple-english-docs" / "scripts" / "ste_lint.py"

_spec = importlib.util.spec_from_file_location("ste_lint", LINTER)
ste_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ste_lint)


def rules(text):
    """(rule, tier, line) for each structure finding in text."""
    return [(f[2], f[1], f[0]) for f in ste_lint.check_structure(ste_lint.structure_lines(text))]


class LabelTest(unittest.TestCase):
    def test_rogue_label_is_an_error(self):
        self.assertIn(("label", "error", 1), rules("**NOTE:** the job retries.\n"))

    def test_rogue_label_in_a_list_item_is_an_error(self):
        self.assertIn(("label", "error", 1), rules("- **IMPORTANT:** back up first.\n"))

    def test_listed_label_passes(self):
        self.assertEqual(rules("**WARNING:** this deletes the branch.\n"), [])

    def test_bold_acronym_lead_in_passes(self):
        self.assertEqual(rules("**API:** the endpoint changed.\n"), [])

    def test_label_in_inline_code_is_ignored(self):
        self.assertEqual(rules("`**NOTE:**` is not on the list.\n"), [])

    def test_label_in_a_fence_is_ignored(self):
        self.assertEqual(rules("```\n**NOTE:** x\n```\n"), [])

    def test_same_label_twice_in_a_section_is_a_review_hit(self):
        self.assertIn(("label-repeat", "warn", 3), rules("**WARNING:** a.\n\n**WARNING:** b.\n"))

    def test_a_heading_starts_a_new_section(self):
        self.assertEqual(rules("**WARNING:** a.\n\n# Next\n\n**WARNING:** b.\n"), [])


class EmphasisTest(unittest.TestCase):
    def test_two_emphasis_spans_in_a_paragraph(self):
        self.assertIn(("emphasis", "warn", 1),
                      rules("The job **silently** drops rows\nand **only** logs once.\n"))

    def test_lead_in_does_not_count(self):
        self.assertEqual(rules("**Retries.** The job **silently** drops rows.\n"), [])

    def test_label_does_not_count(self):
        self.assertEqual(rules("**WARNING:** the job **silently** drops rows.\n"), [])

    def test_each_paragraph_counts_on_its_own(self):
        self.assertEqual(rules("The job **silently** drops rows.\n\nIt logs **once**.\n"), [])

    def test_each_list_item_counts_on_its_own(self):
        self.assertEqual(rules("- **only** once\n- **never** twice\n- **at most** 3\n"), [])


class NestingTest(unittest.TestCase):
    def test_second_level_is_a_review_hit(self):
        self.assertIn(("nesting", "warn", 3), rules("- a\n  - b\n    - c\n"))

    def test_one_level_passes(self):
        self.assertEqual(rules("- a\n  - b\n- c\n- d\n"), [])

    def test_numbered_parent_counts(self):
        self.assertIn(("nesting", "warn", 3), rules("1. a\n   - b\n     - c\n"))

    def test_a_paragraph_resets_the_list(self):
        self.assertEqual(rules("- a\n  - b\n\nText.\n\n  - c\n"), [])


class TwoItemTest(unittest.TestCase):
    def test_two_bullets_is_a_review_hit(self):
        self.assertIn(("two-item", "warn", 1), rules("- a\n- b\n"))

    def test_three_bullets_pass(self):
        self.assertEqual(rules("- a\n- b\n- c\n"), [])

    def test_two_numbered_steps_pass(self):
        self.assertEqual(rules("1. a\n2. b\n"), [])

    def test_blank_lines_between_items_keep_one_list(self):
        self.assertEqual(rules("- a\n\n- b\n\n- c\n"), [])


class CellTest(unittest.TestCase):
    TABLE = "| Form | Use |\n| --- | --- |\n"

    def test_two_sentences_in_a_cell(self):
        self.assertIn(("cell", "warn", 3), rules(self.TABLE + "| Table | Use it. Then stop. |\n"))

    def test_one_sentence_passes(self):
        self.assertEqual(rules(self.TABLE + "| Table | Use it for 2 attributes. |\n"), [])

    def test_a_numbered_cell_label_passes(self):
        self.assertEqual(rules(self.TABLE + "| 1. New cases | Use it. |\n"), [])


class ReviewFixTest(unittest.TestCase):
    def test_rogue_label_in_a_block_quote(self):
        self.assertIn(("label", "error", 1), rules("> **NOTE:** a.\n"))
        self.assertIn(("label", "error", 1), rules("> > **NOTE:** a.\n"))

    def test_block_quote_lead_in_does_not_count(self):
        self.assertEqual(rules("> **Amendment.** The job **silently** drops.\n"), [])

    def test_em_dash_lead_in_does_not_count(self):
        self.assertEqual(rules("**If it fails** — the job **silently** stops.\n"), [])
        self.assertEqual(rules("**If it fails** - the job **silently** stops.\n"), [])

    def test_title_case_rogue_label_is_an_error(self):
        self.assertIn(("label", "error", 1), rules("**Note:** x.\n"))

    def test_title_case_acronym_passes(self):
        self.assertEqual(rules("**Api:** x.\n"), [])

    def test_tilde_fence_is_ignored(self):
        self.assertEqual(rules("~~~\n- a\n- b\n~~~\n"), [])

    def test_tilde_fence_is_not_closed_by_backticks(self):
        self.assertEqual(rules("~~~\n```\n- a\n- b\n~~~\n"), [])


class ScopeTest(unittest.TestCase):
    def test_prose_and_structure_scopes_split_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "doc.md")
            Path(path).write_text("The build has been broken.\n\n- a\n- b\n", encoding="utf-8")
            prose = {f[2] for f in ste_lint.lint(path, "prose")}
            structure = {f[2] for f in ste_lint.lint(path, "structure")}
            everything = {f[2] for f in ste_lint.lint(path)}
        self.assertIn("perfect", prose)
        self.assertNotIn("two-item", prose)
        self.assertEqual(structure, {"two-item"})
        self.assertEqual(everything, prose | structure)


class CopiesTest(unittest.TestCase):
    def test_the_two_copies_are_identical(self):
        self.assertEqual(LINTER.read_bytes(), DOCS_LINTER.read_bytes())


class SelftestTest(unittest.TestCase):
    def test_selftest_passes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ste_lint.selftest()
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("32 passed, 0 failed", out.getvalue())


if __name__ == "__main__":
    unittest.main()
