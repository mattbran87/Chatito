"""Jev calibration: sample a blind label sheet, then score Jev against it. See README.md.

The user fills in labels.jsonl by hand. Claude never fills it in: the point is
to measure Jev against a person, not against another model.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import common
import jev
import report

THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)
PASS_AGREEMENT = 0.8
MIN_EACH = 3
MUST_INCLUDE = ("diagnose-clear", "diagnose-partial")


def _order(row):
    return hashlib.sha256(("%s|%d|%s" % common.row_key(row)).encode("utf-8")).hexdigest()


def _blind_order(row):
    text = "%s\x00%s\x00%s\x00calibrate-order" % (row["case_id"], row["trial"], row["condition"])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def missing_must(responses, must=MUST_INCLUDE):
    """The (case, condition) pairs among the must cases that have no ok response."""
    latest = list(common.latest(responses).values())
    conditions = sorted({row["condition"] for row in latest})
    ok = {(row["case_id"], row["condition"]) for row in latest if row.get("ok")}
    return [(case_id, name) for case_id in must for name in conditions if (case_id, name) not in ok]


def _warn_missing(responses):
    for case_id, name in missing_must(responses):
        print("calibrate: warning: no ok response for %s under %s, so the sample lacks it." % (case_id, name), file=sys.stderr)


def sample(cases, responses, questions, n=20, must=MUST_INCLUDE, *, cfg):
    """Pick n responses, spread across conditions, with one of each must case per condition.

    The must cases are the only ones that `invents_cause` applies to, so without
    them a sample rarely holds the 3 "yes" and 3 "no" labels calibration needs.
    An out-of-date response (see common.split_out_of_date) is never picked.

    Returns (items, key). Items hold only an item number and blank labels, so
    the person who labels them never sees which condition wrote a response.
    """
    by_case = {case["id"]: case for case in cases}
    pool = [row for row in common.split_out_of_date(responses, cases, cfg)[0]
            if row.get("ok") and row["case_id"] in by_case and jev.request_questions(questions, by_case[row["case_id"]])]
    pool.sort(key=_order)
    conditions = sorted({row["condition"] for row in pool})
    picked = []
    for case_id in must:
        for name in conditions:
            for row in pool:
                if row["case_id"] == case_id and row["condition"] == name:
                    picked.append(row)
                    break
    queues = {name: [row for row in pool if row["condition"] == name and row not in picked] for name in conditions}
    while len(picked) < n and any(queues.values()):
        for name in conditions:
            if queues[name] and len(picked) < n:
                picked.append(queues[name].pop(0))
    picked = picked[:n]
    # Pick order is periodic by condition and groups each must case, so number the items in a hashed order.
    picked.sort(key=_blind_order)
    items, key = [], []
    for index, row in enumerate(picked, 1):
        asked = jev.request_questions(questions, by_case[row["case_id"]])
        items.append({"item": index, "labels": {q: None for q in asked}})
        key.append({"item": index, "case_id": row["case_id"], "trial": row["trial"], "condition": row["condition"],
                    "text_hash": text_hash(row["text"])})
    return items, key


def text_hash(text):
    """A hash of a response text, so score can tell when a labelled text has changed."""
    return common.input_hash(text, "")


def changed_items(labels, key, responses):
    """Labelled items whose latest response is missing, failed, or has new text since sample ran."""
    entries = {entry["item"]: entry for entry in key}
    latest = common.latest(responses)
    changed = []
    for row in labels:
        if not any(value in ("yes", "no") for value in row["labels"].values()):
            continue
        entry = entries[row["item"]]
        found = latest.get((entry["case_id"], entry["trial"], entry["condition"]))
        if not found or not found.get("ok") or text_hash(found.get("text", "")) != entry.get("text_hash"):
            changed.append(row["item"])
    return sorted(changed)


def render_sheet(items, key, cases, responses, questions):
    by_case = {case["id"]: case for case in cases}
    latest = common.latest(responses)
    lines = ["# Label sheet", "",
             "Do not open sample-key.jsonl until you finish labelling.", "",
             "For each item, read the prompt and the response, then set each label in labels.jsonl to \"yes\" or \"no\".",
             "Accepted values: \"yes\", \"y\", \"no\", \"n\" (any case), true, false. Leave a label as null when you cannot tell.", ""]
    for item, entry in zip(items, key):
        row = latest[(entry["case_id"], entry["trial"], entry["condition"])]
        lines += ["## Item %d" % item["item"], "", "**Prompt**", "", by_case[entry["case_id"]]["prompt"], "",
                  "**Response**", "", row["text"], "", "**Questions**", ""]
        lines += ["- `%s`: %s" % (q, questions[q]["question"]) for q in item["labels"]]
        lines.append("")
    return "\n".join(lines)


def write_sample(folder, cases, questions, cfg, n=20):
    """Write the label sheet, labels.jsonl, and sample-key.jsonl. Return the item count.

    With 0 items, write nothing, so an earlier sheet and its labels stay as they are.
    """
    responses = common.read_jsonl(folder / "responses.jsonl")
    _warn_missing(common.split_out_of_date(responses, cases, cfg)[0])
    items, key = sample(cases, responses, questions, n=n, cfg=cfg)
    if not items:
        return 0
    for name, rows in (("labels.jsonl", items), ("sample-key.jsonl", key)):
        path = folder / name
        if path.exists():
            path.unlink()
        for row in rows:
            common.append_jsonl(path, row)
    (folder / "sheet.md").write_text(render_sheet(items, key, cases, responses, questions), encoding="utf-8")
    return len(items)


YES_WORDS = ("yes", "y")
NO_WORDS = ("no", "n")


def _normalise(value):
    """Return "yes", "no", or None for a blank. Raise ValueError for anything else."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        word = value.strip().lower()
        if word in YES_WORDS:
            return "yes"
        if word in NO_WORDS:
            return "no"
        if word == "":
            return None
    raise ValueError("not an accepted value")


