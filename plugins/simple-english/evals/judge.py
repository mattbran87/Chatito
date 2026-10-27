"""Stage 3: blind side-by-side scores from a Claude judge. See README.md."""

import argparse
import hashlib
import json
import re
import sys

import common

BEGIN, END = "<!-- judge:begin -->", "<!-- judge:end -->"
DIMENSIONS = ("correctness", "fact_retention", "readability", "concision", "safety")
LABELS = "ABCDEFGH"


def judge_block(rubric):
    start, end = rubric.find(BEGIN), rubric.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("rubric.md has no judge block between %s and %s" % (BEGIN, END))
    return rubric[start + len(BEGIN):end].strip()


def rubric_hash(rubric):
    return hashlib.sha256(judge_block(rubric).encode("utf-8")).hexdigest()[:16]


def group_hash(cfg, prompt):
    """Hash of every judge input: model, effort, the system text run_claude sends (the no-tools note
    alone, because judge passes none), and the built prompt (block, task, criteria, labels, texts)."""
    joined = (cfg["model"] + "\x00" + str(cfg.get("effort")) + "\x00" + common.system_text_for("") + "\x00"
              + prompt)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def assign_labels(case_id, trial, conditions):
    """Rotate a fixed order by a case offset plus the trial: blind, deterministic, and balanced across trials."""
    base = sorted(conditions)
    start = (int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16) + trial) % len(base)
    order = base[start:] + base[:start]
    return {name: LABELS[index] for index, name in enumerate(order)}


def build_prompt(case, labeled, block):
    parts = [block, "", "## Task given to every response", "", case["prompt"], "",
             "## What a good response does", ""]
    parts += ["- " + criterion for criterion in case["criteria"]]
    for label in sorted(labeled):
        text = re.sub(r"<(?=/?response)", "&lt;", labeled[label], flags=re.I)
        parts += ["", '<response label="%s">' % label, text, "</response>"]
    parts += ["", "Return only a JSON object, with no code fence. Give one key per response, using the label "
              "values (%s). Each value is an object with an integer from 1 to 5 for each of %s, "
              "a boolean \"blocker\", and a one-line \"note\"."
              % (", ".join(sorted(labeled)), ", ".join(DIMENSIONS))]
    return "\n".join(parts)


def _find_object(text):
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            data, _end = decoder.raw_decode(text, index)
        except ValueError:
            data = None
        if isinstance(data, dict):
            return data
        index = text.find("{", index + 1)
    return None


def parse_scores(text, labels):
    raw = _find_object(text)
    if raw is None:
        return None
    data = {}
    for key, value in raw.items():
        key = str(key).strip()
        if key.lower().startswith("response "):
            key = key[len("response "):].strip()
        data.setdefault(key, value)
    out = {}
    for label in labels:
        entry = data.get(label)
        if not isinstance(entry, dict) or not isinstance(entry.get("blocker"), bool):
            return None
        scores = {}
        for dimension in DIMENSIONS:
            value = entry.get(dimension)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
                return None
            scores[dimension] = value
        out[label] = {"scores": scores, "blocker": entry["blocker"], "note": str(entry.get("note", ""))[:300]}
    return out


def _plan(cases, responses, cfg, rubric):
    """Every group in run order: (group, labels, prompt, hash), or (group, None, None, None) when a response is missing.
    An out-of-date response counts as missing, so its group gets no call and no current hash.
    judge_run and current_group_hashes both read this, so the hash cannot drift."""
    block = judge_block(rubric)
    names = list(cfg["conditions"])
    by_key = common.latest(common.split_out_of_date(responses, cases, cfg)[0])
    plan = []
    # Trials come from every response, so a group whose responses are all out of date is still listed as skipped.
    for trial in sorted({row["trial"] for row in common.latest(responses).values()}):
        for case in cases:
            rows = [by_key.get((case["id"], trial, name)) for name in names]
            if any(row is None or not row.get("ok") for row in rows):
                plan.append(((case["id"], trial), case, None, None, None))
                continue
            labels = assign_labels(case["id"], trial, names)
            prompt = build_prompt(case, {labels[n]: row["text"] for n, row in zip(names, rows)}, block)
            plan.append(((case["id"], trial), case, labels, prompt, group_hash(cfg, prompt)))
    return plan


def current_group_hashes(cases, responses, cfg, rubric):
    return {group: ghash for group, _case, _labels, _prompt, ghash in _plan(cases, responses, cfg, rubric)
            if ghash is not None}


