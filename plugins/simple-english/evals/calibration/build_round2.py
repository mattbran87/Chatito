"""Build the 2026-10-23-calibration run folder: old labelled items, 7 new real items, and planted items.

A one-off record of how calibration round 2 was built, kept so the round can be rebuilt.
Usage: python calibration/build_round2.py <evals dir> calibration/planted-2026-10-23.jsonl
Then run `jev.py` and `calibrate.py score` with --run-id 2026-10-23-calibration.
"""
import hashlib
import json
import sys
from pathlib import Path

EVALS = Path(sys.argv[1])
sys.path.insert(0, str(EVALS))
import calibrate  # noqa: E402
import common  # noqa: E402
import jev  # noqa: E402

SRC = common.run_dir("2026-10-20-baseline-2")
DST = common.run_dir("2026-10-23-calibration")
PLANTED = Path(sys.argv[2])
NEW_REAL = 7

assert not (DST / "responses.jsonl").exists(), "run folder already built"
cases = common.load_cases(EVALS / "cases.jsonl")
by_case = {c["id"]: c for c in cases}
questions = jev.load_questions(EVALS / "jev_questions.json")
responses = common.latest(common.read_jsonl(SRC / "responses.jsonl"))
jev_rows = common.latest(common.read_jsonl(SRC / "jev.jsonl"))
old_key = common.read_jsonl(SRC / "sample-key.jsonl")
old_labels = common.read_jsonl(SRC / "labels.jsonl")

old_keys = {(e["case_id"], e["trial"], e["condition"]) for e in old_key}
# New real items: ok rows with Jev questions and a fresh Jev row, not labelled before, in hash order.
pool = []
for key, row in responses.items():
    case = by_case.get(row["case_id"])
    if key in old_keys or not row.get("ok") or case is None or not jev.request_questions(questions, case):
        continue
    j = jev_rows.get(key)
    if not j or not j.get("ok") or j.get("text_hash") != jev.row_hash(case, row["text"], jev.request_questions(questions, case)):
        continue
    pool.append(row)
pool.sort(key=lambda r: hashlib.sha256(("%s|%d|%s|calib2" % common.row_key(r)).encode()).hexdigest())
new_real = pool[:NEW_REAL]

planted = []
counts = {}
for line in PLANTED.read_text(encoding="utf-8").splitlines():
    if line.strip():
        p = json.loads(line)
        counts[p["case_id"]] = counts.get(p["case_id"], 0) + 1
        planted.append({"case_id": p["case_id"], "trial": counts[p["case_id"]], "condition": "planted", "ok": True,
                        "text": p["text"]})

for key in sorted(old_keys):
    common.append_jsonl(DST / "responses.jsonl", responses[key])
    common.append_jsonl(DST / "jev.jsonl", jev_rows[key])
for row in new_real:
    common.append_jsonl(DST / "responses.jsonl", row)
    common.append_jsonl(DST / "jev.jsonl", jev_rows[common.row_key(row)])
for row in planted:
    common.append_jsonl(DST / "responses.jsonl", row)

# Old items keep their numbers and labels. New items get 21 on, in a blind hashed order.
for e in old_key:
    common.append_jsonl(DST / "sample-key.jsonl", e)
for row in old_labels:
    common.append_jsonl(DST / "labels.jsonl", row)
new_rows = sorted(new_real + planted,
                  key=lambda r: hashlib.sha256(("%s|%d|%s|calib2-order" % common.row_key(r)).encode()).hexdigest())
items, key = [], []
start = max(e["item"] for e in old_key) + 1
for n, row in enumerate(new_rows, start):
    asked = jev.request_questions(questions, by_case[row["case_id"]])
    item = {"item": n, "labels": {q: None for q in asked}}
    entry = {"item": n, "case_id": row["case_id"], "trial": row["trial"], "condition": row["condition"],
             "text_hash": calibrate.text_hash(row["text"])}
    items.append(item)
    key.append(entry)
    common.append_jsonl(DST / "labels.jsonl", item)
    common.append_jsonl(DST / "sample-key.jsonl", entry)

all_responses = common.read_jsonl(DST / "responses.jsonl")
sheet = calibrate.render_sheet(items, key, cases, all_responses, questions)
sheet = sheet.replace("# Label sheet", "# Label sheet, round 2\n\nItems 1 to %d keep the labels from round 1. Label items %d to %d."
                      % (start - 1, start, start + len(items) - 1), 1)
(DST / "sheet.md").write_text(sheet, encoding="utf-8")
labels = sum(len(i["labels"]) for i in items)
print("built %s: %d old items, %d new real, %d planted, %d new labels" % (DST, len(old_key), len(new_real), len(planted), labels))
