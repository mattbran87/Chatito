import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import calibrate
import common
import jev

QUESTIONS = {"filler": {"question": "F?", "kinds": ["chat", "doc"], "bad_when": "yes", "gating": False, "threshold": 0.5},
             "invents_cause": {"question": "I?", "cases": ["diagnose-partial"], "bad_when": "yes", "gating": False, "threshold": 0.5}}
CASES = [{"id": "c%d" % i, "kind": "chat", "prompt": "prompt %d" % i} for i in range(10)]
CASES.append({"id": "diagnose-partial", "kind": "chat", "prompt": "partial"})
CASES.append({"id": "diagnose-clear", "kind": "chat", "prompt": "clear"})
CASES.append({"id": "commit-x", "kind": "commit", "prompt": "commit"})
CONDITIONS = ("baseline", "skill", "style")
CFG = common.load_conditions()
RESPONSES = [{"case_id": c["id"], "trial": 1, "condition": n, "ok": True, "text": "%s by %s" % (c["id"], n),
              "input_hash": common.response_hash(c, CFG, n)}
             for c in CASES for n in CONDITIONS]


def labels_and_key(pairs, question="filler", questions=QUESTIONS):
    """pairs: list of (human 'yes'/'no', jev noul)."""
    labels, key, jev_rows = [], [], []
    for index, (human, noul) in enumerate(pairs, 1):
        labels.append({"item": index, "labels": {question: human}})
        case = CASES[index]
        text = "%s by skill" % case["id"]
        key.append({"item": index, "case_id": case["id"], "trial": 1, "condition": "skill",
                    "text_hash": common.input_hash(text, "")})
        jev_rows.append({"case_id": case["id"], "trial": 1, "condition": "skill", "ok": True, "answers": {question: noul},
                         "text_hash": jev.row_hash(case, text, jev.request_questions(questions, case))})
    return labels, key, jev_rows


class SampleTest(unittest.TestCase):
    def test_twenty_blind_items_that_include_the_partial_case_for_each_condition(self):
        items, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=20)
        self.assertEqual(len(items), 20)
        self.assertEqual([item["item"] for item in items], list(range(1, 21)))
        partial = [k["condition"] for k in key if k["case_id"] == "diagnose-partial"]
        self.assertEqual(sorted(partial), sorted(CONDITIONS))
        self.assertTrue(all(set(item) == {"item", "labels"} for item in items))
        self.assertNotIn("commit-x", [k["case_id"] for k in key])
        partial_item = next(i for i, k in zip(items, key) if k["case_id"] == "diagnose-partial")
        self.assertEqual(partial_item["labels"], {"filler": None, "invents_cause": None})

    def test_sample_is_the_same_every_time(self):
        self.assertEqual(calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG),
                         calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG))

    def test_item_order_does_not_follow_condition(self):
        items, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=20)
        periodic = [CONDITIONS[(k["item"] - 1) % 3] for k in key]
        self.assertNotEqual([k["condition"] for k in key], periodic)
        self.assertEqual([k["item"] for k in key], list(range(1, 21)))
        for case_id in ("diagnose-clear", "diagnose-partial"):
            numbers = sorted(k["item"] for k in key if k["case_id"] == case_id)
            self.assertEqual(len(numbers), 3)
            self.assertNotEqual(numbers[2] - numbers[0], 2)
            ordered = [k["condition"] for k in sorted(key, key=lambda k: k["item"]) if k["case_id"] == case_id]
            self.assertNotEqual(ordered, sorted(CONDITIONS))

    def test_sample_holds_both_must_cases_for_every_condition(self):
        _, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=20)
        for case_id in ("diagnose-clear", "diagnose-partial"):
            self.assertEqual(sorted(k["condition"] for k in key if k["case_id"] == case_id), sorted(CONDITIONS))

    def test_the_key_holds_a_hash_of_each_sampled_text(self):
        _, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=5)
        texts = {common.row_key(row): row["text"] for row in RESPONSES}
        for entry in key:
            text = texts[(entry["case_id"], entry["trial"], entry["condition"])]
            self.assertEqual(entry["text_hash"], common.input_hash(text, ""))

    def test_an_out_of_date_response_is_never_sampled(self):
        responses = [dict(row, input_hash="old") if row["condition"] == "style" else row for row in RESPONSES]
        _, key = calibrate.sample(CASES, responses, QUESTIONS, cfg=CFG, n=40)
        self.assertTrue(key)
        self.assertNotIn("style", {k["condition"] for k in key})

    def test_missing_must_responses_are_reported(self):
        responses = [dict(row, ok=False) if (row["case_id"], row["condition"]) == ("diagnose-clear", "skill") else row
                     for row in RESPONSES]
        self.assertEqual(calibrate.missing_must(responses), [("diagnose-clear", "skill")])
        self.assertEqual(calibrate.missing_must(RESPONSES), [])

    def test_only_the_latest_response_counts_for_a_must_case(self):
        row = next(r for r in RESPONSES if (r["case_id"], r["condition"]) == ("diagnose-clear", "skill"))
        responses = RESPONSES + [dict(row, ok=False)]
        self.assertEqual(calibrate.missing_must(responses), [("diagnose-clear", "skill")])
        self.assertEqual(calibrate.missing_must([dict(row, ok=False)] + RESPONSES), [])

    def test_sheet_tells_the_labeller_not_to_open_the_key(self):
        items, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=3)
        sheet = calibrate.render_sheet(items, key, CASES, RESPONSES, QUESTIONS)
        self.assertIn("Do not open sample-key.jsonl until you finish labelling.", sheet)
        self.assertIn('"yes"', sheet)
        self.assertIn('"no"', sheet)

    def test_sheet_shows_text_but_no_condition(self):
        items, key = calibrate.sample(CASES, RESPONSES, QUESTIONS, cfg=CFG, n=3)
        responses = [dict(row, text="response text %d" % index) for index, row in enumerate(RESPONSES)]
        sheet = calibrate.render_sheet(items, key, CASES, responses, QUESTIONS)
        self.assertIn("## Item 1", sheet)
        self.assertIn("F?", sheet)
        for name in CONDITIONS:
            self.assertNotIn(name, sheet)


