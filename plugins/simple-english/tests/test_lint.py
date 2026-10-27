import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common
import lint


class RunLinterTest(unittest.TestCase):
    def test_counts_errors_and_reviews_by_rule(self):
        result = lint.run_linter("The build has been broken by several tests.\n")
        self.assertGreaterEqual(result["errors"], 1)
        self.assertGreaterEqual(result["reviews"], 1)
        self.assertIn("perfect", result["by_rule"])
        self.assertIn("passive", result["by_rule"])
        self.assertIn("vague", result["by_rule"])

    def test_clean_text_has_no_errors(self):
        self.assertEqual(lint.run_linter("Run the tests.\n")["errors"], 0)

    def test_empty_text_has_no_findings(self):
        result = lint.run_linter("")
        self.assertEqual((result["errors"], result["reviews"]), (0, 0))

    def test_non_ascii_text_does_not_raise(self):
        result = lint.run_linter("Run it — now.\nテストを実行する。\n")
        self.assertIn("errors", result)

    def test_table_cell_is_linted(self):
        text = "| Step | Note |\n| --- | --- |\n| 1 | The build has been broken by several tests |\n"
        self.assertGreaterEqual(lint.run_linter(text)["errors"], 1)

    def test_crashing_linter_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "boom.py"
            script.write_text("raise ValueError('boom')\n", encoding="utf-8")
            with mock.patch.object(lint, "LINTER", script):
                with self.assertRaises(RuntimeError):
                    lint.run_linter("Run the tests.\n")

    def test_linter_with_empty_stdout_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "quiet.py"
            script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
            with mock.patch.object(lint, "LINTER", script):
                with self.assertRaises(RuntimeError):
                    lint.run_linter("Run the tests.\n")

    def test_linter_output_without_the_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "other.py"
            script.write_text("print('{\"elsewhere\": []}')\n", encoding="utf-8")
            with mock.patch.object(lint, "LINTER", script):
                with self.assertRaises(RuntimeError):
                    lint.run_linter("Run the tests.\n")


class PrepareTest(unittest.TestCase):
    def test_table_row_becomes_its_cells(self):
        self.assertEqual(lint.prepare("| a | b |\n"), "a\n\nb\n\n")

    def test_separator_row_is_dropped(self):
        self.assertEqual(lint.prepare("| a |\n|:---|---:|\n| b |\n"), "a\n\nb\n\n")

    def test_table_cells_do_not_merge_into_one_paragraph(self):
        rows = "".join("| Run the tests. Fix the bug. | Read the log. Ask a peer. |\n" for _ in range(4))
        result = lint.run_linter("| Step | Note |\n| --- | --- |\n" + rows)
        self.assertNotIn("paragraph", result["by_rule"])

    def test_tilde_fence_is_masked_as_code(self):
        self.assertEqual(lint.run_linter("~~~\nThe build has been broken.\n~~~\n")["errors"], 0)

    def test_tilde_fence_becomes_a_backtick_fence_and_keeps_its_info_string(self):
        self.assertEqual(lint.prepare("~~~python\n| c |\n~~~\n"), "```python\n| c |\n```\n")

    def test_indented_bullet_loses_its_indent(self):
        self.assertEqual(lint.prepare("- top\n    - nested\n      1. one\n"), "- top\n- nested\n1. one\n")

    def test_fenced_code_is_untouched(self):
        text = "```\n| a | b |\n    - x\n```\n"
        self.assertEqual(lint.prepare(text), text)

    def test_crlf_becomes_lf(self):
        self.assertEqual(lint.prepare("a\r\nb\rc\n"), "a\nb\nc\n")


CFG = {"model": "m", "conditions": {"baseline": None, "skill": "skills/simple-english/SKILL.md"}}


def stamp(rows, cases, cfg=CFG):
    """Give each row the input_hash generate.py would store under cfg."""
    by_case = {case["id"]: case for case in cases}
    return [dict(row, input_hash=common.response_hash(by_case[row["case_id"]], cfg, row["condition"])) for row in rows]


