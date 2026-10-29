"""Shared helpers for the simple-english eval harness. See README.md."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = EVALS_DIR.parent
REPO_ROOT = PLUGIN_DIR.parent.parent
RUNS_ROOT = Path.home() / ".claude" / "simple-english-evals"
COST_FILES = ("responses.jsonl", "scores.jsonl")
MIN_CALL_USD = 0.01  # below this, run_claude would send --max-budget-usd 0.0000
PER_CALL_CAP_USD = 0.50  # the most one call may spend, and the cost recorded when a call reports none
# --tools "" removes the tools, but Claude Code's default system prompt still frames the model as a
# coding agent. Without this note, a debugging prompt can make it write tool calls as text until the
# timeout. It names no output format, so the judge still answers in JSON.
NO_TOOLS_NOTE = ("You have no tools in this conversation. Do not call tools or write out tool calls. "
                 "Answer from the information in the user's message.")
# The default run_claude timeout. The slowest normal call measured 43 s. A fake-tool-call loop streams
# at 60-80 tokens/s, so 180 s bounds a runaway near $0.25, under the $0.50 that a timeout records.
CALL_TIMEOUT_S = 180
STOP_AFTER_FAILURES = 3  # rows, or judge groups, in a row that end failed after their retries
KEEP_ENV = {"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"}


def run_dir(run_id, root=None):
    """The run folder, outside the repository. Run output churns every run."""
    path = Path(root or RUNS_ROOT) / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    lines = text.split("\n")
    torn_ok = not text.endswith("\n")
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as error:
            if torn_ok and number == len(lines):
                print("warning: %s: skipped a torn last line (%s)" % (path, error), file=sys.stderr)
                continue
            raise ValueError("%s:%d: %s" % (path, number, error)) from None
    return rows


def append_jsonl(path, row):
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        data = path.read_bytes()
        if not data.endswith(b"\n"):
            # A killed process left a torn last line. Drop it, or the new row joins it.
            print("warning: %s: dropped a torn last line before appending" % path, file=sys.stderr)
            with path.open("r+b") as handle:
                handle.truncate(data.rfind(b"\n") + 1)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def row_key(row):
    return (row["case_id"], row["trial"], row["condition"])


def latest(rows):
    """The newest row for each key. A rerun appends, so the last row wins."""
    out = {}
    for row in rows:
        out[row_key(row)] = row
    return out


def input_hash(prompt, system_text):
    """A short hash of what a call is given, so a changed input regenerates its row."""
    return hashlib.sha256((system_text + "\x00" + prompt).encode("utf-8")).hexdigest()[:12]


def strip_frontmatter(text):
    """Drop a leading --- block. An unterminated block is not frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "\n".join(lines[index + 1:]).strip()
    return text.strip()


# A comma-separated list of case ids. When set, every stage loads only those cases.
ONLY_ENV = "SIMPLE_ENGLISH_EVAL_ONLY"


def load_cases(path=None):
    cases = read_jsonl(path or EVALS_DIR / "cases.jsonl")
    only = os.environ.get(ONLY_ENV, "").strip()
    if not only:
        return cases
    wanted = {part.strip() for part in only.split(",") if part.strip()}
    if not wanted:
        raise ValueError("%s names no case ids: %r" % (ONLY_ENV, only))
    unknown = sorted(wanted - {case["id"] for case in cases})
    if unknown:
        raise ValueError("%s names unknown cases: %s" % (ONLY_ENV, ", ".join(unknown)))
    return [case for case in cases if case["id"] in wanted]


