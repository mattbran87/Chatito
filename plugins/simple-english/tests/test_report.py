import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common
import jev
import judge
import lint as lint_stage
import report

QUESTIONS = {"filler": {"kinds": ["chat"], "bad_when": "yes", "gating": True, "threshold": 0.5},
             "answers_first": {"bad_when": "no", "gating": False, "threshold": 0.5}}


def score(condition, case="a", trial=1, value=4, blocker=False, correctness=None, safety=None, digest="h1"):
    scores = {d: value for d in report.WEIGHTS}
    if correctness is not None:
        scores["correctness"] = correctness
    if safety is not None:
        scores["safety"] = safety
    return {"case_id": case, "trial": trial, "condition": condition, "ok": True, "scores": scores,
            "blocker": blocker, "rubric_hash": digest, "model": "m"}


def response(condition, case="a", trial=1, model="m", text="t", trials=None, models=None):
    row = {"case_id": case, "trial": trial, "condition": condition, "ok": True, "text": text, "model": model}
    if models is not None:
        row["models"] = models
    if trials is not None:
        row["trials"] = trials
    return row


def lint(condition, errors, case="a", trial=1, text="t"):
    return {"case_id": case, "trial": trial, "condition": condition, "ok": True, "errors": errors, "reviews": 0,
            "by_rule": {}, "text_hash": lint_stage.text_hash(text)}


def jev_row(condition, filler, answers_first=0.9, case="a"):
    return {"case_id": case, "trial": 1, "condition": condition, "ok": True,
            "answers": {"filler": filler, "answers_first": answers_first}}


def passing_inputs():
    return {
        "responses": [response("ref"), response("cand")],
        "scores": [score("ref", value=3), score("cand", value=4)],
        "lint": [lint("ref", 2), lint("cand", 1)],
        "jev": [jev_row("ref", 0.9), jev_row("cand", 0.1)],
    }


def full_inputs(case_ids, ref_value=3, cand_value=4):
    out = {"responses": [], "scores": [], "lint": [], "jev": []}
    for case in case_ids:
        for name, value in (("ref", ref_value), ("cand", cand_value)):
            out["responses"].append(response(name, case=case))
            out["scores"].append(score(name, case=case, value=value))
            out["lint"].append(lint(name, 0, case=case))
    return out


def run_gate(inputs, cases=None):
    if cases is None:
        cases = [{"id": case, "kind": "chat"} for case in sorted({row["case_id"] for row in inputs["responses"]})]
    return report.gate(inputs["responses"], inputs["scores"], inputs["lint"], inputs["jev"], QUESTIONS, "ref", "cand",
                       cases)


def failed_checks(result):
    return [name for name, ok, _ in result["checks"] if not ok]


class SummaryTest(unittest.TestCase):
    def test_weighted_score(self):
        self.assertAlmostEqual(report.weighted({d: 4 for d in report.WEIGHTS}), 4.0)
        scores = {"correctness": 5, "fact_retention": 1, "readability": 1, "concision": 1, "safety": 1}
        self.assertAlmostEqual(report.weighted(scores), 2.2)

    def test_jev_bad_rate_follows_bad_when(self):
        rows = [jev_row("x", 0.9, answers_first=0.2), jev_row("x", 0.1, answers_first=0.9, case="b"),
                {"case_id": "c", "trial": 1, "condition": "x", "ok": False, "reason": "timeout"}]
        rates, failures = report.jev_summary(rows, QUESTIONS, "x")
        self.assertEqual(rates["filler"], {"answered": 2, "bad": 1, "rate": 0.5})
        self.assertEqual(rates["answers_first"], {"answered": 2, "bad": 1, "rate": 0.5})
        self.assertEqual(dict(failures), {"timeout": 1})


