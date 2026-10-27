# simple-english evals

This harness runs 15 cases under 3 conditions and scores every response with
3 judges. It answers one question: do the rules make a response better, and
does a rule change make them better still?

Design: `2026-10-20-simple-english-eval-design.md`, in the specs folder of the
development repository.

| Condition | Text added to the system prompt |
| --- | --- |
| `baseline` | None, except the no-tools note that every condition gets (see Limits) |
| `skill` | `skills/simple-english/SKILL.md`, without frontmatter |
| `style` | `output-styles/simple-english.md`, without frontmatter |

| Judge | Measures |
| --- | --- |
| `ste_lint.py` | The 10 rules a regex can find |
| Claude, blind | 5 dimensions, with all conditions side by side. The labels run A, B, C, D, and so on, 1 for each condition. |
| Jev | 5 narrow yes-or-no questions, one response at a time |

## Run it

Pick a run id, such as the date. Every stage takes the same id, writes to
`~/.claude/simple-english-evals/<run-id>/`, and resumes where it stopped.

```
python3 generate.py --run-id 2026-10-21 --budget-usd 15
python3 lint.py     --run-id 2026-10-21
python3 judge.py    --run-id 2026-10-21 --budget-usd 15
python3 jev.py      --run-id 2026-10-21
python3 report.py   --run-id 2026-10-21
```

`--budget-usd` caps the whole run. Generation and judging share it, so pass
the same number to both. When a stage reaches the cap, it stops, and the
report marks the run as partial. Raise the cap and rerun to continue.

Run `generate.py` and `judge.py` one after the other, never at the same time.
Each stage reads the spend in the run folder once, when it starts. Two stages
that run together do not see each other's spend, so together they can spend
up to 2 times the cap.

Each call gets the remaining budget as `--max-budget-usd`, but never more than
$0.50. Claude Code checks that value between turns, so 1 call can spend a
little more than its budget.

A call that times out, or that fails and reports no cost, can still cost
money. The harness records $0.50 for it and sets `cost_estimated: true` on the
row. So the recorded spend can run high, but not low.

Each row gets its retries first: 3 calls in `generate.py`, and 2 calls for
each group in `judge.py`. When a row fails after its retries, the stage
records the failure and goes on to the next row. After 3 failed rows in a row, of any kind,
the stage stops, prints the last error, and exits 1. A row that succeeds sets
the count back to 0. `generate.py` keeps 1 count for each condition and 1
overall count. It stops at 3 failed rows in a row for one condition, or at 3
failed rows in a row across conditions, whichever comes first, and it names
the condition or says "across conditions". So a condition that always fails
stops the run early, and so does a run where every call fails. `judge.py`
keeps 1 count, because each group holds every condition.

On a rerun, `generate.py` skips a row whose last try failed on its content,
with `fake-tool-call`, `empty-result`, or `bad-result`, when its inputs did not
change. The same inputs would most likely fail the same way at the same cost.
The stage prints how many rows it skipped. Pass `--retry-failed` to try them
again. A timeout or any other failure always gets a new try. So 1 row whose content always fails does not stop a run.

Each generate and judge row stores `duration_ms`, the time that the CLI
reports for the slowest call of the row. Under the failure list, the report
shows the slowest call of each stage, such as `Slowest call: generate 43 s,
judge 12 s.` Use it to check that normal calls stay well under the 180-second
timeout. A call that times out reports no duration, so this line never
includes a timeout. The failed-rows list shows each timeout.
For the judge, a reply that is not valid score JSON is a failed call. Check
`claude` and the network, then rerun.

