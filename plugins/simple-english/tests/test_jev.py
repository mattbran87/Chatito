import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import common
import jev

QUESTIONS = {
    "filler": {"question": "Filler?", "kinds": ["chat", "doc"], "bad_when": "yes", "gating": False, "threshold": 0.5},
    "invents_cause": {"question": "Invents?", "cases": ["diag"], "bad_when": "yes", "gating": False, "threshold": 0.5},
    "drops_warning": {"question": "Drops?", "kinds": ["doc"], "bad_when": "yes", "gating": False, "threshold": 0.5},
}
CASES = [{"id": "diag", "kind": "chat", "prompt": "P" * 5000}, {"id": "note", "kind": "commit", "prompt": "Q"}]
CFG = {"model": "m", "conditions": {"baseline": None, "skill": "skills/simple-english/SKILL.md"}}


def stamp(rows, cases=CASES, cfg=CFG):
    """Give each row the input_hash generate.py would store under cfg."""
    by_case = {case["id"]: case for case in cases}
    return [dict(row, input_hash=common.response_hash(by_case[row["case_id"]], cfg, row["condition"])) for row in rows]


RESPONSES = stamp([{"case_id": "diag", "trial": 1, "condition": "skill", "ok": True, "text": "R" * 5000},
                   {"case_id": "note", "trial": 1, "condition": "skill", "ok": True, "text": "S"},
                   {"case_id": "diag", "trial": 1, "condition": "baseline", "ok": False, "error": "boom"}])


# Variables that point git at a repository. A git hook that runs these tests
# can set them, and git would then read the developer's own repository. This
# copies GIT_REPOSITORY_VARS in plugins/session-tools/tests/digest_helpers.py,
# because a plugin cannot import from another plugin.
GIT_REPOSITORY_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


class IsolatedHome(unittest.TestCase):
    """Each test gets an empty home folder, so the real ~/.claude/jev-user.json plays no part.

    feature_consent runs git in the repo_root folder. The git variables are
    removed and the temporary folder is a ceiling, so git never finds the
    developer's own repository.
    """

    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.home = home.name
        patch = mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home,
                                             "GIT_CEILING_DIRECTORIES": tempfile.gettempdir()})
        patch.start()
        self.addCleanup(patch.stop)
        for name in GIT_REPOSITORY_VARS:
            os.environ.pop(name, None)

    def opted_in(self, folder):
        """Opt in through the user file, and return folder for use as repo_root."""
        claude = Path(self.home) / ".claude"
        claude.mkdir(exist_ok=True)
        (claude / "jev-user.json").write_text(json.dumps({"simple_english_eval": {"enabled": True}}), encoding="utf-8")
        return folder

    def repo_file(self, folder, data):
        (Path(folder) / ".claude").mkdir(exist_ok=True)
        (Path(folder) / ".claude" / "jev.json").write_text(json.dumps(data), encoding="utf-8")


class Sender:
    def __init__(self, status=200):
        self.bodies = []
        self.status = status

    def factory(self, key):
        self.key = key
        return self.send

    def send(self, body):
        self.bodies.append(body)
        if self.status != 200:
            return self.status, "server error"
        answers = {q: {"type": "noul", "noul": 0.8} for q in body["questions"]}
        return 200, json.dumps({"answers": answers})


class ClientTest(unittest.TestCase):
    def test_the_vendored_client_resolves(self):
        self.assertEqual(jev.CLIENT_PATH, common.EVALS_DIR / "jev_client.py")
        self.assertTrue(jev.CLIENT_PATH.is_file(), jev.CLIENT_PATH)
        client = jev.load_client()
        self.assertTrue(callable(client.ask))
        self.assertEqual(client.KEY_VAR, "TYPESAFE_API_KEY")
        self.assertTrue(callable(client.feature_consent))
        self.assertFalse(hasattr(client, "feature_config"))
        self.assertTrue(callable(client.make_sender))
        self.assertTrue(callable(client.redact))