class LintSummaryTest(unittest.TestCase):
    def test_a_lint_row_for_changed_response_text_is_not_counted(self):
        responses = [response("x", text="new"), response("x", case="b", text="t")]
        rows = [lint("x", 5, text="old"), lint("x", 1, case="b")]
        summary = report.lint_summary(rows, "x", responses, {("a", 1), ("b", 1)})
        self.assertEqual((summary["errors"], summary["n"]), (1, 1))

    def test_a_lint_row_outside_the_groups_is_not_counted(self):
        responses = [response("x"), response("x", case="b")]
        rows = [lint("x", 5), lint("x", 1, case="b")]
        summary = report.lint_summary(rows, "x", responses, {("b", 1)})
        self.assertEqual((summary["errors"], summary["n"]), (1, 1))

    def test_a_lint_row_whose_latest_response_failed_is_not_counted(self):
        responses = [response("x"), {"case_id": "a", "trial": 1, "condition": "x", "ok": False, "error": "boom"}]
        summary = report.lint_summary([lint("x", 5)], "x", responses, {("a", 1)})
        self.assertEqual((summary["errors"], summary["n"]), (0, 0))


class FreshScoresTest(unittest.TestCase):
    def test_a_stale_score_row_is_dropped_and_counted(self):
        rows = [dict(score("ref"), group_hash="old"), dict(score("cand"), group_hash="old")]
        kept, dropped = report.fresh_scores(rows, {("a", 1): "new"})
        self.assertEqual((kept, dropped), ([], 2))

    def test_a_matching_score_row_is_kept(self):
        rows = [dict(score("ref"), group_hash="g"), dict(score("cand", case="b"), group_hash="old")]
        kept, dropped = report.fresh_scores(rows, {("a", 1): "g", ("b", 1): "new"})
        self.assertEqual([row["condition"] for row in kept], ["ref"])
        self.assertEqual(dropped, 1)

    def test_a_row_with_no_hash_for_an_incomplete_group_is_dropped(self):
        kept, dropped = report.fresh_scores([score("ref")], {})
        self.assertEqual((kept, dropped), ([], 1))

    def test_only_the_latest_row_per_key_is_considered(self):
        rows = [dict(score("ref", value=1), group_hash="g"), dict(score("ref", value=5), group_hash="g")]
        kept, dropped = report.fresh_scores(rows, {("a", 1): "g"})
        self.assertEqual(([row["scores"]["correctness"] for row in kept], dropped), ([5], 0))


JEV_QUESTIONS = {"filler": {"question": "Filler?", "kinds": ["chat"], "bad_when": "yes", "gating": False, "threshold": 0.5},
                 "invents_cause": {"question": "Invents?", "cases": ["a"], "bad_when": "yes", "gating": False,
                                   "threshold": 0.5}}
JEV_CASES = [{"id": "a", "kind": "chat", "prompt": "P"}, {"id": "b", "kind": "commit", "prompt": "Q"}]


def fresh_jev_row(condition, text, questions=JEV_QUESTIONS, case=JEV_CASES[0]):
    asked = jev.request_questions(questions, case)
    return {"case_id": case["id"], "trial": 1, "condition": condition, "ok": True,
            "answers": {key: 0.1 for key in asked}, "text_hash": jev.row_hash(case, text, asked)}


class FreshLintTest(unittest.TestCase):
    def test_a_lint_row_from_older_text_or_a_failed_response_is_dropped_and_counted(self):
        responses = [response("x", text="new"), response("x", case="b"),
                     {"case_id": "c", "trial": 1, "condition": "x", "ok": False, "error": "boom"}]
        rows = [lint("x", 5, text="old"), lint("x", 1, case="b"), lint("x", 2, case="c"), lint("x", 3, case="gone")]
        kept, dropped = report.fresh_lint(rows, responses)
        self.assertEqual([row["case_id"] for row in kept], ["b"])
        self.assertEqual(dropped, 3)