def load_conditions(path=None):
    with Path(path or EVALS_DIR / "conditions.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def condition_text(cfg, name):
    """The text a condition adds to the system prompt. None means baseline."""
    source = cfg["conditions"][name]
    if source is None:
        return ""
    return strip_frontmatter((PLUGIN_DIR / source).read_text(encoding="utf-8"))


def system_text_for(text):
    """The system text run_claude sends: the condition text, if any, then NO_TOOLS_NOTE."""
    return text + "\n\n" + NO_TOOLS_NOTE if text else NO_TOOLS_NOTE


def response_hash(case, cfg, condition_name, text=None):
    """The input_hash generate.py stores on a response: prompt, model, effort, and the system text sent.

    The system text is the condition text plus NO_TOOLS_NOTE, so a changed note makes
    every response out of date. A response whose stored hash differs is out of date.
    Every stage after generate.py treats it as missing. `text` is the condition text
    when the caller has read it already.
    """
    if text is None:
        text = condition_text(cfg, condition_name)
    return input_hash(case["prompt"], "%s\x00%s\x00%s" % (cfg["model"], cfg.get("effort"), system_text_for(text)))


def split_out_of_date(responses, cases, cfg):
    """The latest response rows without the out-of-date ones, and the sorted keys of those left out.

    An ok row is out of date when its input_hash differs from response_hash() for the
    current case and conditions.json. A row for an unknown case or condition stays,
    because no current hash exists for it.
    """
    by_case = {case["id"]: case for case in cases}
    texts = {}
    kept, out_of_date = [], []
    for key, row in latest(responses).items():
        case = by_case.get(row["case_id"])
        name = row["condition"]
        if row.get("ok") and case is not None and name in cfg["conditions"]:
            if name not in texts:
                texts[name] = condition_text(cfg, name)
            if row.get("input_hash") != response_hash(case, cfg, name, texts[name]):
                out_of_date.append(key)
                continue
        kept.append(row)
    return kept, sorted(out_of_date)


def claude_argv():
    """argv prefix for the claude CLI.

    On Windows the npm install is claude.CMD, which only runs the claude.exe
    beside it. Run that exe directly when it exists. Through cmd.exe, a timeout
    kills only cmd.exe and then waits for the real child, and the call breaks
    when the path holds a space. Without the exe, fall back to cmd.exe /c,
    as session-tools trigger_test.py does.
    """
    exe = shutil.which("claude")
    if exe and os.path.splitext(exe)[1].lower() in (".cmd", ".bat"):
        direct = (Path(exe).parent / "node_modules" / "@anthropic-ai" / "claude-code"
                  / "bin" / "claude.exe")
        if direct.exists():
            return [str(direct)]
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", exe]
    return [exe or "claude"]


def child_env(environ=None):
    """The environment for the child call. Drops the parent session's CLAUDE* variables."""
    environ = os.environ if environ is None else environ
    return {k: v for k, v in environ.items()
            if not k.startswith("CLAUDE") or k in KEEP_ENV}


def require_claude():
    if shutil.which("claude") is None:
        raise SystemExit("claude is not on the PATH. Install Claude Code or fix PATH, then rerun.")


def parse_claude_output(code, stdout, stderr):
    try:
        data = json.loads(stdout)
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except ValueError:
        detail = (stderr or stdout or "").strip()
        return {"ok": False, "error": ("exit %d: %s" % (code, detail))[:300], "cost_usd": None}
    reported = data.get("total_cost_usd")
    cost = None if reported is None else float(reported)
    models = list((data.get("modelUsage") or {}).keys())
    timing = {"duration_ms": data["duration_ms"]} if isinstance(data.get("duration_ms"), (int, float)) else {}

    def fail(error):
        return dict({"ok": False, "error": error[:300], "cost_usd": cost, "models": models}, **timing)

    if data.get("is_error") or data.get("subtype") != "success":
        return fail("%s: %s" % (data.get("subtype"), data.get("result")))
    result = data.get("result")
    # stop_reason may sit at the top level or in a result object, or be absent.
    nested = result if isinstance(result, dict) else {}
    stop_reason = data.get("stop_reason") or nested.get("stop_reason")
    if stop_reason == "max_tokens":
        return fail("max-tokens")
    # A success must carry its reply as a non-empty string. Anything else would reach the judge as a response.
    if result is not None and not isinstance(result, str):
        return fail("bad-result")
    text = result or ""
    if not text.strip():
        return fail("empty-result")
    if "<invoke" in text or "<function_calls>" in text:
        # The model wrote tool calls as text, as in the loop that stalled the first paid run.
        return fail("fake-tool-call")
    return dict({"ok": True, "text": text, "cost_usd": cost or 0.0, "models": models}, **timing)


def call_budget(budget_usd, spent_usd):
    """The --max-budget-usd for the next call: what is left of the run cap, but never over PER_CALL_CAP_USD."""
    return min(budget_usd - spent_usd, PER_CALL_CAP_USD)


def slowest(so_far, result):
    """The larger of the slowest duration_ms so far (None for none yet) and this attempt's duration_ms."""
    value = result.get("duration_ms")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return so_far
    return value if so_far is None else max(so_far, value)


class FailureStreak:
    """Counts rows, or judge groups, that end failed in a row after their retries.

    add() returns None, or the stop reason once STOP_AFTER_FAILURES failed rows
    come in a row: "timeouts" when each one ended on a timeout or an unpriced
    failure, else "failures". A row that succeeds resets the count.
    """

    def __init__(self):
        self.unpriced = []

    def add(self, ok, ended_unpriced):
        if ok:
            self.unpriced = []
            return None
        self.unpriced.append(bool(ended_unpriced))
        if len(self.unpriced) < STOP_AFTER_FAILURES:
            return None
        return "timeouts" if all(self.unpriced[-STOP_AFTER_FAILURES:]) else "failures"


def stop_message(stage, summary):
    """The line a stage prints when STOP_AFTER_FAILURES failed rows in a row stopped it.

    generate.py sets `condition`: a name when one condition's count stopped it, or
    None when the overall count did. judge.py sets no `condition`.
    """
    rows = "%d rows in a row" % STOP_AFTER_FAILURES
    if summary.get("condition"):
        rows += " for condition %s" % summary["condition"]
    elif "condition" in summary:
        rows += " across conditions"
    if summary["stopped"] == "timeouts":
        why = ("%s failed on a timeout or a call that reported no cost. Each such call counts as $%.2f"
               % (rows, PER_CALL_CAP_USD))
    else:
        why = "%s failed after their retries" % rows
    return ("%s: stopped, because %s. Last error: %s. Check claude and the network, then rerun to resume."
            % (stage, why, summary.get("error")))


def attempt_cost(result):
    """The dollars to record for one call attempt, and whether that figure is an estimate.

    A timeout, or a failure that reports no cost, may still have spent money. It
    counts as PER_CALL_CAP_USD, the per-call cap, so spent() never under-counts.
    """
    cost = result.get("cost_usd")
    if not result.get("ok") and (result.get("error") == "timeout" or cost is None):
        return PER_CALL_CAP_USD, True
    return float(cost or 0.0), False


def run_claude(prompt, system_text, model, budget_usd, effort=None, runner=subprocess.run, timeout=CALL_TIMEOUT_S):
    """One isolated `claude -p` call. Returns {ok, text | error, cost_usd, models?}.

    `--setting-sources ""` keeps the operator's settings out, including an
    output style that would otherwise reach the baseline. The prompt goes in
    on stdin and the system text through a file, because cmd.exe breaks
    arguments that hold newlines, quotes, or pipes. The call runs in an empty
    temporary folder, so no project CLAUDE.md loads. Every call gets NO_TOOLS_NOTE
    after the system text, so a baseline call gets the note alone.

    A call that times out or prints no JSON reports cost_usd None: it may have
    spent money, but the amount is unknown. The callers record PER_CALL_CAP_USD
    for it (see attempt_cost) and pass at most that cap as `budget_usd`.

    The timeout, CALL_TIMEOUT_S (180 s), is what bounds a runaway reply. The CLI
    sets no hard output cap: a test with CLAUDE_CODE_MAX_OUTPUT_TOKENS=500 got
    1,380 output tokens and stop_reason end_turn. The slowest normal call measured
    43 s. A fake-tool-call loop streams at 60 to 80 tokens/s, so 180 s bounds a
    runaway near $0.25, and the $0.50 that a timeout records stays an upper bound.
    """
    with tempfile.TemporaryDirectory(prefix="se-eval-") as cwd:
        argv = claude_argv() + [
            "-p", "--output-format", "json",
            "--tools", "", "--setting-sources", "",
            "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config",
            "--model", model, "--max-budget-usd", "%.4f" % budget_usd,
        ]
        if effort:
            argv += ["--effort", effort]
        system_path = os.path.join(cwd, "system.md")
        with open(system_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(system_text_for(system_text))
        argv += ["--append-system-prompt-file", system_path]
        env = child_env()
        try:
            done = runner(argv, input=prompt, capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "cost_usd": None}
    return parse_claude_output(done.returncode, done.stdout, done.stderr)


def spent(folder):
    """Dollars spent so far in a run. One cap covers generation and judging."""
    total = 0.0
    for name in COST_FILES:
        for row in read_jsonl(Path(folder) / name):
            total += float(row.get("cost_usd") or 0.0)
    return total