def validate_labels(labels, key, questions, cases):
    """Check the label sheet against the sample key and return the rows with each label as "yes", "no", or None."""
    by_case = {case["id"]: case for case in cases}
    entries = {entry["item"]: entry for entry in key}
    seen = set()
    rows = []
    for row in labels:
        item = row.get("item")
        if item in seen:
            raise ValueError("item %s appears more than once in labels.jsonl" % item)
        if item not in entries:
            raise ValueError("item %s is not in sample-key.jsonl" % item)
        seen.add(item)
        if not isinstance(row.get("labels"), dict):
            raise ValueError("item %s has no \"labels\" object" % item)
        expected = set(jev.request_questions(questions, by_case[entries[item]["case_id"]]))
        if set(row["labels"]) != expected:
            raise ValueError("item %s has the label keys %s, but its questions are %s"
                             % (item, sorted(row["labels"]), sorted(expected)))
        normalised = {}
        for question, value in row["labels"].items():
            try:
                normalised[question] = _normalise(value)
            except ValueError:
                raise ValueError("item %s, question %s: %r is not yes, no, or blank" % (item, question, value)) from None
        rows.append({"item": item, "labels": normalised})
    return rows


def count_labelled(rows):
    """The number of items with at least one yes or no label."""
    return sum(1 for row in rows if any(value in ("yes", "no") for value in row["labels"].values()))


def score(labels, key, jev_rows, questions, cases, responses):
    items = {entry["item"]: (entry["case_id"], entry["trial"], entry["condition"]) for entry in key}
    fresh, _ = report.fresh_jev(jev_rows, cases, responses, questions)
    answers = {common.row_key(row): row for row in fresh}
    results = {}
    for question in questions:
        pairs = []
        for row in labels:
            human = row["labels"].get(question)
            if human not in ("yes", "no"):
                continue
            found = answers.get(items[row["item"]])
            if not found or not found.get("ok") or question not in found.get("answers", {}):
                continue
            pairs.append((human == "yes", found["answers"][question]))
        yes = sum(1 for human, _ in pairs if human)
        no = len(pairs) - yes
        agreement = {t: (sum(1 for human, value in pairs if (value >= t) == human) / len(pairs) if pairs else None)
                     for t in THRESHOLDS}
        judged = yes >= MIN_EACH and no >= MIN_EACH
        threshold = None
        if judged:
            passing = [t for t in THRESHOLDS if agreement[t] >= PASS_AGREEMENT]
            if passing:
                # Round, so 0.4 and 0.6 are equally far from 0.5. A true tie goes to the lower threshold.
                threshold = max(passing, key=lambda t: (agreement[t], -round(abs(t - 0.5), 6), -t))
        results[question] = {"yes": yes, "no": no, "agreement": agreement, "threshold": threshold,
                             "judged": judged, "gating": threshold is not None}
    return results