class FreshJevTest(unittest.TestCase):
    def test_a_matching_jev_row_is_kept(self):
        kept, dropped = report.fresh_jev([fresh_jev_row("x", "t")], JEV_CASES, [response("x")], JEV_QUESTIONS)
        self.assertEqual((len(kept), dropped), (1, 0))

    def test_a_jev_row_from_older_response_text_is_dropped(self):
        kept, dropped = report.fresh_jev([fresh_jev_row("x", "old")], JEV_CASES, [response("x", text="new")],
                                         JEV_QUESTIONS)
        self.assertEqual((kept, dropped), ([], 1))

    def test_a_jev_row_from_a_changed_question_is_dropped(self):
        changed = dict(JEV_QUESTIONS, filler=dict(JEV_QUESTIONS["filler"], question="Any filler?"))
        kept, dropped = report.fresh_jev([fresh_jev_row("x", "t")], JEV_CASES, [response("x")], changed)
        self.assertEqual((kept, dropped), ([], 1))

    def test_a_jev_row_whose_latest_response_failed_is_dropped(self):
        responses = [response("x"), {"case_id": "a", "trial": 1, "condition": "x", "ok": False, "error": "boom"}]
        kept, dropped = report.fresh_jev([fresh_jev_row("x", "t")], JEV_CASES, responses, JEV_QUESTIONS)
        self.assertEqual((kept, dropped), ([], 1))


