import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common
import generate

CFG = {"model": "claude-x", "effort": "medium",
       "conditions": {"baseline": None, "skill": "skills/simple-english/SKILL.md"}}
CASES = [{"id": "a", "kind": "chat", "prompt": "PA"}, {"id": "b", "kind": "chat", "prompt": "PB"}]
ONE = {"model": "claude-x", "conditions": {"baseline": None}}  # 1 condition, so every row adds to 1 failure count


class FakeCall:
    def __init__(self, results=None, cost=0.01):
        self.calls = []
        self.results = list(results or [])
        self.cost = cost

    def __call__(self, prompt, system_text, model, budget_usd, effort=None):
        self.calls.append({"prompt": prompt, "system": system_text, "model": model, "budget": budget_usd,
                           "effort": effort})
        if self.results:
            return self.results.pop(0)
        return {"ok": True, "text": "answer to " + prompt, "cost_usd": self.cost, "models": [model]}


class GenerateTest(unittest.TestCase):
    def test_one_row_per_case_trial_and_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            call = FakeCall()
            summary = generate.generate(CASES, CFG, 2, 5.0, out, call=call)
            rows = common.read_jsonl(out)
            self.assertEqual(len(rows), 8)
            self.assertEqual(summary["made"], 8)
            self.assertFalse(summary["stopped"])
            row = common.latest(rows)[("a", 1, "skill")]
            self.assertEqual(row["text"], "answer to PA")
            self.assertEqual(row["model"], "claude-x")
            self.assertEqual(row["effort"], "medium")
            self.assertEqual(call.calls[0]["effort"], "medium")

    def test_baseline_gets_no_system_text_and_skill_gets_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            call = FakeCall()
            generate.generate(CASES[:1], CFG, 1, 5.0, Path(tmp) / "r.jsonl", call=call)
            self.assertEqual(call.calls[0]["system"], "")
            self.assertTrue(call.calls[1]["system"].startswith("# Simple English"))

    def test_rerun_skips_finished_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES, CFG, 1, 5.0, out, call=FakeCall())
            again = FakeCall()
            generate.generate(CASES, CFG, 1, 5.0, out, call=again)
            self.assertEqual(again.calls, [])

    def test_two_retries_then_a_success_sums_the_cost(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.02}
        call = FakeCall(results=[fail, fail])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out, call=call)
            row = common.read_jsonl(out)[0]
            self.assertEqual(len(call.calls), 3)
            self.assertTrue(row["ok"])
            self.assertAlmostEqual(row["cost_usd"], 0.05)

    def test_three_failures_store_the_error(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.0}
        call = FakeCall(results=[fail, fail, fail])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            summary = generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out, call=call)
            row = common.read_jsonl(out)[0]
            self.assertFalse(row["ok"])
            self.assertEqual(row["error"], "boom")
            self.assertEqual(summary["failed"], 1)

    def test_budget_stops_the_stage_and_passes_the_remainder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            call = FakeCall(cost=0.01)
            summary = generate.generate(CASES, CFG, 1, 0.035, out, call=call)
            self.assertTrue(summary["stopped"])
            self.assertEqual(len(call.calls), 3)
            self.assertAlmostEqual(call.calls[1]["budget"], 0.025)
            rows = common.read_jsonl(out)
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertAlmostEqual(row["cost_usd"], 0.01)

    def test_cap_reached_partway_through_retries_writes_the_row_and_stops(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.03}
        call = FakeCall(results=[fail, fail, fail])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            summary = generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 0.05, out,
                                        call=call)
            rows = common.read_jsonl(out)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["ok"])
            self.assertAlmostEqual(rows[0]["cost_usd"], 0.06)
            self.assertEqual(len(call.calls), 2)
            self.assertTrue(summary["stopped"])

    def test_remainder_below_the_minimum_makes_no_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            call = FakeCall()
            summary = generate.generate(CASES, CFG, 1, 1.0, Path(tmp) / "r.jsonl", spent_so_far=0.995, call=call)
            self.assertTrue(summary["stopped"])
            self.assertEqual(call.calls, [])

    def test_failed_row_is_retried_on_the_next_run(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.01}
        bare = {"model": "m", "conditions": {"baseline": None}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES[:1], bare, 1, 5.0, out, call=FakeCall(results=[fail, fail, fail]))
            again = FakeCall(cost=0.02)
            generate.generate(CASES[:1], bare, 1, 5.0, out, call=again)
            rows = common.read_jsonl(out)
            self.assertEqual(len(again.calls), 1)
            self.assertEqual(len(rows), 2)
            self.assertTrue(common.latest(rows)[("a", 1, "baseline")]["ok"])
            self.assertAlmostEqual(common.spent(Path(tmp)), 0.05)

    def test_exception_then_success_writes_an_ok_row(self):
        calls = []

        def call(prompt, system_text, model, budget_usd, effort=None):
            calls.append(prompt)
            if len(calls) == 1:
                raise RuntimeError("network down")
            return {"ok": True, "text": "fine", "cost_usd": 0.01, "models": [model]}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out, call=call)
            rows = common.read_jsonl(out)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["ok"])
            # The exception reported no cost, so it counts as the per-call cap.
            self.assertAlmostEqual(rows[0]["cost_usd"], common.PER_CALL_CAP_USD + 0.01)
            self.assertTrue(rows[0]["cost_estimated"])

    def test_exception_on_every_attempt_writes_a_failed_row(self):
        def call(prompt, system_text, model, budget_usd, effort=None):
            raise RuntimeError("network down")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            summary = generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out,
                                        call=call)
            rows = common.read_jsonl(out)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["ok"])
            self.assertIn("network down", rows[0]["error"])
            self.assertEqual(summary["failed"], 1)

    def test_changed_input_hash_is_regenerated_and_same_hash_is_skipped(self):
        bare = {"model": "m", "conditions": {"baseline": None}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES, bare, 1, 5.0, out, call=FakeCall())
            same = FakeCall()
            generate.generate(CASES, bare, 1, 5.0, out, call=same)
            self.assertEqual(same.calls, [])
            changed = [dict(CASES[0], prompt="PA changed"), CASES[1]]
            again = FakeCall()
            generate.generate(changed, bare, 1, 5.0, out, call=again)
            self.assertEqual([c["prompt"] for c in again.calls], ["PA changed"])
            self.assertEqual(common.latest(common.read_jsonl(out))[("a", 1, "baseline")]["text"],
                             "answer to PA changed")

    def test_changed_effort_or_model_regenerates_rows(self):
        bare = {"model": "m", "effort": "low", "conditions": {"baseline": None}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES, bare, 1, 5.0, out, call=FakeCall())
            higher = FakeCall()
            generate.generate(CASES, dict(bare, effort="high"), 1, 5.0, out, call=higher)
            self.assertEqual(len(higher.calls), 2)
            other = FakeCall()
            generate.generate(CASES, dict(bare, effort="high", model="m2"), 1, 5.0, out, call=other)
            self.assertEqual(len(other.calls), 2)

    def test_every_row_records_trials_and_input_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES, CFG, 2, 5.0, out, call=FakeCall())
            by_case = {case["id"]: case for case in CASES}
            for row in common.read_jsonl(out):
                self.assertEqual(row["trials"], 2)
                self.assertEqual(row["input_hash"], common.response_hash(by_case[row["case_id"]], CFG, row["condition"]))

    def test_each_call_gets_at_most_the_per_call_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            call = FakeCall()
            generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0,
                              Path(tmp) / "r.jsonl", call=call)
            self.assertEqual(call.calls[0]["budget"], common.PER_CALL_CAP_USD)

    def test_a_timeout_records_the_cap_as_an_estimated_cost(self):
        timeout = {"ok": False, "error": "timeout", "cost_usd": None}
        call = FakeCall(results=[timeout])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "responses.jsonl"
            generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out, call=call)
            row = common.read_jsonl(out)[0]
            self.assertTrue(row["ok"])
            self.assertAlmostEqual(row["cost_usd"], common.PER_CALL_CAP_USD + 0.01)
            self.assertTrue(row["cost_estimated"])
            self.assertAlmostEqual(common.spent(Path(tmp)), common.PER_CALL_CAP_USD + 0.01)

    def test_a_priced_row_has_no_estimate_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            generate.generate(CASES[:1], {"model": "m", "conditions": {"baseline": None}}, 1, 5.0, out, call=FakeCall())
            self.assertNotIn("cost_estimated", common.read_jsonl(out)[0])

    def test_three_unpriced_attempts_in_a_row_stop_the_stage(self):
        timeout = {"ok": False, "error": "timeout", "cost_usd": None}
        call = FakeCall(results=[timeout] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, ONE, 2, 50.0, out, call=call, retries=0)
            rows = common.read_jsonl(out)
        self.assertEqual(summary["stopped"], "timeouts")
        self.assertEqual(len(call.calls), 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not row["ok"] and row["cost_estimated"] for row in rows))

    def test_a_priced_attempt_resets_the_unpriced_count(self):
        timeout = {"ok": False, "error": "timeout", "cost_usd": None}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["m"]}
        call = FakeCall(results=[timeout, timeout, good, timeout, timeout, good])
        with tempfile.TemporaryDirectory() as tmp:
            summary = generate.generate(CASES, {"model": "m", "conditions": {"baseline": None}}, 1, 50.0,
                                        Path(tmp) / "r.jsonl", call=call)
        self.assertFalse(summary["stopped"])
        self.assertEqual(summary["made"], 2)

    def test_three_priced_failures_in_a_row_stop_the_stage(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.01}
        call = FakeCall(results=[fail] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, ONE, 2, 50.0, out, call=call, retries=0)
            rows = common.read_jsonl(out)
        self.assertEqual(summary["stopped"], "failures")
        self.assertEqual(summary["error"], "boom")
        self.assertEqual(len(call.calls), 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all("cost_estimated" not in row for row in rows))

    def test_one_row_that_always_fails_is_recorded_and_the_stage_carries_on(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        call = FakeCall(results=[fake, fake, fake])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, CFG, 1, 50.0, out, call=call)
            rows = common.latest(common.read_jsonl(out))
        self.assertFalse(summary["stopped"])
        self.assertEqual(len(call.calls), 6)
        self.assertEqual((summary["made"], summary["failed"]), (3, 1))
        self.assertEqual(rows[("a", 1, "baseline")]["error"], "fake-tool-call")
        self.assertTrue(rows[("b", 1, "skill")]["ok"])

    def test_three_failed_rows_in_a_row_stop_the_stage_after_their_retries(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        call = FakeCall(results=[fake] * 12)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, ONE, 2, 50.0, out, call=call)
            rows = common.read_jsonl(out)
        self.assertEqual(summary["stopped"], "failures")
        self.assertEqual(len(call.calls), 9)
        self.assertEqual(len(rows), 3)

    def test_a_condition_that_always_fails_stops_the_stage_and_is_named(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["claude-x"]}
        calls = []

        def call(prompt, system_text, model, budget_usd, effort=None):
            calls.append(system_text)
            return dict(fake if system_text == "" else good)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, CFG, 3, 50.0, out, call=call)
            rows = common.read_jsonl(out)
        self.assertEqual(summary["stopped"], "failures")
        self.assertEqual(summary["condition"], "baseline")
        # baseline fails a1, b1, a2 with 3 attempts each; skill succeeds on a1 and b1 in between.
        self.assertEqual(len(calls), 11)
        self.assertEqual([(r["case_id"], r["trial"]) for r in rows if r["condition"] == "baseline"],
                         [("a", 1), ("b", 1), ("a", 2)])
        self.assertIn("for condition baseline", common.stop_message("generate", summary))

    def test_every_call_failing_stops_after_3_rows_across_conditions(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        call = FakeCall(results=[fake] * 30)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            summary = generate.generate(CASES, CFG, 3, 50.0, out, call=call)
            rows = common.read_jsonl(out)
        self.assertEqual(summary["stopped"], "failures")
        self.assertIsNone(summary["condition"])
        self.assertEqual(len(call.calls), 9)
        self.assertEqual(len(rows), 3)
        self.assertIn("3 rows in a row across conditions", common.stop_message("generate", summary))

    def test_one_row_in_three_failing_across_conditions_does_not_stop(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["claude-x"]}
        count = [0]

        def call(prompt, system_text, model, budget_usd, effort=None):
            count[0] += 1
            return dict(fake if count[0] % 3 == 1 else good)

        with tempfile.TemporaryDirectory() as tmp:
            summary = generate.generate(CASES, CFG, 3, 50.0, Path(tmp) / "r.jsonl", call=call, retries=0)
        self.assertFalse(summary["stopped"])
        self.assertEqual(count[0], 12)
        self.assertEqual((summary["made"], summary["failed"]), (8, 4))

    def content_failure_run(self, error, **kwargs):
        """A first run where baseline fails on every attempt with `error`, then a second run, which returns its calls."""
        bad = {"ok": False, "error": error, "cost_usd": 0.01}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            generate.generate(CASES[:1], ONE, 1, 5.0, out, call=FakeCall(results=[bad] * 3))
            again = FakeCall()
            summary = generate.generate(CASES[:1], ONE, 1, 5.0, out, call=again, **kwargs)
            latest = common.latest(common.read_jsonl(out))[("a", 1, "baseline")]
        return again.calls, summary, latest

    def test_a_row_that_failed_on_its_content_is_skipped_on_the_next_run(self):
        for error in ("fake-tool-call", "empty-result", "bad-result"):
            with self.subTest(error=error):
                calls, summary, latest = self.content_failure_run(error)
                self.assertEqual(calls, [])
                self.assertEqual(summary["skipped"], 1)
                self.assertEqual(latest["error"], error)

    def test_retry_failed_tries_a_content_failure_again(self):
        calls, summary, latest = self.content_failure_run("fake-tool-call", retry_failed=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(summary["skipped"], 0)
        self.assertTrue(latest["ok"])

    def test_a_timeout_or_other_failure_is_still_retried(self):
        for error in ("timeout", "boom", "max-tokens"):
            with self.subTest(error=error):
                calls, summary, latest = self.content_failure_run(error)
                self.assertEqual(len(calls), 1)
                self.assertTrue(latest["ok"])

    def test_a_content_failure_under_a_changed_input_is_retried(self):
        bad = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            generate.generate(CASES[:1], ONE, 1, 5.0, out, call=FakeCall(results=[bad] * 3))
            again = FakeCall()
            generate.generate([dict(CASES[0], prompt="PA changed")], ONE, 1, 5.0, out, call=again)
        self.assertEqual(len(again.calls), 1)

    def test_main_passes_retry_failed_and_prints_the_skipped_count(self):
        for argv, expected in (([], False), (["--retry-failed"], True)):
            with self.subTest(argv=argv):
                out = io.StringIO()
                summary = {"made": 0, "failed": 0, "stopped": False, "spent": 0.0, "skipped": 2}
                with mock.patch.object(generate, "generate", return_value=summary) as stage, \
                        mock.patch.object(generate.common, "require_claude"), \
                        mock.patch.object(generate.common, "run_dir", return_value=Path("nowhere")), \
                        mock.patch.object(generate.common, "spent", return_value=0.0), \
                        contextlib.redirect_stdout(out):
                    generate.main(["--run-id", "r", "--budget-usd", "5"] + argv)
                self.assertIs(stage.call_args.kwargs["retry_failed"], expected)
                self.assertIn("skipped 2 rows that failed on their content", out.getvalue())

    def test_failed_ok_failed_failed_rows_do_not_stop(self):
        fake = {"ok": False, "error": "fake-tool-call", "cost_usd": 0.01}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["claude-x"]}
        call = FakeCall(results=[fake] * 3 + [good] + [fake] * 6)
        with tempfile.TemporaryDirectory() as tmp:
            summary = generate.generate(CASES, CFG, 1, 50.0, Path(tmp) / "r.jsonl", call=call)
        self.assertFalse(summary["stopped"])
        self.assertEqual(len(call.calls), 10)
        self.assertEqual((summary["made"], summary["failed"]), (1, 3))

    def test_a_row_stores_the_slowest_duration_of_its_attempts(self):
        slow_fail = {"ok": False, "error": "boom", "cost_usd": 0.01, "duration_ms": 9000}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["m"], "duration_ms": 1200}
        bare = {"model": "m", "conditions": {"baseline": None}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.jsonl"
            generate.generate(CASES, bare, 1, 5.0, out, call=FakeCall(results=[slow_fail, good]))
            rows = common.latest(common.read_jsonl(out))
        self.assertEqual(rows[("a", 1, "baseline")]["duration_ms"], 9000)
        self.assertNotIn("duration_ms", rows[("b", 1, "baseline")])

    def test_failure_success_failure_failure_does_not_stop(self):
        fail = {"ok": False, "error": "boom", "cost_usd": 0.01}
        good = {"ok": True, "text": "fine", "cost_usd": 0.01, "models": ["claude-x"]}
        call = FakeCall(results=[fail, good, fail, fail])
        with tempfile.TemporaryDirectory() as tmp:
            summary = generate.generate(CASES, CFG, 1, 50.0, Path(tmp) / "r.jsonl", call=call, retries=0)
        self.assertFalse(summary["stopped"])
        self.assertEqual(len(call.calls), 4)
        self.assertEqual((summary["made"], summary["failed"]), (1, 3))

    def test_main_exits_non_zero_after_the_failure_stop_and_prints_the_error(self):
        out = io.StringIO()
        with mock.patch.object(generate, "generate", return_value={"made": 0, "failed": 3, "stopped": "failures",
                                                                   "spent": 0.03, "error": "exit 1: auth"}), \
                mock.patch.object(generate.common, "require_claude"), \
                mock.patch.object(generate.common, "run_dir", return_value=Path("nowhere")), \
                mock.patch.object(generate.common, "spent", return_value=0.0), \
                contextlib.redirect_stdout(out):
            code = generate.main(["--run-id", "r", "--budget-usd", "5"])
        self.assertEqual(code, 1)
        self.assertIn("3 rows in a row failed after their retries", out.getvalue())
        self.assertIn("exit 1: auth", out.getvalue())

    def test_main_exits_non_zero_after_the_timeout_stop(self):
        out = io.StringIO()
        with mock.patch.object(generate, "generate", return_value={"made": 0, "failed": 3, "stopped": "timeouts",
                                                                   "spent": 1.5}), \
                mock.patch.object(generate.common, "require_claude"), \
                mock.patch.object(generate.common, "run_dir", return_value=Path("nowhere")), \
                mock.patch.object(generate.common, "spent", return_value=0.0), \
                contextlib.redirect_stdout(out):
            code = generate.main(["--run-id", "r", "--budget-usd", "5"])
        self.assertEqual(code, 1)
        self.assertIn("3 rows in a row failed on a timeout or a call that reported no cost", out.getvalue())

    def test_money_already_spent_counts_against_the_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            call = FakeCall()
            summary = generate.generate(CASES, CFG, 1, 1.0, Path(tmp) / "r.jsonl", spent_so_far=1.0, call=call)
            self.assertTrue(summary["stopped"])
            self.assertEqual(call.calls, [])


if __name__ == "__main__":
    unittest.main()