def judge_run(cases, responses, cfg, rubric, out_path, budget_usd, spent_so_far=0.0, call=common.run_claude, retries=1):
    """Score each group that has no fresh score. Returns {made, failed, skipped, stopped, spent}.

    `stopped` is False, "budget" when the run cap is reached, or a reason after
    common.STOP_AFTER_FAILURES groups in a row end failed after their retries:
    "timeouts" when each of those groups ended on a timeout or an unpriced
    failure, else "failures". A group that is scored resets the count. A reply
    that is not valid score JSON is a failed attempt. After a "timeouts" or
    "failures" stop, `error` holds the last error.
    """
    digest = rubric_hash(rubric)
    names = list(cfg["conditions"])
    scored = common.latest(common.read_jsonl(out_path))
    spent = spent_so_far
    streak = common.FailureStreak()
    summary = {"made": 0, "failed": [], "skipped": [], "stopped": False}
    for group, case, labels, prompt, ghash in _plan(cases, responses, cfg, rubric):
        trial = group[1]
        if ghash is None:
            summary["skipped"].append(group)
            continue
        old = [scored.get((case["id"], trial, name)) for name in names]
        if all(r is not None and r.get("ok") and r.get("group_hash") == ghash for r in old):
            continue
        if budget_usd - spent < common.MIN_CALL_USD:
            summary["stopped"] = "budget"
            summary["spent"] = spent
            return summary
        cost, estimated, parsed, error, stop, models, duration = 0.0, False, None, None, False, [], None
        for _attempt in range(retries + 1):
            try:
                result = call(prompt, "", cfg["model"], common.call_budget(budget_usd, spent), effort=cfg.get("effort"))
            except Exception as exc:
                result = {"ok": False, "error": repr(exc)[:300], "cost_usd": None}
            attempt_usd, guessed = common.attempt_cost(result)
            cost += attempt_usd
            spent += attempt_usd
            estimated = estimated or guessed
            duration = common.slowest(duration, result)
            models = result.get("models", [])
            if result["ok"]:
                parsed = parse_scores(result["text"], sorted(labels.values()))
                if parsed is not None:
                    break
                error = "invalid-json"
            else:
                error = result.get("error")
            if budget_usd - spent < common.MIN_CALL_USD:
                stop = "budget"
                break
        for name in names:
            row = {"case_id": case["id"], "trial": trial, "condition": name, "label": labels[name],
                   "rubric_hash": digest, "group_hash": ghash, "model": cfg["model"],
                   "effort": cfg.get("effort"), "models": models, "cost_usd": cost / len(names)}
            if estimated:
                row["cost_estimated"] = True
            if duration is not None:
                row["duration_ms"] = duration  # the group's slowest attempt, as the CLI reported it
            if parsed is not None:
                entry = parsed[labels[name]]
                row.update(ok=True, scores=entry["scores"], blocker=entry["blocker"], note=entry["note"])
            else:
                row.update(ok=False, error=error)
            common.append_jsonl(out_path, row)
        stop = stop or streak.add(parsed is not None, guessed)
        if parsed is not None:
            summary["made"] += 1
        else:
            summary["failed"].append(group)
            if stop:
                summary["stopped"] = stop
                summary["spent"] = spent
                if stop != "budget":
                    summary["error"] = error
                return summary
    summary["spent"] = spent
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--budget-usd", type=float, required=True,
                        help="cap for the whole run, generation and judging together")
    args = parser.parse_args(argv)
    common.require_claude()
    folder = common.run_dir(args.run_id)
    rubric = (common.EVALS_DIR / "rubric.md").read_text(encoding="utf-8")
    summary = judge_run(common.load_cases(), common.read_jsonl(folder / "responses.jsonl"), common.load_conditions(),
                        rubric, folder / "scores.jsonl", args.budget_usd, spent_so_far=common.spent(folder))
    print("judge: %d groups scored, %d failed, %d skipped for a missing or out-of-date response"
          % (summary["made"], len(summary["failed"]), len(summary["skipped"])))
    for group in summary["skipped"]:
        print("judge: skipped %s trial %d" % group, file=sys.stderr)
    if summary["stopped"] in ("timeouts", "failures"):
        print(common.stop_message("judge", summary))
        return 1
    if summary["stopped"]:
        print("judge: the budget cap is reached, so the run is partial. Raise --budget-usd and rerun to resume.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
