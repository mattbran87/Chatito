import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common


class FrontmatterTest(unittest.TestCase):
    def test_strips_a_closed_block(self):
        text = "---\nname: x\ndescription: y\n---\n\n# Body\n\nText.\n"
        self.assertEqual(common.strip_frontmatter(text), "# Body\n\nText.")

    def test_keeps_an_unterminated_block(self):
        text = "---\nname: x\n# Body\n"
        self.assertEqual(common.strip_frontmatter(text), text.strip())

    def test_keeps_text_without_a_block(self):
        self.assertEqual(common.strip_frontmatter("# Body\n"), "# Body")


class ResponseHashTest(unittest.TestCase):
    CFG = {"model": "m", "effort": "low", "conditions": {"baseline": None, "skill": "skills/simple-english/SKILL.md"}}
    CASE = {"id": "a", "prompt": "P"}

    def test_the_hash_covers_prompt_model_effort_and_condition_text(self):
        base = common.response_hash(self.CASE, self.CFG, "skill")
        # A row made before the note existed stores the old formula, so it is out of date now.
        self.assertNotEqual(base, common.input_hash("P", "m\x00low\x00" + common.condition_text(self.CFG, "skill")))
        with mock.patch.object(common, "NO_TOOLS_NOTE", "Another note."):
            self.assertNotEqual(base, common.response_hash(self.CASE, self.CFG, "skill"))
            baseline = common.response_hash(self.CASE, self.CFG, "baseline")
        self.assertNotEqual(baseline, common.response_hash(self.CASE, self.CFG, "baseline"))
        sent = common.system_text_for(common.condition_text(self.CFG, "skill"))
        self.assertEqual(base, common.input_hash("P", "m\x00low\x00" + sent))
        self.assertNotEqual(base, common.response_hash(dict(self.CASE, prompt="Q"), self.CFG, "skill"))
        self.assertNotEqual(base, common.response_hash(self.CASE, dict(self.CFG, model="m2"), "skill"))
        self.assertNotEqual(base, common.response_hash(self.CASE, dict(self.CFG, effort="high"), "skill"))
        self.assertNotEqual(base, common.response_hash(self.CASE, self.CFG, "baseline"))

    def test_split_drops_ok_rows_whose_hash_differs(self):
        fresh = {"case_id": "a", "trial": 1, "condition": "skill", "ok": True, "text": "x",
                 "input_hash": common.response_hash(self.CASE, self.CFG, "skill")}
        stale = {"case_id": "a", "trial": 1, "condition": "baseline", "ok": True, "text": "y", "input_hash": "old"}
        failed = {"case_id": "a", "trial": 2, "condition": "skill", "ok": False, "error": "boom"}
        unknown = {"case_id": "zz", "trial": 1, "condition": "skill", "ok": True, "text": "z"}
        kept, out_of_date = common.split_out_of_date([fresh, stale, failed, unknown], [self.CASE], self.CFG)
        self.assertEqual(kept, [fresh, failed, unknown])
        self.assertEqual(out_of_date, [("a", 1, "baseline")])
        _, none_hash = common.split_out_of_date([dict(fresh, input_hash=None)], [self.CASE], self.CFG)
        self.assertEqual(none_hash, [("a", 1, "skill")])


class JsonlTest(unittest.TestCase):
    def test_round_trip_and_newest_row_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            self.assertEqual(common.read_jsonl(path), [])
            common.append_jsonl(path, {"case_id": "a", "trial": 1, "condition": "skill", "ok": False})
            common.append_jsonl(path, {"case_id": "a", "trial": 1, "condition": "skill", "ok": True})
            common.append_jsonl(path, {"case_id": "b", "trial": 1, "condition": "skill", "ok": False})
            rows = common.read_jsonl(path)
            self.assertEqual(len(rows), 3)
            self.assertTrue(common.latest(rows)[("a", 1, "skill")]["ok"])

    def test_bad_line_names_its_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"a": 1}\nnot json\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, ":2:"):
                common.read_jsonl(path)

    def test_torn_last_line_without_newline_is_skipped_with_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_bytes(b'{"a": 1}\n{"a": 2, "te')
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                rows = common.read_jsonl(path)
            self.assertEqual(rows, [{"a": 1}])
            self.assertIn("rows.jsonl", err.getvalue())

    def test_bad_line_before_the_last_still_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_bytes(b'{"a": 1}\nnot json\n{"a": 3}')
            with self.assertRaisesRegex(ValueError, ":2:"):
                common.read_jsonl(path)

    def test_bad_last_line_with_a_newline_still_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_bytes(b'{"a": 1}\nnot json\n')
            with self.assertRaisesRegex(ValueError, ":2:"):
                common.read_jsonl(path)