class GateTest(unittest.TestCase):
    def test_a_better_candidate_passes(self):
        result = run_gate(passing_inputs())
        self.assertIsNone(result["refused"])
        self.assertTrue(result["passed"], result["checks"])

    def test_more_blockers_fail(self):
        inputs = passing_inputs()
        inputs["scores"][1]["blocker"] = True
        self.assertEqual(failed_checks(run_gate(inputs)), ["blockers"])

    def test_correctness_drop_over_a_tenth_fails(self):
        inputs = passing_inputs()
        inputs["scores"] = [score("ref", value=3, correctness=5), score("cand", value=4, correctness=4)]
        self.assertIn("correctness", failed_checks(run_gate(inputs)))

    def test_safety_drop_of_exactly_a_tenth_passes(self):
        inputs = passing_inputs()
        inputs["scores"] = [score("ref", value=3, case="a", safety=5), score("ref", value=3, case="b", safety=5),
                            score("cand", value=4, case="a", safety=5), score("cand", value=4, case="b", safety=5)]
        inputs["responses"] = [response("ref", "a"), response("ref", "b"), response("cand", "a"), response("cand", "b")]
        inputs["lint"] += [lint("ref", 0, case="b"), lint("cand", 0, case="b")]
        inputs["jev"] += [jev_row("ref", 0.9, case="b"), jev_row("cand", 0.1, case="b")]
        inputs["scores"][3]["scores"]["safety"] = 4.8
        self.assertNotIn("safety", failed_checks(run_gate(inputs)))

    def test_equal_weighted_score_fails(self):
        inputs = passing_inputs()
        inputs["scores"] = [score("ref", value=4), score("cand", value=4)]
        self.assertEqual(failed_checks(run_gate(inputs)), ["weighted"])

    def test_more_lint_errors_fail(self):
        inputs = passing_inputs()
        inputs["lint"] = [lint("ref", 1), lint("cand", 2)]
        self.assertEqual(failed_checks(run_gate(inputs)), ["lint errors"])

    def test_lint_errors_up_to_10_percent_over_pass(self):
        inputs = passing_inputs()
        inputs["lint"] = [lint("ref", 40), lint("cand", 44)]
        self.assertNotIn("lint errors", failed_checks(run_gate(inputs)))
        inputs["lint"] = [lint("ref", 40), lint("cand", 45)]
        self.assertIn("lint errors", failed_checks(run_gate(inputs)))

    def test_worse_gating_jev_question_fails_and_non_gating_is_ignored(self):
        inputs = full_inputs(["a", "b"])
        inputs["jev"] = [jev_row(name, filler, answers_first=first, case=case) for case in "ab"
                         for name, filler, first in (("ref", 0.1, 0.9), ("cand", 0.9, 0.1))]
        self.assertEqual(failed_checks(run_gate(inputs)), ["jev filler"])

    def test_one_more_bad_jev_answer_passes(self):
        inputs = passing_inputs()
        inputs["jev"] = [jev_row("ref", 0.1), jev_row("cand", 0.9)]
        self.assertEqual(failed_checks(run_gate(inputs)), [])

    def test_refuses_a_different_case_set(self):
        inputs = passing_inputs()
        inputs["scores"].append(score("cand", case="b"))
        self.assertIn("case set", run_gate(inputs)["refused"])

    def test_refuses_a_different_model(self):
        inputs = passing_inputs()
        inputs["responses"] = [response("ref"), response("cand", model="other")]
        self.assertIn("model", run_gate(inputs)["refused"])

    def test_refuses_when_the_models_used_differ(self):
        inputs = passing_inputs()
        inputs["responses"] = [response("ref", models=["m"]), response("cand", models=["m", "claude-haiku"])]
        refused = run_gate(inputs)["refused"]
        self.assertIn("models used differ", refused)
        self.assertIn("claude-haiku", refused)
        inputs["responses"] = [response("ref", models=["m"]), response("cand", models=["m"])]
        self.assertIsNone(run_gate(inputs)["refused"])

    def test_refuses_a_different_rubric(self):
        inputs = passing_inputs()
        inputs["scores"] = [score("ref", value=3), score("cand", value=4, digest="h2")]
        self.assertIn("rubric", run_gate(inputs)["refused"])

    def test_refuses_when_nothing_is_scored(self):
        inputs = passing_inputs()
        inputs["scores"] = []
        self.assertIn("no scored", run_gate(inputs)["refused"])

    def test_refuses_when_candidate_lint_rows_are_stale(self):
        inputs = passing_inputs()
        inputs["lint"] = [lint("ref", 2), lint("cand", 0, text="old")]
        refused = run_gate(inputs)["refused"]
        self.assertIn("lint rows missing for 1 candidate", refused)
        self.assertIn("rerun lint.py", refused)

    def test_refuses_when_candidate_has_fewer_lint_rows(self):
        inputs = full_inputs(["a", "b"])
        inputs["lint"] = [row for row in inputs["lint"] if not (row["condition"] == "cand" and row["case_id"] == "b")]
        self.assertIn("lint rows missing", run_gate(inputs)["refused"])

    def test_a_case_with_lint_false_needs_no_lint_row(self):
        inputs = passing_inputs()
        inputs["lint"] = []
        result = run_gate(inputs, cases=[{"id": "a", "kind": "chat", "lint": False}])
        self.assertIsNone(result["refused"])

    def test_refuses_when_the_candidate_failed_every_response_for_a_case(self):
        inputs = full_inputs(["a", "b"])
        inputs["responses"].append({"case_id": "b", "trial": 1, "condition": "cand", "ok": False, "error": "boom"})
        inputs["scores"] = [row for row in inputs["scores"] if row["case_id"] != "b"]
        refused = run_gate(inputs)["refused"]
        self.assertIn("1 of 2", refused)

    def test_refuses_a_cap_stopped_run(self):
        inputs = passing_inputs()
        inputs["responses"] = [response("ref", trials=3), response("cand", trials=3)]
        refused = run_gate(inputs)["refused"]
        self.assertIn("2 of 3", refused)

    def test_refuses_when_candidate_has_2_of_4_gating_jev_answers(self):
        inputs = full_inputs(["a", "b", "c", "d"])
        inputs["jev"] = [jev_row("ref", 0.1, case="a"), jev_row("ref", 0.1, case="b"),
                         jev_row("ref", 0.9, case="c"), jev_row("ref", 0.9, case="d"),
                         jev_row("cand", 0.9, case="a"), jev_row("cand", 0.1, case="b")]
        inputs["jev"] += [{"case_id": case, "trial": 1, "condition": "cand", "ok": False, "reason": "timeout"}
                          for case in ("c", "d")]
        refused = run_gate(inputs)["refused"]
        self.assertIn("Jev answers missing for 2 of 4 responses on filler", refused)
        self.assertIn("rerun jev.py", refused)

    def test_refuses_when_one_side_has_no_gating_jev_answers(self):
        inputs = passing_inputs()
        inputs["jev"] = [jev_row("ref", 0.9)]
        self.assertIn("Jev answers missing for 1 of 1 responses on filler", run_gate(inputs)["refused"])

    def test_full_jev_pairing_evaluates_the_rule(self):
        inputs = full_inputs(["a", "b", "c", "d"])
        inputs["jev"] = [jev_row(name, value, case=case) for name, values in (("ref", (0.1, 0.1, 0.9, 0.9)),
                                                                              ("cand", (0.9, 0.9, 0.9, 0.9)))
                         for case, value in zip("abcd", values)]
        result = run_gate(inputs)
        self.assertIsNone(result["refused"])
        self.assertEqual(failed_checks(result), ["jev filler"])
        inputs["jev"] = [jev_row(row["condition"], 0.1 if row["condition"] == "cand" else row["answers"]["filler"],
                                 case=row["case_id"]) for row in inputs["jev"]]
        self.assertTrue(run_gate(inputs)["passed"])

    def test_a_gating_question_that_applies_to_no_scored_case_is_skipped(self):
        inputs = passing_inputs()
        inputs["jev"] = []
        result = run_gate(inputs, cases=[{"id": "a", "kind": "commit"}])
        self.assertIsNone(result["refused"])
        self.assertNotIn("jev filler", [name for name, _ok, _detail in result["checks"]])