class MaskHomeTest(IsolatedHome):
    HOME = r"C:\Users\Jdoe"

    def test_the_home_folder_becomes_a_tilde_in_both_slash_styles_and_any_case(self):
        text = (r"Open C:\Users\Jdoe\repo\a.py, then c:/users/jdoe/repo/b.py, then "
                "C:\\\\Users\\\\JDOE\\\\c.py.")
        self.assertEqual(jev.mask_home(text, self.HOME), r"Open ~\repo\a.py, then ~/repo/b.py, then ~\\c.py.")

    def test_the_user_name_inside_another_path_becomes_user(self):
        text = r"See D:\Users\jdoe\notes, /home/jdoe/x, and /mnt/c/Users/Jdoe."
        self.assertEqual(jev.mask_home(text, self.HOME),
                         r"See D:\Users\[user]\notes, /home/[user]/x, and /mnt/c/Users/[user].")

    def test_a_user_name_under_4_characters_is_not_masked_in_other_paths(self):
        text = "Run `ls /dev/null` and see /srv/dev/app."
        self.assertEqual(jev.mask_home(text, "/home/dev"), text)
        self.assertEqual(jev.mask_home("Open /home/dev/x and /srv/dev/app.", "/home/dev"),
                         "Open ~/x and /srv/dev/app.")

    def test_the_user_name_outside_a_path_stays(self):
        text = "Jdoe wrote it. /home/jdoesmith/x stays. C:\\Users\\jdoe.bak stays."
        self.assertEqual(jev.mask_home(text, self.HOME), text)

    def test_the_prompt_and_the_response_are_masked_before_they_are_sent(self):
        cases = [dict(CASES[0], prompt=r"Read C:\Users\Jdoe\app.log")]
        responses = stamp([dict(RESPONSES[0], text="The log at c:/users/jdoe/app.log and /home/jdoe/y")], cases)
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            jev.jev_run(cases, responses, QUESTIONS, Path(tmp) / "j.jsonl", self.opted_in(tmp),
                        {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=sender.factory, home=self.HOME)
        state = sender.bodies[0]["state"]
        self.assertEqual(state["prompt"], r"Read ~\app.log")
        self.assertEqual(state["response"], "The log at ~/app.log and /home/[user]/y")


class QuestionsTest(unittest.TestCase):
    def test_questions_apply_by_kind_or_case(self):
        self.assertEqual(set(jev.request_questions(QUESTIONS, CASES[0])), {"filler", "invents_cause"})
        self.assertEqual(jev.request_questions(QUESTIONS, CASES[1]), {})
        self.assertEqual(jev.request_questions(QUESTIONS, CASES[0])["filler"],
                         {"type": "noul", "instructions": "Filler?"})


class JevRunTest(IsolatedHome):
    def test_not_opted_in_sends_nothing(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "jev.jsonl"
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, out, tmp, {"TYPESAFE_API_KEY": "k"},
                                  cfg=CFG, sender_factory=sender.factory)
            rows = common.read_jsonl(out)
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary, {"sent": 0, "reason": "not opted in", "failed": {}, "stopped": None})
        self.assertEqual([r["reason"] for r in rows], ["not opted in"])
        self.assertEqual(rows[0]["text_hash"],
                         jev.row_hash(CASES[0], "R" * 5000, jev.request_questions(QUESTIONS, CASES[0])))

    def test_an_old_repository_opt_in_no_longer_counts(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            self.repo_file(tmp, {"simple_english_eval": {"enabled": True}})
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, Path(tmp) / "j.jsonl", tmp, {"TYPESAFE_API_KEY": "k"},
                                  cfg=CFG, sender_factory=sender.factory)
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary["reason"], "not opted in")

    def test_a_failed_consent_check_reads_as_off(self):
        sender = Sender()
        client = jev.load_client()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(client, "feature_consent", side_effect=RuntimeError("boom")):
            out = Path(tmp) / "j.jsonl"
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), {"TYPESAFE_API_KEY": "k"},
                                  client=client, cfg=CFG, sender_factory=sender.factory)
            rows = common.read_jsonl(out)
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary["reason"], "consent check failed")
        self.assertEqual([r["reason"] for r in rows], ["consent check failed"])

    def test_a_repository_that_forbids_sends_nothing(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            self.repo_file(tmp, {"simple_english_eval": {"allowed": False}})
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, Path(tmp) / "j.jsonl", self.opted_in(tmp),
                                  {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=sender.factory)
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary["reason"], "repository forbids")

    def test_no_key_sends_nothing(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "j.jsonl"
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), {},
                                  cfg=CFG, sender_factory=sender.factory)
            rows = common.read_jsonl(out)
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary["reason"], "no-key")
        self.assertEqual([(r["ok"], r["reason"]) for r in rows], [(False, "no-key")])
        self.assertIn("text_hash", rows[0])

    def test_sends_capped_text_and_stores_nouls(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "jev.jsonl"
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), {"TYPESAFE_API_KEY": "k"},
                                  cfg=CFG, sender_factory=sender.factory)
            rows = common.read_jsonl(out)
        self.assertEqual(summary, {"sent": 1, "reason": None, "failed": {}, "stopped": None})
        state = sender.bodies[0]["state"]
        self.assertEqual(len(state["prompt"]), 4000)
        self.assertEqual(len(state["response"]), 4000)
        self.assertEqual(rows, [{"case_id": "diag", "trial": 1, "condition": "skill", "ok": True,
                                 "text_hash": jev.row_hash(CASES[0], "R" * 5000,
                                                           jev.request_questions(QUESTIONS, CASES[0])),
                                 "answers": {"filler": 0.8, "invents_cause": 0.8}}])

    def test_a_failed_call_stores_the_reason_and_a_rerun_retries_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "jev.jsonl"
            repo = self.opted_in(tmp)
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"},
                        cfg=CFG, sender_factory=Sender(status=500).factory)
            failed = common.read_jsonl(out)[0]
            self.assertEqual(failed["reason"], "http-500")
            self.assertEqual(failed["detail"], "server error")
            self.assertIn("text_hash", failed)
            again = Sender()
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=again.factory)
            self.assertEqual(len(again.bodies), 1)
            third = Sender()
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=third.factory)
            self.assertEqual(third.bodies, [])

    def test_a_changed_response_text_is_sent_to_jev_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "jev.jsonl"
            repo = self.opted_in(tmp)
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"},
                        cfg=CFG, sender_factory=Sender().factory)
            changed = [dict(RESPONSES[0], text="T" * 100)] + RESPONSES[1:]
            again = Sender()
            summary = jev.jev_run(CASES, changed, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"},
                                  cfg=CFG, sender_factory=again.factory)
            self.assertEqual(summary["sent"], 1)
            self.assertEqual(again.bodies[0]["state"]["response"], "T" * 100)
            third = Sender()
            jev.jev_run(CASES, changed, QUESTIONS, out, repo, {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=third.factory)
            self.assertEqual(third.bodies, [])

    def test_a_changed_or_added_question_is_asked_again_and_same_inputs_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "jev.jsonl"
            repo = self.opted_in(tmp)
            env = {"TYPESAFE_API_KEY": "k"}
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, env, cfg=CFG, sender_factory=Sender().factory)
            same = Sender()
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, repo, env, cfg=CFG, sender_factory=same.factory)
            self.assertEqual(same.bodies, [])
            reworded = dict(QUESTIONS, filler=dict(QUESTIONS["filler"], question="Filler, reworded?"))
            second = Sender()
            jev.jev_run(CASES, RESPONSES, reworded, out, repo, env, cfg=CFG, sender_factory=second.factory)
            self.assertEqual(len(second.bodies), 1)
            added = dict(reworded, extra={"question": "Extra?", "kinds": ["chat"]})
            third = Sender()
            jev.jev_run(CASES, RESPONSES, added, out, repo, env, cfg=CFG, sender_factory=third.factory)
            self.assertEqual(len(third.bodies), 1)
            self.assertIn("extra", third.bodies[0]["questions"])

    def test_a_rerun_after_not_opted_in_rows_sends_them(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bare:
            out = Path(tmp) / "jev.jsonl"
            env = {"TYPESAFE_API_KEY": "k"}
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, bare, env, cfg=CFG, sender_factory=Sender().factory)
            sender = Sender()
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), env, cfg=CFG, sender_factory=sender.factory)
        self.assertEqual(len(sender.bodies), 1)

    def test_secrets_are_redacted_before_the_cut(self):
        token = "sk-" + "a1B2c3D4e5F6g7H8i9J0"
        responses = [dict(RESPONSES[0], text="x" * 3990 + token + "y" * 100),
                     dict(RESPONSES[1], text="password = hunter2")]
        cases = [CASES[0], dict(CASES[1], kind="chat")]
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            jev.jev_run(cases, responses, QUESTIONS, Path(tmp) / "j.jsonl", self.opted_in(tmp),
                        {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=sender.factory)
        sent = [body["state"]["response"] for body in sender.bodies]
        self.assertEqual(len(sent), 2)
        long_sent = [r for r in sent if r.startswith("xxx")][0]
        self.assertNotIn("sk-", long_sent)
        self.assertIn("[redacted]", [r for r in sent if r.startswith("password")][0])
        self.assertNotIn("hunter2", "".join(sent))

    def test_failures_are_counted_by_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, Path(tmp) / "j.jsonl", self.opted_in(tmp),
                                  {"TYPESAFE_API_KEY": "k"}, cfg=CFG, sender_factory=Sender(status=500).factory)
        self.assertEqual(summary, {"sent": 1, "reason": None, "failed": {"http-500": 1}, "stopped": None})

    def test_three_failures_in_a_row_stop_the_run_and_a_rerun_resumes(self):
        cases = [{"id": "c%d" % n, "kind": "chat", "prompt": "p"} for n in range(5)]
        responses = stamp([{"case_id": c["id"], "trial": 1, "condition": "skill", "ok": True, "text": "t"} for c in cases],
                          cases)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "j.jsonl"
            repo = self.opted_in(tmp)
            env = {"TYPESAFE_API_KEY": "k"}
            denied = Sender(status=401)
            summary = jev.jev_run(cases, responses, QUESTIONS, out, repo, env, cfg=CFG, sender_factory=denied.factory)
            self.assertEqual(len(denied.bodies), 3)
            self.assertEqual(summary["stopped"], "http-401")
            self.assertEqual(summary["failed"], {"http-401": 3})
            self.assertEqual(len(common.read_jsonl(out)), 3)
            resumed = Sender()
            jev.jev_run(cases, responses, QUESTIONS, out, repo, env, cfg=CFG, sender_factory=resumed.factory)
            self.assertEqual(len(resumed.bodies), 5)

    def test_an_out_of_date_response_is_not_sent_and_writes_nothing(self):
        sender = Sender()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "j.jsonl"
            summary = jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), {"TYPESAFE_API_KEY": "k"},
                                  cfg=dict(CFG, model="m2"), sender_factory=sender.factory)
            self.assertFalse(out.exists())
        self.assertEqual(sender.bodies, [])
        self.assertEqual(summary["sent"], 0)

    def test_an_extra_answer_key_in_the_reply_is_ignored(self):
        class Extra(Sender):
            def send(self, body):
                self.bodies.append(body)
                answers = {q: {"type": "noul", "noul": 0.2} for q in list(body["questions"]) + ["surprise"]}
                return 200, json.dumps({"answers": answers})

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "j.jsonl"
            jev.jev_run(CASES, RESPONSES, QUESTIONS, out, self.opted_in(tmp), {"TYPESAFE_API_KEY": "k"},
                        cfg=CFG, sender_factory=Extra().factory)
            rows = common.read_jsonl(out)
        self.assertEqual(rows[0]["answers"], {"filler": 0.2, "invents_cause": 0.2})