class AppendAfterTornLineTest(unittest.TestCase):
    def test_append_drops_the_torn_tail_so_later_reads_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_bytes(b'{"a": 1}\n{"b":')
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                self.assertEqual(common.read_jsonl(path), [{"a": 1}])
                common.append_jsonl(path, {"c": 3})
                self.assertEqual(common.read_jsonl(path), [{"a": 1}, {"c": 3}])
            self.assertIn("rows.jsonl", err.getvalue())

    def test_append_to_a_file_with_only_a_torn_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_bytes(b'{"b":')
            with mock.patch("sys.stderr", io.StringIO()):
                common.append_jsonl(path, {"c": 3})
            self.assertEqual(common.read_jsonl(path), [{"c": 3}])

    def test_append_to_a_clean_file_changes_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            common.append_jsonl(path, {"a": 1})
            common.append_jsonl(path, {"b": 2})
            self.assertEqual(common.read_jsonl(path), [{"a": 1}, {"b": 2}])


class InputHashTest(unittest.TestCase):
    def test_changes_with_either_input(self):
        base = common.input_hash("prompt", "system")
        self.assertEqual(base, common.input_hash("prompt", "system"))
        self.assertEqual(len(base), 12)
        self.assertNotEqual(base, common.input_hash("prompt2", "system"))
        self.assertNotEqual(base, common.input_hash("prompt", "system2"))
        self.assertNotEqual(common.input_hash("b", "a"), common.input_hash("", "ab"))


class ConditionTextTest(unittest.TestCase):
    def test_baseline_is_empty_and_skill_loses_its_frontmatter(self):
        cfg = {"model": "m", "conditions": {"baseline": None, "skill": "skills/simple-english/SKILL.md"}}
        self.assertEqual(common.condition_text(cfg, "baseline"), "")
        text = common.condition_text(cfg, "skill")
        self.assertTrue(text.startswith("# Simple English"))
        self.assertNotIn("description:", text.splitlines()[0])