class LintRunTest(unittest.TestCase):
    def test_skips_unlintable_cases_failed_rows_and_finished_rows(self):
        cases = [{"id": "a", "kind": "chat", "prompt": "P"}, {"id": "toast", "kind": "chat", "prompt": "T", "lint": False}]
        responses = stamp([
            {"case_id": "a", "trial": 1, "condition": "skill", "ok": True, "text": "x"},
            {"case_id": "a", "trial": 1, "condition": "baseline", "ok": False, "error": "boom"},
            {"case_id": "toast", "trial": 1, "condition": "skill", "ok": True, "text": "y"},
        ], cases)
        seen = []

        def fake(text):
            seen.append(text)
            return {"errors": 2, "reviews": 1, "by_rule": {"passive": 2, "vague": 1}}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lint.jsonl"
            self.assertEqual(lint.lint_run(cases, responses, out, linter=fake, cfg=CFG), 1)
            self.assertEqual(lint.lint_run(cases, responses, out, linter=fake, cfg=CFG), 0)
            rows = common.read_jsonl(out)
        self.assertEqual(seen, ["x"])
        self.assertEqual(rows, [{"case_id": "a", "trial": 1, "condition": "skill", "ok": True,
                                 "text_hash": lint.text_hash("x"),
                                 "errors": 2, "reviews": 1, "by_rule": {"passive": 2, "vague": 1}}])

    def test_relints_a_response_whose_text_changed(self):
        cases = [{"id": "a", "kind": "chat", "prompt": "P"}]
        seen = []

        def fake(text):
            seen.append(text)
            return {"errors": 0, "reviews": 0, "by_rule": {}}

        def response(text):
            return stamp([{"case_id": "a", "trial": 1, "condition": "skill", "ok": True, "text": text}], cases)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lint.jsonl"
            self.assertEqual(lint.lint_run(cases, response("old"), out, linter=fake, cfg=CFG), 1)
            self.assertEqual(lint.lint_run(cases, response("new"), out, linter=fake, cfg=CFG), 1)
            self.assertEqual(lint.lint_run(cases, response("new"), out, linter=fake, cfg=CFG), 0)
        self.assertEqual(seen, ["old", "new"])

    def test_the_row_hash_covers_ste_lint_and_lint_py_itself(self):
        self.assertEqual(lint.text_hash("x"),
                         common.input_hash("x", lint.LINTER_SOURCE + "\x00" + lint.SELF_SOURCE))
        self.assertIn("def prepare(", lint.SELF_SOURCE)
        cases = [{"id": "a", "kind": "chat", "prompt": "P"}]
        rows = stamp([{"case_id": "a", "trial": 1, "condition": "skill", "ok": True, "text": "x"}], cases)
        seen = []

        def fake(text):
            seen.append(text)
            return {"errors": 0, "reviews": 0, "by_rule": {}}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lint.jsonl"
            lint.lint_run(cases, rows, out, linter=fake, cfg=CFG)
            with mock.patch.object(lint, "SELF_SOURCE", lint.SELF_SOURCE + "# a changed prepare\n"):
                self.assertEqual(lint.lint_run(cases, rows, out, linter=fake, cfg=CFG), 1)
        self.assertEqual(seen, ["x", "x"])

    def test_an_out_of_date_response_is_not_linted(self):
        cases = [{"id": "a", "kind": "chat", "prompt": "P"}]
        rows = stamp([{"case_id": "a", "trial": 1, "condition": "skill", "ok": True, "text": "x"}], cases)
        seen = []

        def fake(text):
            seen.append(text)
            return {"errors": 0, "reviews": 0, "by_rule": {}}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "lint.jsonl"
            self.assertEqual(lint.lint_run(cases, rows, out, linter=fake, cfg=dict(CFG, model="m2")), 0)
            self.assertFalse(out.exists())
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
