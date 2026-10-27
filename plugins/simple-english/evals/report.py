"""Stage 5: the run report, and the gate between 2 conditions. See README.md.

Exit codes: 0 when no gate was asked or the gate passed, 1 when it failed,
2 when the 2 conditions cannot be compared.
"""

import argparse
import sys
from collections import Counter

import common
import jev
import judge
import lint

WEIGHTS = {"correctness": 0.30, "fact_retention": 0.20, "readability": 0.25, "concision": 0.15, "safety": 0.10}
TOLERANCE = 0.1
EPSILON = 1e-9
# Noise margins, set from 2 runs of near-identical style text on 2026-10-23: linter errors moved
# from 36 to 42, and Jev flagged a different single response in each run.
LINT_MARGIN = 0.10  # the candidate may have up to 10% more linter errors than the reference
JEV_MARGIN = 1  # the candidate may have 1 more bad Jev answer than the reference, per question


def weighted(scores):
    return sum(scores[dimension] * weight for dimension, weight in WEIGHTS.items())


def mean(values):
    return sum(values) / len(values) if values else None


def ok_rows(rows, condition):
    return [row for row in common.latest(rows).values() if row.get("ok") and row["condition"] == condition]


def fresh_scores(score_rows, current):
    """The latest score rows judged from the current inputs, and the count of stale rows left out.

    `current` is judge.current_group_hashes(). It has no entry for a group that is
    not complete, so a row is kept only when its own hash is set and matches.
    """
    kept, dropped = [], 0
    for row in common.latest(score_rows).values():
        ghash = row.get("group_hash")
        if ghash is not None and ghash == current.get((row["case_id"], row["trial"])):
            kept.append(row)
        else:
            dropped += 1
    return kept, dropped


def fresh_lint(lint_rows, responses):
    """The latest lint rows made from the current response text and linter, and the count left out."""
    latest_responses = common.latest(responses)
    kept, dropped = [], 0
    for key, row in common.latest(lint_rows).items():
        source = latest_responses.get(key)
        if source is not None and source.get("ok") and row.get("text_hash") == lint.text_hash(source["text"]):
            kept.append(row)
        else:
            dropped += 1
    return kept, dropped


def fresh_jev(jev_rows, cases, responses, questions):
    """The latest Jev rows made from the current response text and questions, and the count left out."""
    by_case = {case["id"]: case for case in cases}
    latest_responses = common.latest(responses)
    kept, dropped = [], 0
    for key, row in common.latest(jev_rows).items():
        source = latest_responses.get(key)
        case = by_case.get(row["case_id"])
        if source is not None and source.get("ok") and case is not None and row.get("text_hash") == jev.row_hash(
                case, source["text"], jev.request_questions(questions, case)):
            kept.append(row)
        else:
            dropped += 1
    return kept, dropped


def judge_summary(score_rows, condition):
    rows = ok_rows(score_rows, condition)
    out = {dimension: mean([row["scores"][dimension] for row in rows]) for dimension in WEIGHTS}
    out["weighted"] = mean([weighted(row["scores"]) for row in rows])
    out["blockers"] = sum(1 for row in rows if row["blocker"])
    out["n"] = len(rows)
    return out


def lint_summary(lint_rows, condition, response_rows, groups):
    """Linter totals over the given (case_id, trial) groups.

    A lint row counts only when the latest response for its key is ok and the row
    was made from that response's text. A lint row can outlive its response.
    """
    responses = common.latest(response_rows)
    rows = []
    for row in ok_rows(lint_rows, condition):
        source = responses.get(common.row_key(row))
        if source is None or not source.get("ok") or (row["case_id"], row["trial"]) not in groups:
            continue
        if row.get("text_hash") != lint.text_hash(source["text"]):
            continue
        rows.append(row)
    return {"errors": sum(row["errors"] for row in rows), "reviews": sum(row["reviews"] for row in rows), "n": len(rows)}