class RenderTest(unittest.TestCase):
    def test_render_marks_a_partial_run_and_shows_the_gate(self):
        inputs = passing_inputs()
        cases = [{"id": "a", "kind": "chat"}, {"id": "b", "kind": "chat"}]
        text = report.render(cases, ["ref", "cand"], inputs["responses"], inputs["scores"], inputs["lint"],
                             inputs["jev"], QUESTIONS, run_gate(inputs))
        self.assertIn("partial", text.lower())
        self.assertIn("Gate: PASSED", text)
        self.assertIn("| ref |", text)

    def test_render_uses_the_trials_asked_for_when_the_cap_stopped_after_trial_1(self):
        cases = [{"id": "a", "kind": "chat"}]
        responses = [response("ref", trials=3), response("cand", trials=3)]
        text = report.render(cases, ["ref", "cand"], responses, [], [], [], QUESTIONS)
        self.assertIn("2 of 6 responses", text)

    def test_render_counts_lint_only_for_groups_every_condition_scored(self):
        responses = [response("ref"), response("cand"), response("ref", case="b")]
        scores = [score("ref"), score("cand"), score("ref", case="b")]
        rows = [lint("ref", 2), lint("cand", 1), lint("ref", 7, case="b")]
        cases = [{"id": "a", "kind": "chat"}, {"id": "b", "kind": "chat"}]
        text = report.render(cases, ["ref", "cand"], responses, scores, rows, [], QUESTIONS)
        self.assertIn("| ref | 1 | 2 | 0 |", text)

    def test_render_reports_stale_rows(self):
        cases = [{"id": "a", "kind": "chat"}]
        text = report.render(cases, ["ref"], [response("ref")], [], [], [], QUESTIONS, stale_scores=3, stale_jev=2)
        self.assertIn("3 score rows are stale and were left out", text)
        self.assertIn("2 Jev rows are stale and were left out", text)
        clean = report.render(cases, ["ref"], [response("ref")], [], [], [], QUESTIONS)
        self.assertNotIn("stale", clean)

    def test_render_reports_stale_lint_rows(self):
        cases = [{"id": "a", "kind": "chat"}]
        text = report.render(cases, ["ref"], [response("ref")], [], [], [], QUESTIONS, stale_lint=4)
        self.assertIn("4 lint rows are stale and were left out", text)

    def test_render_notes_unbalanced_label_positions(self):
        cases = [{"id": "a", "kind": "chat"}]
        two = [response("ref", trials=2), response("cand", trials=2)]
        text = report.render(cases, ["ref", "cand", "other"], two, [], [], [], QUESTIONS)
        self.assertIn("Label positions are not balanced", text)
        self.assertIn("2 trials", text)
        self.assertIn("3 conditions", text)
        three = [response("ref", trials=3), response("cand", trials=3)]
        self.assertNotIn("not balanced", report.render(cases, ["ref", "cand", "other"], three, [], [], [], QUESTIONS))

    def test_render_counts_responses_that_jev_never_saw(self):
        responses = [response("x"), response("x", case="b"), response("y")]
        rows = [fresh_jev_row("y", "t")]
        text = report.render(JEV_CASES, ["x", "y"], responses, [], [], rows, JEV_QUESTIONS)
        self.assertIn("not sent", text)
        x_line = next(line for line in text.splitlines() if line.startswith("| x |") and "(" in line)
        y_line = next(line for line in text.splitlines() if line.startswith("| y |") and "(" in line)
        # x: case a has no Jev row, case b (commit) has no applicable question.
        self.assertTrue(x_line.rstrip().endswith("| 0 | 1 |"), x_line)
        self.assertTrue(y_line.rstrip().endswith("| 0 | 0 |"), y_line)

    def test_render_says_when_responses_failed_but_all_were_attempted(self):
        failed = {"case_id": "a", "trial": 1, "condition": "cand", "ok": False, "error": "boom"}
        text = report.render([{"id": "a", "kind": "chat"}], ["ref", "cand"], [response("ref"), failed], [], [], [],
                             QUESTIONS)
        self.assertIn("1 of 2 responses succeeded", text)
        self.assertNotIn("partial", text.lower())

    def test_render_shows_both_lines_when_both_hold(self):
        failed = {"case_id": "a", "trial": 1, "condition": "cand", "ok": False, "error": "boom"}
        cases = [{"id": "a", "kind": "chat"}, {"id": "b", "kind": "chat"}]
        text = report.render(cases, ["ref", "cand"], [response("ref"), failed], [], [], [], QUESTIONS)
        self.assertIn("This run is partial:** 2 of 4 responses exist", text)
        self.assertIn("1 of 4 responses succeeded", text)

    def test_render_counts_only_responses_for_known_cases_and_conditions(self):
        cases = [{"id": "a", "kind": "chat"}, {"id": "b", "kind": "chat"}]
        responses = [response("ref"), response("ref", case="z"), response("other")]
        text = report.render(cases, ["ref"], responses, [], [], [], QUESTIONS)
        self.assertIn("1 of 2 responses exist", text)

    def test_render_says_when_there_are_no_responses(self):
        text = report.render([{"id": "a", "kind": "chat"}], ["ref"], [], [], [], [], QUESTIONS)
        self.assertIn("No responses in this run", text)

    def test_render_shows_the_slowest_call_for_each_stage(self):
        responses = [dict(response("ref"), duration_ms=43200), dict(response("cand"), duration_ms=1000),
                     response("ref", case="b")]
        scores = [dict(score("ref"), duration_ms=12400), dict(score("cand"), duration_ms=12400)]
        cases = [{"id": "a", "kind": "chat"}, {"id": "b", "kind": "chat"}]
        text = report.render(cases, ["ref", "cand"], responses, scores, [], [], QUESTIONS)
        self.assertIn("Slowest call: generate 43 s, judge 12 s.", text)
        bare = report.render(cases, ["ref", "cand"], [response("ref")], [], [], [], QUESTIONS)
        self.assertNotIn("Slowest call", bare)

    def test_the_slowest_call_comes_after_the_failure_list(self):
        failed = {"case_id": "a", "trial": 1, "condition": "cand", "ok": False, "error": "boom", "duration_ms": 5000}
        text = report.render([{"id": "a", "kind": "chat"}], ["ref", "cand"], [response("ref"), failed], [], [], [],
                             QUESTIONS)
        self.assertLess(text.index("## Failed rows"), text.index("Slowest call: generate 5 s."))

    def test_render_lists_a_failed_judge_group_once(self):
        rows = [{"case_id": "a", "trial": 1, "condition": name, "ok": False, "error": "invalid-json"}
                for name in ("ref", "cand")]
        text = report.render([{"id": "a", "kind": "chat"}], ["ref", "cand"], [response("ref"), response("cand")], rows,
                             [], [], QUESTIONS)
        failed = [line for line in text.splitlines() if line.startswith("- a trial 1")]
        self.assertEqual(len(failed), 1, failed)
        self.assertIn("invalid-json", failed[0])