class MainTest(unittest.TestCase):
    def run_main(self, summary):
        out = io.StringIO()
        with mock.patch.object(jev, "jev_run", return_value=summary), \
                mock.patch.object(jev.common, "run_dir", return_value=Path("nowhere")), \
                mock.patch.object(jev.common, "load_cases", return_value=[]), \
                mock.patch.object(jev.common, "read_jsonl", return_value=[]), \
                mock.patch.object(jev, "load_questions", return_value={}), \
                contextlib.redirect_stdout(out):
            code = jev.main(["--run-id", "r"])
        self.assertEqual(code, 0)
        return out.getvalue().splitlines()

    def test_failures_and_a_stop_are_reported_in_one_line_each(self):
        lines = self.run_main({"sent": 119, "reason": None, "failed": {"timeout": 2, "http-401": 117}, "stopped": None})
        self.assertEqual(lines[0], "jev: 119 calls failed (http-401: 117, timeout: 2); the other stages are unaffected.")
        self.assertIn("sent 119 responses", lines[-1])
        lines = self.run_main({"sent": 3, "reason": None, "failed": {"http-401": 3}, "stopped": "http-401"})
        self.assertEqual(lines[:2], ["jev: 3 calls failed (http-401: 3); the other stages are unaffected.",
                                     "jev: stopped after 3 consecutive http-401 failures; rerun to resume."])
        self.assertIn("sent 3 responses", lines[-1])
        self.assertEqual(len(lines), 3)

    def test_the_disclosure_line_prints_last_when_the_send_loop_raises(self):
        def broken(*args, summary=None, **kwargs):
            summary["sent"] = 2
            raise RuntimeError("disk full")

        out = io.StringIO()
        with mock.patch.object(jev, "jev_run", side_effect=broken), \
                mock.patch.object(jev.common, "run_dir", return_value=Path("nowhere")), \
                mock.patch.object(jev.common, "load_cases", return_value=[]), \
                mock.patch.object(jev.common, "read_jsonl", return_value=[]), \
                mock.patch.object(jev, "load_questions", return_value={}), \
                contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                jev.main(["--run-id", "r"])
        lines = out.getvalue().splitlines()
        self.assertIn("sent 2 responses", lines[-1])

    def test_nothing_new_and_a_clean_send_have_their_own_wording(self):
        self.assertEqual(self.run_main({"sent": 0, "reason": None, "failed": {}, "stopped": None}),
                         ["jev: nothing new to send to api.typesafe.ai."])
        lines = self.run_main({"sent": 4, "reason": None, "failed": {}, "stopped": None})
        self.assertEqual(len(lines), 1)
        self.assertIn("sent 4 responses", lines[0])
        lines = self.run_main({"sent": 0, "reason": "no-key", "failed": {}, "stopped": None})
        self.assertEqual(lines, ["jev: sent nothing to api.typesafe.ai (no-key)."])


if __name__ == "__main__":
    unittest.main()