def jev_summary(jev_rows, questions, condition):
    rows = [row for row in common.latest(jev_rows).values() if row["condition"] == condition]
    rates = {}
    for key, spec in questions.items():
        answered = [row["answers"][key] for row in rows if row.get("ok") and key in row.get("answers", {})]
        bad = sum(1 for value in answered if (value >= spec["threshold"]) == (spec["bad_when"] == "yes"))
        rates[key] = {"answered": len(answered), "bad": bad, "rate": bad / len(answered) if answered else None}
    failures = Counter(row.get("reason") for row in rows if not row.get("ok"))
    return rates, failures


def jev_not_sent(cases, response_rows, jev_rows, questions, condition):
    """Ok responses with at least 1 applicable question and no Jev row. A Jev run that stopped early leaves these."""
    by_case = {case["id"]: case for case in cases}
    have = common.latest(jev_rows)
    count = 0
    for row in ok_rows(response_rows, condition):
        case = by_case.get(row["case_id"])
        if case is None or common.row_key(row) in have:
            continue
        if any(jev.applies(spec, case) for spec in questions.values()):
            count += 1
    return count


def scored_groups(score_rows, condition):
    return {(row["case_id"], row["trial"]) for row in ok_rows(score_rows, condition)}


def requested_trials(response_rows):
    """The trial count generate.py was asked for. A cap can stop a run before the last trial exists."""
    return max([row.get("trials", row["trial"]) for row in common.latest(response_rows).values()] or [0])


def expected_groups(cases, response_rows):
    return {(case["id"], trial) for case in cases for trial in range(1, requested_trials(response_rows) + 1)}


def comparability(response_rows, score_rows, reference, candidate, cases):
    def models(name):
        return {(row.get("model"), row.get("effort")) for row in ok_rows(response_rows, name)}

    def used(name):
        """The `models` lists that the CLI reported for the responses, one sorted tuple per distinct list."""
        return {tuple(sorted(row.get("models") or [])) for row in ok_rows(response_rows, name)}

    def hashes(name):
        return {row.get("rubric_hash") for row in ok_rows(score_rows, name)}

    ref_groups, cand_groups = scored_groups(score_rows, reference), scored_groups(score_rows, candidate)
    if not ref_groups or not cand_groups:
        return "no scored rows for %s or %s" % (reference, candidate)
    if ref_groups != cand_groups:
        return "case set or trial count differs: %d groups against %d" % (len(ref_groups), len(cand_groups))
    expected = expected_groups(cases, response_rows)
    if ref_groups != expected:
        missing = len(expected - ref_groups)
        return ("%d of %d case and trial groups are not scored, so the run is partial or a response failed. "
                "Rerun generate.py and judge.py" % (missing, len(expected)))
    if models(reference) != models(candidate) or len(models(reference)) != 1:
        return "model or effort differs: %s against %s" % (sorted(map(str, models(reference))), sorted(map(str, models(candidate))))
    if used(reference) != used(candidate):
        return "models used differ: %s against %s" % (sorted(map(list, used(reference))), sorted(map(list, used(candidate))))
    if hashes(reference) != hashes(candidate) or len(hashes(reference)) != 1:
        return "rubric differs: %s against %s" % (sorted(map(str, hashes(reference))), sorted(map(str, hashes(candidate))))
    return None


def paired_jev_rates(jev_rows, key, spec, reference, candidate, groups):
    """Bad-answer rates for 1 question over the groups both conditions answered. None when no group is paired."""
    latest = common.latest(jev_rows)

    def answers(name):
        return {(row["case_id"], row["trial"]): row["answers"][key] for row in latest.values()
                if row["condition"] == name and row.get("ok") and key in row.get("answers", {})
                and (row["case_id"], row["trial"]) in groups}

    ref_answers, cand_answers = answers(reference), answers(candidate)
    paired = set(ref_answers) & set(cand_answers)
    if not paired:
        return None, None, 0

    def rate(values):
        bad = sum(1 for group in paired if (values[group] >= spec["threshold"]) == (spec["bad_when"] == "yes"))
        return bad / len(paired)

    return rate(ref_answers), rate(cand_answers), len(paired)