class ScoreTest(unittest.TestCase):
    def test_separated_labels_pass_at_the_threshold_with_best_agreement(self):
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.65), ("no", 0.2), ("no", 0.1), ("no", 0.35)]
        result = calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]
        self.assertEqual((result["yes"], result["no"]), (3, 3))
        self.assertEqual(result["agreement"][0.5], 1.0)
        self.assertEqual(result["threshold"], 0.5)
        self.assertTrue(result["gating"])

    def test_fewer_than_three_yes_cannot_calibrate(self):
        pairs = [("yes", 0.9), ("yes", 0.8), ("no", 0.2), ("no", 0.1), ("no", 0.3), ("no", 0.2)]
        result = calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]
        self.assertFalse(result["gating"])
        self.assertIsNone(result["threshold"])

    def test_agreement_under_eighty_percent_fails(self):
        pairs = [("yes", 0.9), ("yes", 0.2), ("yes", 0.8), ("no", 0.9), ("no", 0.1), ("no", 0.2), ("yes", 0.1), ("no", 0.8)]
        self.assertFalse(calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]["gating"])

    def test_blank_labels_and_failed_jev_rows_are_left_out(self):
        labels, key, jev_rows = labels_and_key([("yes", 0.9), ("no", 0.1)])
        labels[0]["labels"]["filler"] = None
        jev_rows[1]["ok"] = False
        result = calibrate.score(labels, key, jev_rows, QUESTIONS, CASES, RESPONSES)["filler"]
        self.assertEqual((result["yes"], result["no"]), (0, 0))

    def test_judged_needs_three_yes_and_three_no(self):
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.7), ("no", 0.2), ("no", 0.1), ("no", 0.3)]
        self.assertTrue(calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]["judged"])
        pairs = [("yes", 0.9), ("yes", 0.8), ("no", 0.2), ("no", 0.1), ("no", 0.3), ("no", 0.2)]
        self.assertFalse(calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]["judged"])

    def test_unjudged_question_keeps_gating_and_threshold(self):
        questions = json.loads(json.dumps(QUESTIONS))
        questions["filler"].update(gating=True, threshold=0.6)
        labels, key, jev_rows = labels_and_key([("yes", 0.9), ("no", 0.1)])
        for row in labels:
            row["labels"]["filler"] = None
        results = calibrate.score(labels, key, jev_rows, questions, CASES, RESPONSES)
        calibrate.apply(questions, results)
        self.assertEqual((questions["filler"]["gating"], questions["filler"]["threshold"]), (True, 0.6))

    def test_judged_and_failed_question_loses_gating_but_keeps_threshold(self):
        questions = json.loads(json.dumps(QUESTIONS))
        questions["filler"].update(gating=True, threshold=0.6)
        calibrate.apply(questions, {"filler": {"judged": True, "gating": False, "threshold": None}})
        self.assertEqual((questions["filler"]["gating"], questions["filler"]["threshold"]), (False, 0.6))

    def test_true_ties_go_to_the_lower_threshold(self):
        low = [("yes", 0.65)] * 3 + [("yes", 0.45)] + [("no", 0.35)] * 3 + [("no", 0.55)]
        self.assertEqual(calibrate.score(*labels_and_key(low), QUESTIONS, CASES, RESPONSES)["filler"]["threshold"], 0.4)
        wide = [("yes", 0.8)] * 3 + [("yes", 0.35)] + [("no", 0.2)] * 3 + [("no", 0.65)]
        self.assertEqual(calibrate.score(*labels_and_key(wide), QUESTIONS, CASES, RESPONSES)["filler"]["threshold"], 0.3)

    def test_a_question_that_is_bad_when_no_is_scored_the_same_way(self):
        questions = {"answers_first": {"question": "A?", "kinds": ["chat"], "bad_when": "no", "gating": False, "threshold": 0.5}}
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.65), ("no", 0.2), ("no", 0.1), ("no", 0.35)]
        labels, key, jev_rows = labels_and_key(pairs, question="answers_first", questions=questions)
        result = calibrate.score(labels, key, jev_rows, questions, CASES, RESPONSES)["answers_first"]
        self.assertEqual((result["agreement"][0.5], result["threshold"], result["gating"]), (1.0, 0.5, True))

    def test_a_jev_row_with_a_stale_text_hash_is_left_out(self):
        labels, key, jev_rows = labels_and_key([("yes", 0.9), ("no", 0.1)])
        jev_rows[0]["text_hash"] = "stale"
        result = calibrate.score(labels, key, jev_rows, QUESTIONS, CASES, RESPONSES)["filler"]
        self.assertEqual((result["yes"], result["no"]), (0, 1))

    def test_tie_goes_to_the_threshold_nearest_half(self):
        pairs = [("yes", 0.95), ("yes", 0.9), ("yes", 0.85), ("no", 0.05), ("no", 0.1), ("no", 0.15)]
        self.assertEqual(calibrate.score(*labels_and_key(pairs), QUESTIONS, CASES, RESPONSES)["filler"]["threshold"], 0.5)

    def test_change_lines_name_only_what_changed(self):
        result = {"judged": True, "gating": True, "threshold": 0.6, "agreement": {t: 1.0 for t in calibrate.THRESHOLDS}}
        lines = calibrate._change_lines
        self.assertEqual(lines("q", {"gating": False, "threshold": 0.6}, {"gating": True, "threshold": 0.6}, result)[0],
                         "q: gating false -> true")
        self.assertEqual(lines("q", {"gating": True, "threshold": 0.5}, {"gating": True, "threshold": 0.6}, result)[0],
                         "q: threshold 0.5 -> 0.6")
        self.assertEqual(lines("q", {"gating": False, "threshold": 0.5}, {"gating": True, "threshold": 0.6}, result)[0],
                         "q: gating false -> true, threshold 0.5 -> 0.6")
        self.assertEqual(lines("q", {"gating": True, "threshold": 0.6}, {"gating": True, "threshold": 0.6}, result)[0],
                         "q: no change")

    def test_apply_writes_gating_and_threshold(self):
        questions = json.loads(json.dumps(QUESTIONS))
        calibrate.apply(questions, {"filler": {"judged": True, "gating": True, "threshold": 0.6},
                                    "invents_cause": {"judged": True, "gating": False, "threshold": None}})
        self.assertEqual((questions["filler"]["gating"], questions["filler"]["threshold"]), (True, 0.6))
        self.assertEqual((questions["invents_cause"]["gating"], questions["invents_cause"]["threshold"]), (False, 0.5))


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.labels, self.key, _ = labels_and_key([("yes", 0.9), ("no", 0.1)])

    def check(self):
        return calibrate.validate_labels(self.labels, self.key, QUESTIONS, CASES)

    def test_accepted_spellings_are_normalised(self):
        self.labels[0]["labels"]["filler"] = "Yes "
        self.labels[1]["labels"]["filler"] = "N"
        self.assertEqual([r["labels"]["filler"] for r in self.check()], ["yes", "no"])
        self.labels[0]["labels"]["filler"] = "Y"
        self.labels[1]["labels"]["filler"] = False
        self.assertEqual([r["labels"]["filler"] for r in self.check()], ["yes", "no"])
        self.labels[0]["labels"]["filler"] = ""
        self.labels[1]["labels"]["filler"] = None
        self.assertEqual([r["labels"]["filler"] for r in self.check()], [None, None])

    def test_duplicated_item_is_an_error(self):
        self.labels.append(dict(self.labels[0]))
        with self.assertRaisesRegex(ValueError, "item 1"):
            self.check()

    def test_unknown_item_is_an_error(self):
        self.labels[1]["item"] = 99
        with self.assertRaisesRegex(ValueError, "item 99"):
            self.check()

    def test_row_without_labels_is_an_error(self):
        del self.labels[0]["labels"]
        with self.assertRaisesRegex(ValueError, "item 1"):
            self.check()

    def test_misspelled_question_is_an_error(self):
        self.labels[1]["labels"] = {"fillr": "no"}
        with self.assertRaisesRegex(ValueError, "item 2.*fillr"):
            self.check()

    def test_other_values_are_an_error(self):
        self.labels[0]["labels"]["filler"] = "maybe"
        with self.assertRaisesRegex(ValueError, "item 1.*filler.*maybe"):
            self.check()

    def test_count_of_labelled_items(self):
        self.labels[1]["labels"]["filler"] = None
        self.assertEqual(calibrate.count_labelled(self.check()), 1)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.evals, self.runs = root / "evals", root / "runs"
        self.evals.mkdir()
        for case in CASES:
            common.append_jsonl(self.evals / "cases.jsonl", case)
        self.questions_path = self.evals / "jev_questions.json"
        self.questions_path.write_text(json.dumps(QUESTIONS, indent=2) + "\n", encoding="utf-8")
        self.folder = common.run_dir("r1", self.runs)

    def tearDown(self):
        self.tmp.cleanup()

    def run_score(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = calibrate.main(["score", "--run-id", "r1"], runs_root=self.runs, evals_dir=self.evals)
        return code, out.getvalue()

    def write(self, name, rows):
        for row in rows:
            common.append_jsonl(self.folder / name, row)

    def test_empty_labels_exit_one_and_change_nothing(self):
        labels, key, jev_rows = labels_and_key([("yes", 0.9), ("no", 0.1)])
        for row in labels:
            row["labels"]["filler"] = None
        self.write("labels.jsonl", labels)
        self.write("sample-key.jsonl", key)
        self.write("jev.jsonl", jev_rows)
        self.write("responses.jsonl", RESPONSES)
        before = self.questions_path.read_bytes()
        code, _ = self.run_score()
        self.assertEqual(code, 1)
        self.assertEqual(self.questions_path.read_bytes(), before)

    def test_missing_label_file_exits_one_and_changes_nothing(self):
        before = self.questions_path.read_bytes()
        code, _ = self.run_score()
        self.assertEqual(code, 1)
        self.assertEqual(self.questions_path.read_bytes(), before)

    def test_bad_label_value_exits_one(self):
        labels, key, jev_rows = labels_and_key([("maybe", 0.9)])
        self.write("labels.jsonl", labels)
        self.write("sample-key.jsonl", key)
        self.write("responses.jsonl", RESPONSES)
        code, output = self.run_score()
        self.assertEqual(code, 1)
        self.assertIn("maybe", output)

    def test_scoring_reports_each_question_and_writes_the_file(self):
        questions = dict(QUESTIONS, drops={"question": "D?", "kinds": ["chat", "doc"], "bad_when": "yes",
                                           "gating": False, "threshold": 0.5})
        self.questions_path.write_text(json.dumps(questions, indent=2) + "\n", encoding="utf-8")
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.65), ("no", 0.2), ("no", 0.1), ("no", 0.35)]
        labels, key, jev_rows = labels_and_key(pairs, questions=questions)
        for row, drops_noul in zip(zip(labels, jev_rows), [0.1, 0.2, 0.9, 0.9, 0.8, 0.1]):
            label_row, jev_row = row
            label_row["labels"]["drops"] = label_row["labels"]["filler"]
            jev_row["answers"]["drops"] = drops_noul
        self.write("labels.jsonl", labels)
        self.write("sample-key.jsonl", key)
        self.write("jev.jsonl", jev_rows)
        self.write("responses.jsonl", RESPONSES)
        code, output = self.run_score()
        self.assertEqual(code, 0)
        self.assertIn("labelled 6 of 6 items", output)
        self.assertNotIn("missing items", output)
        self.assertIn("filler: gating false -> true\n"
                      "  0.3: 83%, 0.4: 100%, 0.5: 100%, 0.6: 100%, 0.7: 83%", output)
        self.assertIn("drops: failed (best 33% at 0.3); gating stays false\n"
                      "  0.3: 33%, 0.4: 33%, 0.5: 33%, 0.6: 33%, 0.7: 33%", output)
        self.assertIn("invents_cause: not judged (0 yes, 0 no); left as is", output)
        written = json.loads(self.questions_path.read_text(encoding="utf-8"))
        self.assertTrue(written["filler"]["gating"])
        self.assertFalse(written["invents_cause"]["gating"])
        self.assertFalse(written["drops"]["gating"])

    def test_missing_items_are_named(self):
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.65), ("no", 0.2), ("no", 0.1), ("no", 0.35)]
        labels, key, jev_rows = labels_and_key(pairs)
        self.write("labels.jsonl", [row for row in labels if row["item"] not in (4, 5)])
        self.write("sample-key.jsonl", key)
        self.write("jev.jsonl", jev_rows)
        self.write("responses.jsonl", RESPONSES)
        code, output = self.run_score()
        self.assertEqual(code, 0)
        self.assertIn("labelled 4 of 6 items; missing items: 4, 5", output)

    def write_labelled_run(self):
        pairs = [("yes", 0.9), ("yes", 0.8), ("yes", 0.65), ("no", 0.2), ("no", 0.1), ("no", 0.35)]
        labels, key, jev_rows = labels_and_key(pairs)
        self.write("labels.jsonl", labels)
        self.write("sample-key.jsonl", key)
        self.write("jev.jsonl", jev_rows)
        self.write("responses.jsonl", RESPONSES)
        return key

    def test_a_labelled_response_regenerated_with_new_text_refuses_the_score(self):
        key = self.write_labelled_run()
        entry = key[2]
        row = next(r for r in RESPONSES if (r["case_id"], r["trial"], r["condition"])
                   == (entry["case_id"], entry["trial"], entry["condition"]))
        self.write("responses.jsonl", [dict(row, text="a regenerated text")])
        before = self.questions_path.read_bytes()
        code, output = self.run_score()
        self.assertEqual(code, 1)
        self.assertIn("item 3", output)
        self.assertIn("Nothing written", output)
        self.assertEqual(self.questions_path.read_bytes(), before)

    def test_a_labelled_response_that_failed_or_vanished_refuses_the_score(self):
        key = self.write_labelled_run()
        failed = {"case_id": key[0]["case_id"], "trial": 1, "condition": "skill", "ok": False, "error": "boom"}
        self.write("responses.jsonl", [failed])
        (self.folder / "sample-key.jsonl").unlink()
        self.write("sample-key.jsonl", key + [{"item": 7, "case_id": "c9", "trial": 9, "condition": "skill",
                                               "text_hash": "x"}])
        common.append_jsonl(self.folder / "labels.jsonl", {"item": 7, "labels": {"filler": "yes"}})
        before = self.questions_path.read_bytes()
        code, output = self.run_score()
        self.assertEqual(code, 1)
        self.assertIn("items 1, 7", output)
        self.assertEqual(self.questions_path.read_bytes(), before)

    def test_sample_with_no_current_responses_exits_one_and_writes_nothing(self):
        self.write("responses.jsonl", [dict(row, input_hash="old") for row in RESPONSES])
        self.write("labels.jsonl", [{"item": 1, "labels": {"filler": "yes"}}])
        before = (self.folder / "labels.jsonl").read_bytes()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = calibrate.main(["sample", "--run-id", "r1"], runs_root=self.runs, evals_dir=self.evals)
        self.assertEqual(code, 1)
        self.assertIn("no current responses; rerun generate.py", out.getvalue())
        self.assertEqual((self.folder / "labels.jsonl").read_bytes(), before)
        self.assertFalse((self.folder / "sample-key.jsonl").exists())
        self.assertFalse((self.folder / "sheet.md").exists())

    def test_score_without_a_run_folder_exits_one_and_creates_nothing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = calibrate.main(["score", "--run-id", "nope"], runs_root=self.runs, evals_dir=self.evals)
        self.assertEqual(code, 1)
        self.assertIn("no run folder nope", out.getvalue())
        self.assertFalse((self.runs / "nope").exists())


class FilesTest(unittest.TestCase):
    def test_sample_command_writes_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for row in RESPONSES:
                common.append_jsonl(folder / "responses.jsonl", row)
            calibrate.write_sample(folder, CASES, QUESTIONS, CFG, n=5)
            self.assertEqual(len(common.read_jsonl(folder / "labels.jsonl")), 5)
            self.assertEqual(len(common.read_jsonl(folder / "sample-key.jsonl")), 5)
            self.assertTrue((folder / "sheet.md").is_file())


if __name__ == "__main__":
    unittest.main()