def apply(questions, results):
    """Update the questions that were judged. Leave the rest exactly as they are.

    A judged question that passed gets gating and its threshold. One that failed
    loses gating and keeps its threshold. A question with too few labels is not judged.
    """
    for question, result in results.items():
        if not result["judged"]:
            continue
        questions[question]["gating"] = result["gating"]
        if result["gating"]:
            questions[question]["threshold"] = result["threshold"]
    return questions


def _agreement_line(result):
    return "  " + ", ".join("%.1f: %.0f%%" % (t, a * 100) for t, a in result["agreement"].items())


def _change_lines(question, before, after, result):
    if not result["judged"]:
        return ["%s: not judged (%d yes, %d no); left as is" % (question, result["yes"], result["no"])]
    old = (before["gating"], before["threshold"])
    new = (after["gating"], after["threshold"])
    if not result["gating"]:
        best = max(THRESHOLDS, key=lambda t: (result["agreement"][t], -t))
        outcome = "gating stays false" if not old[0] else "gating true -> false"
        head = "%s: failed (best %.0f%% at %.1f); %s" % (question, result["agreement"][best] * 100, best, outcome)
    elif old == new:
        head = "%s: no change" % question
    else:
        parts = []
        if old[0] != new[0]:
            parts.append("gating %s -> %s" % (str(old[0]).lower(), str(new[0]).lower()))
        if old[1] != new[1]:
            parts.append("threshold %s -> %s" % (old[1], new[1]))
        head = "%s: %s" % (question, ", ".join(parts))
    return [head, _agreement_line(result)]


def main(argv=None, runs_root=None, evals_dir=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sample", "score"):
        command = sub.add_parser(name)
        command.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    evals_dir = Path(evals_dir or common.EVALS_DIR)
    if args.command == "score" and not (Path(runs_root or common.RUNS_ROOT) / args.run_id).is_dir():
        print("calibrate: no run folder %s. Nothing written." % args.run_id, file=sys.stderr)
        return 1
    folder = common.run_dir(args.run_id, runs_root)
    questions_path = evals_dir / "jev_questions.json"
    questions = jev.load_questions(questions_path)
    cases = common.load_cases(evals_dir / "cases.jsonl")
    if args.command == "sample":
        conditions_path = evals_dir / "conditions.json"
        cfg = common.load_conditions(conditions_path if conditions_path.is_file() else None)
        count = write_sample(folder, cases, questions, cfg)
        if count == 0:
            print("calibrate: no current responses; rerun generate.py. Nothing written.", file=sys.stderr)
            return 1
        print("calibrate: %d items. Read %s, then fill in %s." % (count, folder / "sheet.md", folder / "labels.jsonl"))
        return 0
    for name in ("labels.jsonl", "sample-key.jsonl"):
        if not (folder / name).is_file():
            print("calibrate: %s is missing. Run `calibrate.py sample` first. Nothing written." % (folder / name), file=sys.stderr)
            return 1
    responses = common.read_jsonl(folder / "responses.jsonl")
    key = common.read_jsonl(folder / "sample-key.jsonl")
    try:
        labels = validate_labels(common.read_jsonl(folder / "labels.jsonl"), key, questions, cases)
    except ValueError as error:
        print("calibrate: %s. Nothing written." % error, file=sys.stderr)
        return 1
    absent = sorted({entry["item"] for entry in key} - {row["item"] for row in labels})
    print("calibrate: labelled %d of %d items%s" % (
        count_labelled(labels), len(key), ("; missing items: " + ", ".join(str(n) for n in absent)) if absent else ""))
    if not any(value in ("yes", "no") for row in labels for value in row["labels"].values()):
        print("calibrate: labels.jsonl holds no yes or no label. Nothing written.", file=sys.stderr)
        return 1
    changed = changed_items(labels, key, responses)
    if changed:
        print("calibrate: the response for %s %s is missing, failed, or changed since `calibrate.py sample` ran, so "
              "its labels describe other text. Run `calibrate.py sample` again and relabel. Nothing written."
              % ("item" if len(changed) == 1 else "items", ", ".join(str(n) for n in changed)), file=sys.stderr)
        return 1
    _warn_missing(responses)
    results = score(labels, key, common.read_jsonl(folder / "jev.jsonl"), questions, cases, responses)
    before = json.loads(json.dumps(questions))
    apply(questions, results)
    for question, result in results.items():
        print("\n".join(_change_lines(question, before[question], questions[question], result)))
    questions_path.write_text(json.dumps(questions, indent=2) + "\n", encoding="utf-8")
    print("calibrate: wrote %s" % questions_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