**Jev sends data only when you opt in.** Add
`"simple_english_eval": { "enabled": true }` to `.claude/jev.json` and set
`TYPESAFE_API_KEY`. Each send holds the case prompt and the response, cut to
4,000 characters and redacted. Before the redaction, `jev.py` also masks
local paths: `C:\Users\<name>\` becomes `~\`, and the name inside any other
path becomes `[user]` (names of 4 or more characters only). This masking is
local to the eval and does not change the Jev contract or the client.
Without the opt-in, the Jev column shows `not-opted-in` and the other judges
still run.

If your repository tracks `.claude/jev.json`, the file turns features on for
everyone who pulls it. Make the opt-in edit locally, and never commit it.

## Stale rows

Each stage hashes its inputs and stores the hash in every row. A rerun skips a
row only when its stored hash equals the current hash. So after an edit, a
rerun regenerates, relints, or rejudges only the rows that the edit affects.

| Edit | Rows that change |
| --- | --- |
| `SKILL.md`, the output style file, the model, or the effort | Responses, then every row made from them |
| `NO_TOOLS_NOTE` in `common.py` | Every response, because each response hash includes the note, then every row made from them |
| A case prompt | Responses for that case, then every row made from them |
| A case's criteria, or the rubric's judge block | Scores |
| `ste_lint.py` or `lint.py` | Lint rows |
| A Jev question | Jev rows |
| A Jev question's `threshold`, `gating`, or `bad_when` | No row. `jev.py` hashes only the question text, so no Jev call reruns. `report.py` reads these keys when it runs, so the bad-answer rates and the gate result can change |

A response is out of date when its hash no longer matches the case and
`conditions.json`. `judge.py`, `lint.py`, `jev.py`, and `calibrate.py sample`
skip an out-of-date response, so they make no call and write no row for it.
`judge.py` lists its group as skipped.

The report leaves out each stale score, lint, or Jev row and counts it in a
line such as `3 score rows are stale and were left out.` It also leaves out
the out-of-date responses, counts them in the line `N responses are out of
date; rerun generate.py.`, and names them.

So after any edit, rerun every stage in order: generate, lint, judge, jev,
report. When you skip a stage, the gate refuses:

- A skipped `generate.py` leaves out-of-date responses. The gate names them.
- A skipped `judge.py` leaves groups with no fresh score, so the run is
  partial.
- A skipped `lint.py` or `jev.py` leaves lint rows or gating Jev answers
  missing.

## Compare a rule change

1. Add the edited file as a new condition in `conditions.json`, such as
   `"skill-next": "skills/simple-english/SKILL.md.next"`.
2. Run every stage again with a new run id.
3. Apply the gate:

   ```
   python3 report.py --run-id 2026-10-22 --reference skill --candidate skill-next
   ```

The exit code is 0 when the gate passes and 1 when it fails. The exit code is
2 when the gate refuses to compare. It refuses in these cases:

- A reference or candidate response is out of date. Rerun `generate.py`.
- The 2 conditions differ in cases, trials, model, effort, or rubric. The gate
  also refuses when the `models` lists that the CLI reported for the responses
  differ, and it names them.
- The run is partial. The scored groups do not cover every case and every
  requested trial. A failed response or a failed judge call causes the same
  result.
- A lintable response has no lint row, or its lint row is stale. Rerun
  `lint.py`.
- A gating Jev question has no answer for a response. Rerun `jev.py`.
- The run has no responses. `report.py` exits 2 in this case even when you
  pass no `--reference`.

2 rules allow for noise. The candidate may have up to 10% more linter errors
than the reference (`LINT_MARGIN`), and 1 more bad answer for each gating Jev
question (`JEV_MARGIN`). 2 runs of near-identical text moved linter errors from
36 to 42 and flagged a different single Jev answer each time, so a rule with
no margin failed on noise.

The lint counts in the report and in the gate cover only the case and trial
groups that every condition has a score for. Before it lints, the harness
unpacks table cells and nested bullets, so the linter counts the prose in them.

## Calibrate Jev

Jev's numbers decide nothing until a question passes calibration.

1. `python3 calibrate.py sample --run-id <id>` writes `sheet.md`,
   `labels.jsonl`, and `sample-key.jsonl` to the run folder. The sample holds
   20 responses, spread across the conditions. It always holds both diagnosis
   cases, `diagnose-clear` and `diagnose-partial`, under every condition.
   Only those cases can answer "yes" to `invents_cause`. The sample never
   holds an out-of-date response. When no response is current, `sample` exits
   1 and writes nothing. Rerun `generate.py` first.
2. Read `sheet.md`. The harness numbers the items in a hashed order, so an
   item number does not show the condition. In `labels.jsonl`, set each label
   to a value from this list:
   - Yes: `yes`, `y`, or `true`
   - No: `no`, `n`, or `false`
   - Blank: `null` or an empty string, when you cannot tell

   Do not open `sample-key.jsonl` first: it names the condition of each item.
   Label by hand. A model must not fill in this sheet.
3. `python3 calibrate.py score --run-id <id>` prints 1 line per question and
   the agreement at each threshold. It then writes `gating` and `threshold`
   into `jev_questions.json`.

Real responses rarely hold the flaws the questions look for, so a sample of
them alone gives too few "yes" labels to judge a question. Round 2 added
hand-written responses with planted flaws, from
`calibration/planted-2026-10-23.jsonl`. `calibration/build_round2.py` shows
how that run folder was built.

`score` exits 1 and writes nothing in these cases:

- The run folder does not exist.
- `labels.jsonl` or `sample-key.jsonl` is missing.
- A label holds a value that is not in the list above.
- The labels hold no "yes" and no "no".
- The response for a labeled item is missing, failed, or has different text
  since `sample` ran. `score` names those items. Run `sample` again and label
  the new sheet.

A question passes when Jev agrees with your labels on at least 80% of items at
one threshold, and your labels hold at least 3 "yes" and 3 "no". The tested
thresholds are 0.3, 0.4, 0.5, 0.6, and 0.7. A passing question gets
`gating: true` and the best threshold.

A question with fewer than 3 "yes" or fewer than 3 "no" labels has no
judgment. `score` prints "not judged" and keeps its current `gating` and
`threshold`. Only a judged question that fails loses `gating`. It keeps its
threshold. Commit the changed `jev_questions.json`.

## Limits

- **Every call gets a no-tools note.** The calls run with `--tools ""`, but
  Claude Code's default system prompt still tells the model that it is a
  coding agent. In the first paid run, a debugging case made the model write
  tool calls as text in a loop until the 600-second timeout. So every
  generation call and every judge call gets `common.NO_TOOLS_NOTE` at the end
  of its system text. The `baseline` condition gets the note alone. The note
  changes what the eval measures, but it changes it the same way for every
  condition, so the comparison between conditions stays fair. The note is
  part of each response hash, so a change to the note regenerates every
  response.
- **The timeout bounds a runaway reply, not a token cap.** The CLI sets no
  hard output cap. A test with `CLAUDE_CODE_MAX_OUTPUT_TOKENS=500` got 1,380
  output tokens and `stop_reason: end_turn`. So each call stops after
  `common.CALL_TIMEOUT_S`, 180 seconds. The slowest normal call took 43
  seconds. A reply that loops on fake tool calls streams 60 to 80 tokens a
  second, so 180 seconds costs about $0.25, and the $0.50 that a timeout
  records stays an upper bound.
- **A reply that writes out a tool call fails.** The row stores the error
  `fake-tool-call`, and it keeps the cost that the CLI reported. A reply with
  `stop_reason: max_tokens` fails with `max-tokens` in the same way, if the
  CLI ever caps output. A failed call gets the usual retries, and 3 rows in
  a row that fail after their retries stop the stage.

- **The `style` condition tests the text, not the loading.** An installed
  output style replaces part of Claude Code's system prompt.
  `--append-system-prompt-file` only adds to it.
- **The judge and the writer are the same model.** Jev is the cross-model
  check, once it passes calibration.
- **The `skill` condition cannot load `references/documents.md`.** The skill
  tells Claude to read that file before it finalizes a document, but no case
  has tools. So on `doc` cases the `skill` condition is weaker than the skill
  in real use.
- **One hand check proved the isolation.** On 2026-10-20, with Claude Code
  2.1.300, a call with the flags in `common.run_claude` reported
  `output_style: default` and empty `tools`, `mcp_servers`, `skills`, and
  `slash_commands` in its `init` event. Only built-in plugins loaded. If you
  upgrade Claude Code, check this again with `--output-format stream-json
  --verbose`.
- **Effort stays fixed.** `conditions.json` sets `effort`, and every row stores
  it. The gate refuses to compare runs with a different model or effort.
- **Label positions balance only when the trial count is a multiple of the
  condition count.** The judge's labels rotate by trial. With 3 conditions and
  3 trials, each condition sits in each position once per case. With 4
  conditions, 3 trials are not balanced. The report shows a note when the
  positions are not balanced.
- **3 trials is few.** In the `i-have-adhd` run, per-case standard deviations
  reached 0.95. Treat a single-case difference under about 0.5 as noise.
- **No case uses tools,** so the eval cannot measure what Claude does in a
  repository.

## Results

Run output stays out of the repository. Commit a `FINDINGS-<date>.md` here for
each run worth keeping: the date, the model, the CLI version, the cost, and
the report tables.