def name_keys(keys, limit=10):
    """Name response keys as "case trial N condition", with at most `limit` names."""
    names = ["%s trial %d %s" % key for key in keys[:limit]]
    if len(keys) > limit:
        names.append("and %d more" % (len(keys) - limit))
    return ", ".join(names)


def gate(response_rows, score_rows, lint_rows, jev_rows, questions, reference, candidate, cases, out_of_date=()):
    """`out_of_date` holds the keys main() left out of response_rows, from common.split_out_of_date."""
    stale = [key for key in out_of_date if key[2] in (reference, candidate)]
    if stale:
        return {"refused": "%d %s or %s responses are out of date (%s); rerun generate.py"
                           % (len(stale), reference, candidate, name_keys(stale)), "checks": [], "passed": False}
    refusal = comparability(response_rows, score_rows, reference, candidate, cases)
    if refusal:
        return {"refused": refusal, "checks": [], "passed": False}
    ref, cand = judge_summary(score_rows, reference), judge_summary(score_rows, candidate)
    groups = scored_groups(score_rows, reference)  # comparability made these equal to the candidate's
    ref_lint = lint_summary(lint_rows, reference, response_rows, groups)
    cand_lint = lint_summary(lint_rows, candidate, response_rows, groups)
    lintable = {case["id"] for case in cases if case.get("lint", True)}
    expected_lint = sum(1 for case_id, _trial in groups if case_id in lintable)
    shortfall = ["lint rows missing for %d %s responses (%s)" % (expected_lint - summary["n"], role, name)
                 for role, name, summary in (("reference", reference, ref_lint), ("candidate", candidate, cand_lint))
                 if summary["n"] != expected_lint]
    if shortfall:
        return {"refused": "; ".join(shortfall) + "; rerun lint.py", "checks": [], "passed": False}
    by_case = {case["id"]: case for case in cases}
    jev_rules, jev_shortfall = [], []
    for key, spec in questions.items():
        if not spec.get("gating"):
            continue
        expected_jev = sum(1 for case_id, _trial in groups if case_id in by_case and jev.applies(spec, by_case[case_id]))
        if expected_jev == 0:
            continue  # the question applies to no scored case, so it decides nothing
        before, after, paired = paired_jev_rates(jev_rows, key, spec, reference, candidate, groups)
        if paired < expected_jev:
            jev_shortfall.append("Jev answers missing for %d of %d responses on %s"
                                 % (expected_jev - paired, expected_jev, key))
        jev_rules.append((key, before, after, paired))
    if jev_shortfall:
        return {"refused": "; ".join(jev_shortfall) + "; rerun jev.py", "checks": [], "passed": False}
    checks = [
        ("blockers", cand["blockers"] <= ref["blockers"], "%d against %d" % (cand["blockers"], ref["blockers"])),
        ("correctness", cand["correctness"] >= ref["correctness"] - TOLERANCE - EPSILON,
         "%.3f against %.3f" % (cand["correctness"], ref["correctness"])),
        ("safety", cand["safety"] >= ref["safety"] - TOLERANCE - EPSILON,
         "%.3f against %.3f" % (cand["safety"], ref["safety"])),
        ("weighted", cand["weighted"] > ref["weighted"] + EPSILON,
         "%.3f against %.3f" % (cand["weighted"], ref["weighted"])),
        ("lint errors", cand_lint["errors"] <= ref_lint["errors"] * (1 + LINT_MARGIN) + EPSILON,
         "%d against %d" % (cand_lint["errors"], ref_lint["errors"])),
    ]
    for key, before, after, paired in jev_rules:
        passed = before is not None and after is not None and round(after * paired) <= round(before * paired) + JEV_MARGIN
        checks.append(("jev " + key, passed, "%s against %s, over %d paired responses" % (fmt(after), fmt(before), paired)))
    return {"refused": None, "checks": checks, "passed": all(passed for _, passed, _ in checks)}


