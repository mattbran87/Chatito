"""Stage 4: Jev nouls for each response, per docs/jev-contract.md. See README.md.

Sends nothing unless the contract client's feature_consent says
"simple_english_eval" is on (an opt-in in ~/.claude/jev-user.json, no opt-out,
and no "allowed": false in the repository file) and TYPESAFE_API_KEY is set.
Every failure fails open: the row stores the reason, and the other stages
still run.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import common

FEATURE = "simple_english_eval"
CAP = 4000
STOP_AFTER = 3
STOP_REASONS = {"timeout", "network", "http-401", "http-403", "http-429", "http-529"}
CLIENT_PATH = common.EVALS_DIR / "jev_client.py"


def load_client(path=CLIENT_PATH):
    """The contract client: a byte-for-byte copy of the session-tools client, beside this file."""
    spec = importlib.util.spec_from_file_location("simple_english_eval_jev_client", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_questions(path=None):
    with open(path or common.EVALS_DIR / "jev_questions.json", encoding="utf-8") as handle:
        return json.load(handle)


def applies(question, case):
    return case["id"] in question.get("cases", []) or case["kind"] in question.get("kinds", [])


def request_questions(questions, case):
    return {key: {"type": "noul", "instructions": spec["question"]}
            for key, spec in questions.items() if applies(spec, case)}


def row_hash(case, text, asked):
    """A hash of everything one call is built from: the response, the prompt, and the questions asked."""
    return common.input_hash(text + "\x00" + case["prompt"], json.dumps(asked, sort_keys=True))


# A path segment ends at a separator or at the end of the name: not before a word character,
# a hyphen, or a dot that starts an extension. So "jdoe." at the end of a sentence still matches.
_SEGMENT_END = r"(?![\w-]|\.\w)"
# A shorter user name, such as "dev", is too likely to be an ordinary path segment, as in /dev/null.
MIN_MASKED_NAME = 4


def mask_home(text, home=None):
    """Hide the local home folder and user name in text bound for Jev.

    The home folder, in either slash style, doubled backslashes, and any case,
    becomes "~". The bare user name, as a whole segment inside some other path,
    becomes "[user]", but only when it has MIN_MASKED_NAME or more characters. This is extra masking local to the eval. It runs before the
    contract client's redact() and changes nothing in the client or the contract.
    """
    home = str(home or Path.home())
    parts = [part for part in re.split(r"[\\/]+", home) if part]
    if not parts:
        return text
    lead = r"[\\/]+" if home[:1] in "\\/" else ""
    text = re.sub(lead + r"[\\/]+".join(map(re.escape, parts)) + _SEGMENT_END, "~", text, flags=re.I)
    name = parts[-1]
    if len(name) < MIN_MASKED_NAME:
        return text
    return re.sub(r"(?<=[\\/])" + re.escape(name) + _SEGMENT_END, "[user]", text, flags=re.I)


def new_summary():
    return {"sent": 0, "reason": None, "failed": {}, "stopped": None}


def jev_run(cases, responses, questions, out_path, repo_root, env, client=None, sender_factory=None, *, cfg,
            summary=None, home=None):
    """Ask Jev about each finished response once. An out-of-date response is skipped, and nothing is written for it.

    Returns {sent, reason, failed, stopped}. When `summary` is given, it is that dict,
    kept up to date as each call goes out, so a caller can still read it after an exception.
    """
    summary = new_summary() if summary is None else summary
    responses = common.split_out_of_date(responses, cases, cfg)[0]
    client = client or load_client()
    by_case = {case["id"]: case for case in cases}
    previous = common.latest(common.read_jsonl(out_path))
    failed = summary["failed"]
    streak_reason, streak = None, 0
    key = (env.get(client.KEY_VAR) or "").strip()
    try:
        consent = client.feature_consent(FEATURE, str(repo_root))
    except Exception:
        # A consent check that breaks never turns the stage on, and each row
        # records why instead of the run ending in a traceback.
        consent = {"on": False, "reason": "consent check failed", "block": {}}
    if not consent["on"]:
        summary["reason"] = consent["reason"]
    elif not key:
        summary["reason"] = "no-key"
    reason = summary["reason"]
    send = (sender_factory or client.make_sender)(key) if reason is None else None
    for row_key, row in sorted(common.latest(responses).items()):
        case = by_case.get(row["case_id"])
        if not row.get("ok") or case is None:
            continue
        asked = request_questions(questions, case)
        if not asked:
            continue
        text_hash = row_hash(case, row["text"], asked)
        old = previous.get(row_key)
        if old and old.get("ok") and old.get("text_hash") == text_hash:
            continue
        out = {"case_id": row_key[0], "trial": row_key[1], "condition": row_key[2], "text_hash": text_hash}
        if reason is not None:
            common.append_jsonl(out_path, dict(out, ok=False, reason=reason))
            continue
        state = {"prompt": client.redact(mask_home(case["prompt"], home), key)[:CAP],
                 "response": client.redact(mask_home(row["text"], home), key)[:CAP]}
        summary["sent"] += 1  # counted before the call, so the closing line names data that may have gone out
        result = client.ask(state, asked, key, send)
        if result["ok"]:
            out.update(ok=True, answers={q: result["answers"][q]["noul"] for q in asked})
            streak_reason, streak = None, 0
        else:
            out.update(ok=False, reason=result["reason"])
            if result.get("detail"):
                out["detail"] = result["detail"]
            failed[result["reason"]] = failed.get(result["reason"], 0) + 1
            if result["reason"] in STOP_REASONS and result["reason"] == streak_reason:
                streak += 1
            else:
                streak_reason, streak = (result["reason"], 1) if result["reason"] in STOP_REASONS else (None, 0)
        common.append_jsonl(out_path, out)
        if streak >= STOP_AFTER:
            summary["stopped"] = streak_reason
            break
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    folder = common.run_dir(args.run_id)
    cases, cfg = common.load_cases(), common.load_conditions()
    responses = common.read_jsonl(folder / "responses.jsonl")
    out_of_date = common.split_out_of_date(responses, cases, cfg)[1]
    if out_of_date:
        print("jev: skipped %d out-of-date responses; rerun generate.py" % len(out_of_date))
    summary = new_summary()
    try:
        summary = jev_run(cases, responses, load_questions(), folder / "jev.jsonl", common.REPO_ROOT, os.environ,
                          cfg=cfg, summary=summary)
    finally:
        # An exception still re-raises, but only after the closing line.
        print_summary(summary)
    return 0


def print_summary(summary):
    if summary["failed"]:
        print("jev: %d calls failed (%s); the other stages are unaffected."
              % (sum(summary["failed"].values()),
                 ", ".join("%s: %d" % (name, count) for name, count in sorted(summary["failed"].items()))))
    if summary["stopped"]:
        print("jev: stopped after %d consecutive %s failures; rerun to resume." % (STOP_AFTER, summary["stopped"]))
    # The contract: a run that sends data ends with one line naming what went out.
    if summary["reason"]:
        print("jev: sent nothing to api.typesafe.ai (%s)." % summary["reason"])
    elif summary["sent"] == 0:
        print("jev: nothing new to send to api.typesafe.ai.")
    else:
        print("jev: sent %d responses to api.typesafe.ai: each case prompt and response, cut to %d characters and redacted."
              % (summary["sent"], CAP))


if __name__ == "__main__":
    sys.exit(main())