class MainTest(unittest.TestCase):
    def test_main_leaves_stale_rows_out_of_the_report(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(common, "RUNS_ROOT", Path(tmp)):
            folder = common.run_dir("r1")
            case = common.load_cases()[0]
            with (folder / "responses.jsonl").open("w", encoding="utf-8") as handle:
                for name in common.load_conditions()["conditions"]:
                    row = dict(response(name, case=case["id"], model="claude-opus-5-5"), effort="medium", trials=1,
                               input_hash=common.response_hash(case, common.load_conditions(), name))
                    handle.write(json.dumps(row) + "\n")
            with (folder / "scores.jsonl").open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(dict(score("baseline", case=case["id"]), group_hash="stale")) + "\n")
            with (folder / "jev.jsonl").open("w", encoding="utf-8") as handle:
                stale = {"case_id": case["id"], "trial": 1, "condition": "baseline", "ok": True,
                         "answers": {}, "text_hash": "stale"}
                handle.write(json.dumps(stale) + "\n")
            with (folder / "lint.jsonl").open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(lint("baseline", 3, case=case["id"], text="older text")) + "\n")
            with contextlib.redirect_stdout(io.StringIO()):
                code = report.main(["--run-id", "r1"])
            text = (folder / "report.md").read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("1 score rows are stale and were left out", text)
        self.assertIn("1 Jev rows are stale and were left out", text)
        self.assertIn("1 lint rows are stale and were left out", text)

    def write_full_run(self, folder, skill_value, lint_skill=True, cfg=None):
        """A complete fresh run for the real cases and conditions, with 1 trial."""
        cases, cfg = common.load_cases(), cfg or common.load_conditions()
        rubric = (common.EVALS_DIR / "rubric.md").read_text(encoding="utf-8")
        responses = [dict(response(name, case=case["id"], model=cfg["model"], text="Text %s %s" % (case["id"], name),
                                   trials=1), effort=cfg.get("effort"), input_hash=common.response_hash(case, cfg, name))
                     for case in cases for name in cfg["conditions"]]
        current = judge.current_group_hashes(cases, responses, cfg, rubric)
        scores = [dict(score(row["condition"], case=row["case_id"],
                             value=skill_value if row["condition"] == "skill" else 3, digest=judge.rubric_hash(rubric)),
                       group_hash=current[(row["case_id"], 1)]) for row in responses]
        lintable = {case["id"] for case in cases if case.get("lint", True)}
        lints = [lint(row["condition"], 0, case=row["case_id"], text=row["text"]) for row in responses
                 if row["case_id"] in lintable and (lint_skill or row["condition"] != "skill")]
        # A clean Jev answer for every response, so a gating question never refuses the gate.
        questions, by_case = jev.load_questions(), {case["id"]: case for case in cases}
        jev_rows = []
        for row in responses:
            case = by_case[row["case_id"]]
            asked = jev.request_questions(questions, case)
            if asked:
                jev_rows.append({"case_id": row["case_id"], "trial": row["trial"], "condition": row["condition"],
                                 "ok": True, "text_hash": jev.row_hash(case, row["text"], asked),
                                 "answers": {q: 1.0 if questions[q]["bad_when"] == "no" else 0.0 for q in asked}})
        for name, rows in (("responses", responses), ("scores", scores), ("lint", lints), ("jev", jev_rows)):
            with (folder / ("%s.jsonl" % name)).open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")

    def run_main(self, *args, **run):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(common, "RUNS_ROOT", Path(tmp)):
            folder = common.run_dir("r1")
            if run:
                self.write_full_run(folder, **run)
            with contextlib.redirect_stdout(io.StringIO()):
                code = report.main(["--run-id", "r1"] + list(args))
            return code, (folder / "report.md").read_text(encoding="utf-8")

    def test_main_exits_0_when_the_gate_passes(self):
        code, text = self.run_main("--reference", "baseline", "--candidate", "skill", skill_value=4)
        self.assertEqual(code, 0, text)
        self.assertIn("Gate: PASSED", text)

    def test_main_exits_1_when_the_gate_fails(self):
        code, text = self.run_main("--reference", "baseline", "--candidate", "skill", skill_value=2)
        self.assertEqual(code, 1, text)
        self.assertIn("Gate: FAILED", text)

    def test_main_exits_2_when_the_gate_refuses(self):
        code, text = self.run_main("--reference", "baseline", "--candidate", "skill", skill_value=4, lint_skill=False)
        self.assertEqual(code, 2, text)
        self.assertIn("lint rows missing", text)

    def run_stale_main(self, edit):
        """A full fresh run, then `edit(cfg, skill_file)` changes the inputs without rerunning generate.py."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(common, "RUNS_ROOT", Path(tmp)):
            skill = Path(tmp) / "skill.md"
            skill.write_text("Rule one.\n", encoding="utf-8")
            cfg = common.load_conditions()
            cfg["conditions"]["skill"] = str(skill)
            folder = common.run_dir("r1")
            self.write_full_run(folder, skill_value=4, cfg=json.loads(json.dumps(cfg)))
            edit(cfg, skill)
            out = io.StringIO()
            with mock.patch.object(common, "load_conditions", return_value=cfg), contextlib.redirect_stdout(out):
                code = report.main(["--run-id", "r1", "--reference", "baseline", "--candidate", "skill"])
            return code, (folder / "report.md").read_text(encoding="utf-8"), out.getvalue()

    def test_an_edited_condition_text_without_generate_refuses_the_gate(self):
        code, text, printed = self.run_stale_main(lambda cfg, skill: skill.write_text("Rule two.\n", encoding="utf-8"))
        count = len(common.load_cases())
        self.assertEqual(code, 2, text)
        self.assertIn("Gate: REFUSED", text)
        self.assertIn("%d responses are out of date; rerun generate.py" % count, text)
        first = sorted(case["id"] for case in common.load_cases())[0]
        self.assertIn("%s trial 1 skill" % first, text)
        self.assertIn("out of date", printed)

    def test_a_changed_model_without_generate_refuses_the_gate(self):
        code, text, _ = self.run_stale_main(lambda cfg, skill: cfg.update(model="claude-other"))
        count = len(common.load_cases()) * 3
        self.assertEqual(code, 2, text)
        self.assertIn("%d responses are out of date; rerun generate.py" % count, text)
        self.assertIn("Gate: REFUSED", text)

    def test_main_exits_2_when_there_are_no_responses(self):
        code, text = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("No responses in this run", text)


if __name__ == "__main__":
    unittest.main()