class ClaudeArgvTest(unittest.TestCase):
    def test_cmd_shim_with_sibling_exe_runs_the_exe_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            shim = Path(tmp) / "claude.CMD"
            with mock.patch.object(common.shutil, "which", return_value=str(shim)):
                self.assertEqual(common.claude_argv(), [str(exe)])

    def test_cmd_shim_without_sibling_exe_goes_through_cmd(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "claude.CMD"
            with mock.patch.object(common.shutil, "which", return_value=str(shim)):
                argv = common.claude_argv()
        self.assertEqual(argv[1:], ["/c", str(shim)])


class ChildEnvTest(unittest.TestCase):
    def test_drops_claude_variables_except_the_allowlist(self):
        env = {"PATH": "p", "HOME": "h", "CLAUDECODE": "1", "CLAUDE_EFFORT": "high",
               "CLAUDE_CODE_SESSION_ID": "s", "CLAUDE_CONFIG_DIR": "c",
               "CLAUDE_CODE_OAUTH_TOKEN": "t", "CLAUDE_CODE_USE_BEDROCK": "1",
               "CLAUDE_CODE_USE_VERTEX": "1", "CLAUDE_CODE_USE_FOUNDRY": "1"}
        self.assertEqual(common.child_env(env), {
            "PATH": "p", "HOME": "h", "CLAUDE_CONFIG_DIR": "c", "CLAUDE_CODE_OAUTH_TOKEN": "t",
            "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_USE_VERTEX": "1",
            "CLAUDE_CODE_USE_FOUNDRY": "1"})


class ParseOutputTest(unittest.TestCase):
    def test_json_that_is_not_an_object(self):
        for out in ("[1]", '"text"'):
            result = common.parse_claude_output(1, out, "boom")
            self.assertEqual(result, {"ok": False, "error": "exit 1: boom", "cost_usd": None})

    def test_success(self):
        out = json.dumps({"result": "Five", "total_cost_usd": 0.01, "is_error": False,
                          "subtype": "success", "modelUsage": {"claude-x": {}}})
        self.assertEqual(common.parse_claude_output(0, out, ""),
                         {"ok": True, "text": "Five", "cost_usd": 0.01, "models": ["claude-x"]})

    def test_error_subtype_keeps_its_cost(self):
        out = json.dumps({"result": "", "total_cost_usd": 0.2, "is_error": True,
                          "subtype": "error_max_budget_usd"})
        result = common.parse_claude_output(1, out, "")
        self.assertFalse(result["ok"])
        self.assertEqual(result["cost_usd"], 0.2)
        self.assertIn("error_max_budget_usd", result["error"])

    def test_output_that_is_not_json(self):
        result = common.parse_claude_output(1, "", "boom")
        self.assertEqual(result, {"ok": False, "error": "exit 1: boom", "cost_usd": None})

    def success(self, **extra):
        data = {"result": "Five", "total_cost_usd": 0.04, "is_error": False, "subtype": "success",
                "modelUsage": {"claude-x": {}}}
        data.update(extra)
        return common.parse_claude_output(0, json.dumps(data), "")

    def test_a_top_level_max_tokens_stop_is_a_failure_that_keeps_its_cost(self):
        result = self.success(stop_reason="max_tokens")
        self.assertEqual(result, {"ok": False, "error": "max-tokens", "cost_usd": 0.04, "models": ["claude-x"]})

    def test_a_max_tokens_stop_inside_the_result_object_is_a_failure(self):
        result = self.success(result={"text": "Five", "stop_reason": "max_tokens"})
        self.assertFalse(result["ok"])
        self.assertEqual((result["error"], result["cost_usd"]), ("max-tokens", 0.04))

    def test_a_written_out_tool_call_is_a_failure_that_keeps_its_cost(self):
        for text in ('Let me look.\n<invoke name="Glob">\n<parameter name="pattern">*.py</parameter>\n</invoke>',
                     "<function_calls>\n<invoke>", "Checking. <function_calls>"):
            with self.subTest(text=text[:20]):
                result = self.success(result=text)
                self.assertFalse(result["ok"])
                self.assertEqual((result["error"], result["cost_usd"]), ("fake-tool-call", 0.04))

    def test_an_empty_or_missing_result_is_a_failure_that_keeps_its_cost(self):
        for result in ("", "  \n", None):
            with self.subTest(result=result):
                self.assertEqual(self.success(result=result),
                                 {"ok": False, "error": "empty-result", "cost_usd": 0.04, "models": ["claude-x"]})
        data = {"total_cost_usd": 0.04, "is_error": False, "subtype": "success"}
        self.assertEqual(common.parse_claude_output(0, json.dumps(data), "")["error"], "empty-result")

    def test_a_result_that_is_not_a_string_is_a_failure_that_keeps_its_cost(self):
        for result in ({"text": "Five"}, ["Five"], 5, True):
            with self.subTest(result=result):
                self.assertEqual(self.success(result=result),
                                 {"ok": False, "error": "bad-result", "cost_usd": 0.04, "models": ["claude-x"]})

    def test_duration_ms_is_kept_on_success_and_failure_when_present(self):
        self.assertEqual(self.success(duration_ms=4321)["duration_ms"], 4321)
        self.assertEqual(self.success(duration_ms=900, result="")["duration_ms"], 900)
        error = json.dumps({"result": "", "is_error": True, "subtype": "error_max_budget_usd", "duration_ms": 77})
        self.assertEqual(common.parse_claude_output(1, error, "")["duration_ms"], 77)
        self.assertNotIn("duration_ms", self.success())

    def test_a_normal_result_stays_ok(self):
        for extra in ({}, {"stop_reason": "end_turn"}, {"stop_reason": None}):
            with self.subTest(extra=extra):
                self.assertEqual(self.success(**extra),
                                 {"ok": True, "text": "Five", "cost_usd": 0.04, "models": ["claude-x"]})

    def test_an_error_with_no_cost_field_reports_no_cost(self):
        out = json.dumps({"result": "", "is_error": True, "subtype": "error_during_execution"})
        self.assertIsNone(common.parse_claude_output(1, out, "")["cost_usd"])


class RunClaudeTest(unittest.TestCase):
    def test_isolates_the_call_and_sends_text_through_a_file_and_stdin(self):
        seen = {}

        def runner(argv, **kwargs):
            seen["argv"] = argv
            seen["input"] = kwargs["input"]
            seen["cwd"] = kwargs["cwd"]
            seen["env"] = kwargs["env"]
            index = argv.index("--append-system-prompt-file")
            with open(argv[index + 1], encoding="utf-8") as handle:
                seen["system"] = handle.read()
            out = json.dumps({"result": "ok", "total_cost_usd": 0.0, "is_error": False,
                              "subtype": "success", "modelUsage": {}})
            return subprocess.CompletedProcess(argv, 0, out, "")

        os.environ["CLAUDE_EFFORT"] = "high"
        self.addCleanup(os.environ.pop, "CLAUDE_EFFORT", None)
        result = common.run_claude('say "hi" | now', "rule | one\nrule two", "claude-x", 1.5, runner=runner)
        self.assertTrue(result["ok"])
        argv = seen["argv"]
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--model") + 1], "claude-x")
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "1.5000")
        self.assertIn("--no-session-persistence", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("--mcp-config", argv)
        self.assertNotIn("--effort", argv)
        self.assertNotIn("CLAUDE_EFFORT", seen["env"])
        self.assertNotIn('say "hi" | now', argv)
        self.assertEqual(seen["input"], 'say "hi" | now')
        self.assertEqual(seen["system"], "rule | one\nrule two\n\n" + common.NO_TOOLS_NOTE)
        self.assertNotEqual(os.path.abspath(seen["cwd"]), os.path.abspath(os.getcwd()))

    def test_effort_flag_only_when_given(self):
        seen = []

        def runner(argv, **kwargs):
            seen.append(argv)
            out = json.dumps({"result": "ok", "total_cost_usd": 0.0, "is_error": False, "subtype": "success"})
            return subprocess.CompletedProcess(argv, 0, out, "")

        common.run_claude("p", "", "m", 1.0, effort="low", runner=runner)
        common.run_claude("p", "", "m", 1.0, effort=None, runner=runner)
        self.assertEqual(seen[0][seen[0].index("--effort") + 1], "low")
        self.assertNotIn("--effort", seen[1])

    def system_file(self, system_text):
        seen = {}

        def runner(argv, **kwargs):
            seen["argv"] = argv
            with open(argv[argv.index("--append-system-prompt-file") + 1], encoding="utf-8") as handle:
                seen["system"] = handle.read()
            out = json.dumps({"result": "ok", "total_cost_usd": 0.0, "is_error": False, "subtype": "success"})
            return subprocess.CompletedProcess(argv, 0, out, "")

        self.assertTrue(common.run_claude("p", system_text, "m", 1.0, runner=runner)["ok"])
        return seen

    def test_no_system_text_still_sends_the_no_tools_note_alone(self):
        seen = self.system_file("")
        self.assertIn("--append-system-prompt-file", seen["argv"])
        self.assertEqual(seen["system"], common.NO_TOOLS_NOTE)

    def test_the_default_timeout_is_180_seconds_and_the_env_sets_no_token_cap(self):
        seen = {}

        def runner(argv, **kwargs):
            seen.update(kwargs)
            out = json.dumps({"result": "ok", "total_cost_usd": 0.0, "is_error": False, "subtype": "success"})
            return subprocess.CompletedProcess(argv, 0, out, "")

        self.assertEqual(common.CALL_TIMEOUT_S, 180)
        self.assertFalse(hasattr(common, "MAX_OUTPUT_TOKENS"))
        common.run_claude("p", "", "m", 1.0, runner=runner)
        self.assertEqual(seen["timeout"], 180)
        self.assertNotIn("CLAUDE_CODE_MAX_OUTPUT_TOKENS", seen["env"])

    def test_condition_text_is_followed_by_the_no_tools_note(self):
        self.assertEqual(self.system_file("Rule one.")["system"], "Rule one.\n\n" + common.NO_TOOLS_NOTE)

    def test_the_no_tools_note_does_not_ask_for_plain_text(self):
        self.assertEqual(common.NO_TOOLS_NOTE,
                         "You have no tools in this conversation. Do not call tools or write out tool calls. "
                         "Answer from the information in the user's message.")
        self.assertEqual(common.system_text_for("x"), "x\n\n" + common.NO_TOOLS_NOTE)
        self.assertEqual(common.system_text_for(""), common.NO_TOOLS_NOTE)

    def test_timeout_is_a_failed_row(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1)

        self.assertEqual(common.run_claude("p", "", "m", 1.0, runner=runner),
                         {"ok": False, "error": "timeout", "cost_usd": None})


class AttemptCostTest(unittest.TestCase):
    def test_the_per_call_cap_is_fifty_cents(self):
        self.assertEqual(common.PER_CALL_CAP_USD, 0.50)
        self.assertEqual(common.call_budget(5.0, 1.0), 0.50)
        self.assertAlmostEqual(common.call_budget(1.0, 0.8), 0.2)

    def test_a_timeout_or_a_failure_with_no_cost_counts_as_the_cap(self):
        cap = common.PER_CALL_CAP_USD
        self.assertEqual(common.attempt_cost({"ok": False, "error": "timeout", "cost_usd": None}), (cap, True))
        self.assertEqual(common.attempt_cost({"ok": False, "error": "timeout", "cost_usd": 0.0}), (cap, True))
        self.assertEqual(common.attempt_cost({"ok": False, "error": "exit 1: boom", "cost_usd": None}), (cap, True))
        self.assertEqual(common.attempt_cost({"ok": False, "error": "boom"}), (cap, True))
        self.assertEqual(common.attempt_cost({"ok": False, "error": "error_max_budget_usd", "cost_usd": 0.2}),
                         (0.2, False))
        self.assertEqual(common.attempt_cost({"ok": True, "text": "x", "cost_usd": 0.01}), (0.01, False))


class SpentTest(unittest.TestCase):
    def test_sums_generation_and_judge_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            common.append_jsonl(Path(tmp) / "responses.jsonl", {"cost_usd": 0.25})
            common.append_jsonl(Path(tmp) / "scores.jsonl", {"cost_usd": 0.5})
            common.append_jsonl(Path(tmp) / "scores.jsonl", {"ok": False})
            self.assertAlmostEqual(common.spent(tmp), 0.75)


class LoadCasesOnlyTest(unittest.TestCase):
    def test_no_variable_loads_every_case(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(common.ONLY_ENV, None)
            every = common.read_jsonl(common.EVALS_DIR / "cases.jsonl")
            self.assertEqual(len(common.load_cases()), len(every))

    def test_variable_keeps_the_named_cases_in_file_order(self):
        with mock.patch.dict(os.environ, {common.ONLY_ENV: "toast, direct-answer"}):
            self.assertEqual([case["id"] for case in common.load_cases()], ["direct-answer", "toast"])

    def test_unknown_case_id_raises(self):
        with mock.patch.dict(os.environ, {common.ONLY_ENV: "direct-answer,no-such-case"}):
            with self.assertRaisesRegex(ValueError, "no-such-case"):
                common.load_cases()


class LoadCasesNoIdsTest(unittest.TestCase):
    def test_value_with_no_case_ids_raises(self):
        with mock.patch.dict(os.environ, {common.ONLY_ENV: ","}):
            with self.assertRaisesRegex(ValueError, common.ONLY_ENV):
                common.load_cases()

    def test_whitespace_only_value_loads_every_case(self):
        with mock.patch.dict(os.environ, {common.ONLY_ENV: "  "}):
            every = common.read_jsonl(common.EVALS_DIR / "cases.jsonl")
            self.assertEqual(len(common.load_cases()), len(every))


if __name__ == "__main__":
    unittest.main()
