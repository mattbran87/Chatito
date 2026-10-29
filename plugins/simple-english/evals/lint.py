"""Stage 2: ste_lint.py counts for each response. See README.md."""

import argparse
import json
import os
import subprocess
import re
import sys
import tempfile
from pathlib import Path

import common

LINTER = common.PLUGIN_DIR / "skills" / "simple-english" / "scripts" / "ste_lint.py"
# Read once. A row hash covers both, so a changed linter or a changed prepare() lints every response again.
LINTER_SOURCE = LINTER.read_text(encoding="utf-8")
SELF_SOURCE = Path(__file__).read_text(encoding="utf-8")
_LIST_ITEM = re.compile(r"(?:[-*+]|\d+[.)]) ")


def prepare(text):
    """Reshape markdown so the linter reads all of the prose.

    ste_lint.py skips lines that start with "|" and treats a line indented 4 or more
    spaces as code. Table cells and nested bullets are prose, so unpack them first.
    Fenced code stays as it is.
    """
    out = []
    fence = None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.lstrip()
        marker = stripped[:3] if stripped[:3] in ("```", "~~~") else None
        if marker:
            # ste_lint.py masks only backtick fences, so write a ~~~ fence as one.
            fenced = line.replace("~~~", "```", 1)
            if fence is None:
                fence = marker
                out.append(fenced)
                continue
            if marker == fence:
                fence = None
                out.append(fenced)
                continue
        if fence is not None:
            out.append(line)
        elif stripped.startswith("|"):
            if set(stripped) <= set("|-: "):
                continue
            for cell in stripped.split("|"):
                if cell.strip():
                    # A blank line keeps the cells from merging into one paragraph.
                    out.extend([cell.strip(), ""])
        elif _LIST_ITEM.match(stripped):
            out.append(stripped)
        else:
            out.append(line)
    return "\n".join(out)


def text_hash(text):
    """The hash a lint row stores: the response text, ste_lint.py, and this file, which holds prepare()."""
    return common.input_hash(text, LINTER_SOURCE + "\x00" + SELF_SOURCE)


def _lint(text, scope):
    """Run ste_lint.py with scope "--prose" or "--structure" on text, and return its findings."""
    with tempfile.TemporaryDirectory(prefix="se-lint-") as tmp:
        path = os.path.join(tmp, "response.md")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        done = subprocess.run([sys.executable, str(LINTER), "--json", scope, path],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    detail = (done.stderr or done.stdout or "")[:300]
    if done.returncode not in (0, 1) or "Traceback" in done.stderr:
        raise RuntimeError("ste_lint.py failed: " + detail)
    try:
        return json.loads(done.stdout)[path]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("ste_lint.py gave unusable output: " + detail)


def run_linter(text):
    """Prose rules read prepare()'s text. Structure rules read the original layout,
    because prepare() unpacks the tables and nested lists that those rules check."""
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    findings = _lint(prepare(text), "--prose") + _lint(raw, "--structure")
    errors = reviews = 0
    by_rule = {}
    for finding in findings:
        by_rule[finding["rule"]] = by_rule.get(finding["rule"], 0) + 1
        if finding["tier"] == "error":
            errors += 1
        else:
            reviews += 1
    return {"errors": errors, "reviews": reviews, "by_rule": by_rule}


def lint_run(cases, responses, out_path, linter=run_linter, *, cfg):
    """Lint each finished response once. A case with "lint": false is skipped.

    A response counts as done only when its latest lint row is ok and was made
    from the same text, because generate.py can replace a response under the same key.
    An out-of-date response (see common.split_out_of_date) is skipped, and nothing is written for it.
    """
    lintable = {case["id"] for case in cases if case.get("lint", True)}
    previous = common.latest(common.read_jsonl(out_path))
    count = 0
    fresh, _out_of_date = common.split_out_of_date(responses, cases, cfg)
    for key, row in sorted(common.latest(fresh).items()):
        if not row.get("ok") or row["case_id"] not in lintable:
            continue
        digest = text_hash(row["text"])
        old = previous.get(key)
        if old and old.get("ok") and old.get("text_hash") == digest:
            continue
        result = linter(row["text"])
        common.append_jsonl(out_path, {"case_id": key[0], "trial": key[1], "condition": key[2], "ok": True,
                                       "text_hash": digest, **result})
        count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    folder = common.run_dir(args.run_id)
    cases, cfg = common.load_cases(), common.load_conditions()
    responses = common.read_jsonl(folder / "responses.jsonl")
    count = lint_run(cases, responses, folder / "lint.jsonl", cfg=cfg)
    print("lint: %d responses linted" % count)
    out_of_date = common.split_out_of_date(responses, cases, cfg)[1]
    if out_of_date:
        print("lint: skipped %d out-of-date responses; rerun generate.py" % len(out_of_date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