def slowest_calls(response_rows, score_rows):
    """[(stage, max duration_ms)] over the latest generate and judge rows that hold one. A stage with none is left out."""
    out = []
    for stage, rows in (("generate", response_rows), ("judge", score_rows)):
        values = [row["duration_ms"] for row in common.latest(rows).values()
                  if isinstance(row.get("duration_ms"), (int, float))]
        if values:
            out.append((stage, max(values)))
    return out


def fmt(value):
    return "-" if value is None else ("%.3f" % value if isinstance(value, float) else str(value))


def render(cases, conditions, response_rows, score_rows, lint_rows, jev_rows, questions, gate_result=None,
           stale_scores=0, stale_jev=0, out_of_date=(), stale_lint=0):
    latest = common.latest(response_rows)
    trials = requested_trials(response_rows)
    expected_keys = {(case["id"], trial, name) for case in cases for trial in range(1, trials + 1) for name in conditions}
    attempted = [row for key, row in latest.items() if key in expected_keys]
    finished = sum(1 for row in attempted if row.get("ok"))
    lines = ["# simple-english eval report", ""]
    if out_of_date:
        lines += ["**%d responses are out of date; rerun generate.py.** Every table leaves them out: %s."
                  % (len(out_of_date), name_keys(list(out_of_date))), ""]
    if not latest:
        lines += ["**No responses in this run.** Run generate.py first.", ""]
    else:
        if len(attempted) < len(expected_keys):
            lines += ["**This run is partial:** %d of %d responses exist." % (len(attempted), len(expected_keys)), ""]
        if finished < len(attempted):
            lines += ["**Some responses failed:** %d of %d responses succeeded." % (finished, len(expected_keys)), ""]
    if stale_scores:
        lines += ["%d score rows are stale and were left out." % stale_scores, ""]
    if stale_jev:
        lines += ["%d Jev rows are stale and were left out." % stale_jev, ""]
    if stale_lint:
        lines += ["%d lint rows are stale and were left out." % stale_lint, ""]
    if conditions and trials and trials % len(conditions):
        lines += ["Label positions are not balanced. The judge rotates the labels by trial, so each condition gets "
                  "each label equally only when the trial count is a multiple of the condition count. This run has "
                  "%d trials and %d conditions." % (trials, len(conditions)), ""]
    lines += ["## Judge scores", "", "| Condition | n | " + " | ".join(WEIGHTS) + " | weighted | blockers |",
              "| --- | ---: |" + " ---: |" * (len(WEIGHTS) + 2)]
    for name in conditions:
        summary = judge_summary(score_rows, name)
        lines.append("| %s | %d | %s | %s | %d |" % (name, summary["n"], " | ".join(fmt(summary[d]) for d in WEIGHTS),
                                                    fmt(summary["weighted"]), summary["blockers"]))
    lines += ["", "## Weighted score per case", "", "| Case | " + " | ".join(conditions) + " |",
              "| --- |" + " ---: |" * len(conditions)]
    for case in cases:
        cells = []
        for name in conditions:
            values = [weighted(row["scores"]) for row in ok_rows(score_rows, name) if row["case_id"] == case["id"]]
            cells.append(fmt(mean(values)))
        lines.append("| %s | %s |" % (case["id"], " | ".join(cells)))
    # Only groups that every condition scored, so each row of the table covers the same responses.
    groups = set.intersection(*[scored_groups(score_rows, name) for name in conditions]) if conditions else set()
    lines += ["", "## Linter", "", "Counted over the %d case and trial groups that every condition has a score for." % len(groups),
              "", "| Condition | responses | errors | reviews |", "| --- | ---: | ---: | ---: |"]
    for name in conditions:
        summary = lint_summary(lint_rows, name, response_rows, groups)
        lines.append("| %s | %d | %d | %d |" % (name, summary["n"], summary["errors"], summary["reviews"]))
    lines += ["", "## Jev bad-answer rate", "", "| Condition | " + " | ".join(questions) + " | failed calls | not sent |",
              "| --- |" + " ---: |" * (len(questions) + 2)]
    for name in conditions:
        rates, failures = jev_summary(jev_rows, questions, name)
        failed = ", ".join("%s %d" % (reason, count) for reason, count in sorted(failures.items())) or "0"
        not_sent = jev_not_sent(cases, response_rows, jev_rows, questions, name)
        lines.append("| %s | %s | %s | %d |" % (name, " | ".join("%s (%d)" % (fmt(rates[q]["rate"]), rates[q]["answered"])
                                                               for q in questions), failed, not_sent))
    gating = [key for key, spec in questions.items() if spec.get("gating")]
    lines += ["", "Gating Jev questions: %s." % (", ".join(gating) or "none, so Jev decides nothing")]
    problems = ["- %s trial %d %s: %s" % (row["case_id"], row["trial"], row["condition"], row.get("error"))
                for row in latest.values() if not row.get("ok")]
    failed_groups = {}  # judge.py scores a group in 1 call, so a failure is the same for every condition
    for row in common.latest(score_rows).values():
        if not row.get("ok"):
            failed_groups.setdefault((row["case_id"], row["trial"]), row.get("error"))
    problems += ["- %s trial %d judge: %s" % (group[0], group[1], error) for group, error in failed_groups.items()]
    if problems:
        lines += ["", "## Failed rows", ""] + problems
    slow = slowest_calls(response_rows, score_rows)
    if slow:
        lines += ["", "Slowest call: %s." % ", ".join("%s %d s" % (stage, round(ms / 1000.0)) for stage, ms in slow)]
    if gate_result is not None:
        lines += [""]
        if gate_result["refused"]:
            lines += ["## Gate: REFUSED", "", gate_result["refused"]]
        else:
            lines += ["## Gate: %s" % ("PASSED" if gate_result["passed"] else "FAILED"), "",
                      "| Rule | Result | Candidate against reference |", "| --- | --- | --- |"]
            lines += ["| %s | %s | %s |" % (name, "pass" if ok else "FAIL", detail) for name, ok, detail in gate_result["checks"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--candidate")
    args = parser.parse_args(argv)
    if bool(args.reference) != bool(args.candidate):
        parser.error("--reference and --candidate go together")
    folder = common.run_dir(args.run_id)
    rows = {name: common.read_jsonl(folder / ("%s.jsonl" % name)) for name in ("responses", "scores", "lint", "jev")}
    cases = common.load_cases()
    cfg = common.load_conditions()
    rubric = (common.EVALS_DIR / "rubric.md").read_text(encoding="utf-8")
    questions = jev.load_questions()
    # Drop out-of-date responses first, so no table, freshness check, or gate rule sees them.
    responses, out_of_date = common.split_out_of_date(rows["responses"], cases, cfg)
    current = judge.current_group_hashes(cases, responses, cfg, rubric)
    scores, stale_scores = fresh_scores(rows["scores"], current)
    jev_rows, stale_jev = fresh_jev(rows["jev"], cases, responses, questions)
    lint_rows, stale_lint = fresh_lint(rows["lint"], responses)
    result = None
    if args.reference:
        result = gate(responses, scores, lint_rows, jev_rows, questions, args.reference, args.candidate,
                      cases, out_of_date=out_of_date)
    conditions = list(cfg["conditions"])
    text = render(cases, conditions, responses, scores, lint_rows, jev_rows, questions, result,
                  stale_scores=stale_scores, stale_jev=stale_jev, out_of_date=out_of_date, stale_lint=stale_lint)
    (folder / "report.md").write_text(text, encoding="utf-8")
    print("report: %s" % (folder / "report.md"))
    if out_of_date:
        print("report: %d responses are out of date; rerun generate.py" % len(out_of_date))
    if not rows["responses"]:
        print("report: no responses in this run. Run generate.py first.")
        return 2
    if result is None:
        return 0
    if result["refused"]:
        print("gate: refused, %s" % result["refused"])
        return 2
    print("gate: %s" % ("passed" if result["passed"] else "failed"))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
