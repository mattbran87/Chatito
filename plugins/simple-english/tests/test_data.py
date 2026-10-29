import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common

BEGIN, END = "<!-- judge:begin -->", "<!-- judge:end -->"


class CasesTest(unittest.TestCase):
    def setUp(self):
        self.cases = common.load_cases()

    def test_twenty_cases_with_unique_ids(self):
        ids = [case["id"] for case in self.cases]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)

    def test_structure_cases_exist(self):
        ids = {case["id"] for case in self.cases}
        self.assertTrue({"compare-options", "ordered-steps", "causal-chain",
                         "risky-unverified", "plain-answer"} <= ids)

    def test_kind_counts_match_the_spec(self):
        self.assertEqual(Counter(case["kind"] for case in self.cases),
                         {"chat": 12, "commit": 4, "doc": 4})

    def test_every_case_is_complete(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["prompt"].strip())
                self.assertIsInstance(case["criteria"], list)
                self.assertTrue(case["criteria"])
                for item in case["criteria"]:
                    self.assertIsInstance(item, str)
                    self.assertTrue(item.strip())
                self.assertIn(case["risk"], ("low", "medium", "high"))

    def test_only_the_toast_skips_the_linter(self):
        skipped = [case["id"] for case in self.cases if case.get("lint", True) is False]
        self.assertEqual(skipped, ["toast"])

    def test_the_calibration_case_exists(self):
        self.assertIn("diagnose-partial", [case["id"] for case in self.cases])

    def test_cases_do_not_name_a_condition_or_the_ruleset(self):
        names = list(common.load_conditions()["conditions"])
        for case in self.cases:
            for text in [case["prompt"]] + case["criteria"]:
                with self.subTest(case=case["id"], text=text[:30]):
                    for name in names:
                        self.assertIsNone(re.search(r"\b%s\b" % name, text, re.I), name)
                    self.assertIsNone(re.search(r"\bSTE\b", text))
                    for phrase in ("Simplified Technical English", "simple-english"):
                        self.assertNotIn(phrase, text)

    def test_key_prompt_details(self):
        by_id = {case["id"]: case for case in self.cases}
        self.assertNotIn("British", by_id["doc-british"]["prompt"])
        self.assertIn("Resolves:", by_id["commit-format"]["prompt"])


class ConditionsTest(unittest.TestCase):
    def test_three_conditions_and_their_files_exist(self):
        cfg = common.load_conditions()
        self.assertEqual(list(cfg["conditions"]), ["baseline", "skill", "style"])
        self.assertTrue(cfg["model"])
        self.assertIn(cfg["effort"], ("low", "medium", "high", "xhigh", "max"))
        for name, source in cfg["conditions"].items():
            if source is not None:
                self.assertTrue((common.PLUGIN_DIR / source).is_file(), source)


class RubricTest(unittest.TestCase):
    def test_judge_block_names_no_condition(self):
        rubric = (common.EVALS_DIR / "rubric.md").read_text(encoding="utf-8")
        self.assertIn(BEGIN, rubric)
        self.assertIn(END, rubric)
        block = rubric.split(BEGIN, 1)[1].split(END, 1)[0]
        for name in common.load_conditions()["conditions"]:
            self.assertIsNone(re.search(r"\b%s\b" % name, block, re.I), name)

    def test_structure_questions_do_not_gate_and_reach_their_cases(self):
        questions = json.loads((common.EVALS_DIR / "jev_questions.json").read_text(encoding="utf-8"))
        for key in ("table_missed", "chain_bulleted", "label_misgraded", "label_overuse"):
            self.assertFalse(questions[key]["gating"], key)
        self.assertIn("compare-options", questions["table_missed"]["cases"])
        self.assertIn("causal-chain", questions["chain_bulleted"]["cases"])
        self.assertIn("risky-unverified", questions["label_misgraded"]["cases"])
        self.assertIn("plain-answer", questions["label_overuse"]["cases"])
        for key in ("answers_first", "filler", "idiom"):
            self.assertIn("plain-answer", questions[key]["cases"], key)


class RubricContentTest(unittest.TestCase):
    def test_judge_block_has_dimensions_and_the_safety_rule(self):
        rubric = (common.EVALS_DIR / "rubric.md").read_text(encoding="utf-8")
        block = rubric.split(BEGIN, 1)[1].split(END, 1)[0]
        for dim in ("correctness", "fact_retention", "readability", "concision", "safety", "structure"):
            self.assertIn(dim, block)
        self.assertIn("When the task carries no risk, score safety 5", block)


class JevQuestionsTest(unittest.TestCase):
    def test_questions_are_well_formed_and_point_at_real_cases(self):
        questions = json.loads((common.EVALS_DIR / "jev_questions.json").read_text(encoding="utf-8"))
        ids = {case["id"] for case in common.load_cases()}
        self.assertEqual(set(questions),
                         {"answers_first", "invents_cause", "filler", "idiom", "drops_warning",
                          "table_missed", "chain_bulleted", "label_misgraded", "label_overuse"})
        for key, spec in questions.items():
            with self.subTest(question=key):
                self.assertTrue(spec["question"].strip())
                self.assertIn(spec["bad_when"], ("yes", "no"))
                self.assertIsInstance(spec["gating"], bool)
                self.assertTrue(0 < spec["threshold"] < 1)
                self.assertTrue(set(spec.get("kinds", [])) <= {"chat", "commit", "doc"})
                self.assertTrue(set(spec.get("cases", [])) <= ids)
                self.assertTrue(spec.get("kinds") or spec.get("cases"))
                self.assertIn("`response`", spec["question"])

    def test_applicability(self):
        questions = json.loads((common.EVALS_DIR / "jev_questions.json").read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in common.load_cases()}

        def applies(key, cid):
            spec = questions[key]
            return cid in spec.get("cases", []) or cases[cid]["kind"] in spec.get("kinds", [])

        for key in ("filler", "idiom"):
            for cid in ("toast", "casual-thanks"):
                self.assertFalse(applies(key, cid), (key, cid))
        self.assertFalse(applies("answers_first", "toast"))


if __name__ == "__main__":
    unittest.main()
