# simple-english deep dive

This page explains how the simple-english plugin works and why it works that
way. For the shapes, read the 2 pages next to it:
[workflows.md](workflows.md) holds the diagrams, and
[data-model.md](data-model.md) holds the files, keys, and hashes.

## Delivery surfaces

The plugin ships 1 rule set in 3 files. Each file has its own trigger, as the
table in `plugins/simple-english/README.md` lists:

| File | Turns on | Size |
| --- | --- | ---: |
| `skills/simple-english/SKILL.md` | Claude invokes it for any expository prose, or you type its slash command, /simple-english:simple-english | 18,145 bytes |
| `skills/simple-english-docs/SKILL.md` | Claude invokes it for a project document only | 22,273 bytes |
| `output-styles/simple-english.md` | You select it in the /output-style picker, and then it applies to every reply | 10,550 bytes |

The sizes come from `wc -c`. The next 3 sentences describe how Claude Code
loads skills and output styles, not anything this repository sets. Until a
skill triggers, only its `description:` field sits in context. When the skill
triggers, its whole body enters the context. The output style costs its 10,550
bytes on every reply, because Claude Code puts it into the system prompt. In
exchange, it needs no trigger.

The 3 files carry near-copies of the same rules, because each route starts
from its own file and can reach no other route's files. The output style is a
single file, and neither skill reads the other skill's folder
(`plugins/simple-english/README.md`, "The linter"). So each file must hold the goals, the hard
floor, the exemptions, and the rule lists itself. The copies differ only where
the scope differs:

- `skills/simple-english/SKILL.md` covers chat replies too. For a document,
  it sends Claude to `skills/simple-english/references/documents.md` for the
  linter steps.
- `skills/simple-english-docs/SKILL.md` covers documents only. It holds the
  linter steps inline, with the regex patterns as a fallback, and it adds the
  RFC 2119 exception and the partial-edit rule.
- `output-styles/simple-english.md` keeps the rules and a "Check before you
  send" list. Its check item 1 also says that a caveat about what you cannot
  see comes after the first sentence. The cycle 3 style run added that line
  (`FINDINGS-2026-10-23-style3.md`).

`plugins/simple-english/README.md` says to use 1 skill, not both. The `simple-english` description
says to choose it instead of a document-only style skill.

## The rule text

`skills/simple-english/SKILL.md` sets 2 goals in a fixed order: higher
readability first, shorter output second. The order decides every conflict.
So a table that runs longer than a paragraph still wins when the reader
compares columns in it.

A hard floor limits goal 2: a cut never removes a warning. The floor keeps
each sentence that carries a failure mode, a precondition, a recovery step,
or a threshold. It also keeps the words that set the risk, such as
"silently" and "only". The floor outranks every other rule, the sentence caps
too. The "Common Mistakes" table gives the reason: blind judges caught a
shorter version that dropped a rollback warning.

The Exemptions section carries the heading "read first", and its items win over every
rule. They
cover text that the request, a template, or a tool requires, such as a
`Resolves:` field. They also cover code, identifiers, quoted material, and
mandated boilerplate. A rule edit there breaks the thing the text names.

`skills/simple-english/references/documents.md` extends the skill for
documents only. A document allows a search before you finalize it, and a
chat reply does not. So this file holds the linter steps: run the linter
once, fix each `ERROR`, judge each `review` hit, then run once more with
`--quiet` and stop. It also holds the RFC 2119 exception and the partial-edit
rule.

The eval has a known limit here. The `skill` condition adds
`skills/simple-english/SKILL.md` to the system prompt, and no eval call has
tools. So the model cannot read
`skills/simple-english/references/documents.md`, and on `doc` cases the
`skill` condition runs weaker than the skill in real use. The "Limits"
section of the [evals README](../../../plugins/simple-english/evals/README.md#limits)
records this.

## The linter

`skills/simple-english/scripts/ste_lint.py` checks the 10 rules that a search
can reach. It uses the Python standard library only. Its `RULES` list, at
`ste_lint.py:111`, holds 8 patterns, and 2 functions add the length checks.
The rules fall in 2 tiers:

| Tier | Output label | Rules |
| --- | --- | --- |
| `error` | `ERROR` | `perfect` (stacked auxiliaries), `passive`, `spelling` (British) |
| `warn` | `review` | `gerund`, `vague`, `modal`, `canonical`, `condition`, `length`, `paragraph` |

The exit code is 1 when the linter finds an error, and 0 for review hits
only. A review hit asks for a judgment, because each of those patterns also
matches correct text. For example, `modal` flagged 29 hits in the measured
corpus, and 17 of them were real counterfactuals, as the precision note in
`RULES` records. The caps are `PROSE_CAP_DESCRIPTIVE` (25 words),
`PROSE_CAP_PROCEDURAL` (20 words), and `PARAGRAPH_CAP` (6 sentences). The
`--selftest` flag runs 19 planted cases, and it reported `19 passed, 0
failed` at `1d7c77c`.

Each skill carries its own copy of the script, because a skill cannot read
files from another skill's folder (`plugins/simple-english/README.md`, "The linter"). The 2 copies
are `skills/simple-english/scripts/ste_lint.py` and
`skills/simple-english-docs/scripts/ste_lint.py`. `cmp` found no difference
between them at `1d7c77c`. `plugins/simple-english/README.md` says to keep them identical, but no
test in the plugin tests compares them. The eval uses only the first copy:
`LINTER` in `evals/lint.py` points at it.

The linter skips 2 groups of text, and it leaves out 5 checks:

- `mask` blanks 5 kinds of text: fenced code, indented code, inline code,
  URLs, and quoted text. So it never flags the exemptions.
- `is_structural` skips blank lines, headings, table rows, separator lines,
  and short front-matter labels such as `Status:`. For the eval,
  `lint.prepare` in `evals/lint.py` unpacks table cells and nested bullets
  first, so the eval counts that prose.
- The docstring of the script names 3 rules it leaves out: noun clusters,
  list parallelism, and one term per concept beyond the fixed table.
  Detectors for them ran at about 85% false positives without
  part-of-speech tagging.
- The footer of a run without `--quiet` also says that the linter cannot
  check front-loading, or if a claim names its mechanism.

## Eval stages

A run has 5 stages, in this order. `evals/calibrate.py` runs apart from them.
The commands and flags are in the
[evals README](../../../plugins/simple-english/evals/README.md#run-it). The run
folder holds the files in the "Writes" column.

| Stage | Reads | Writes | Makes model calls | Stops when |
| --- | --- | --- | --- | --- |
| `evals/generate.py` | `evals/cases.jsonl`, `evals/conditions.json`, each condition file, its own earlier rows, the spend in `responses.jsonl` and `scores.jsonl` | `responses.jsonl` | yes, 1 `claude` call per case, trial, and condition, with up to 3 tries | every row is current (exit 0) |
| `evals/lint.py` | `responses.jsonl`, `evals/cases.jsonl`, `evals/conditions.json`, the linter, its own earlier rows | `lint.jsonl` | no | every current response of a case without `"lint": false` has a current row (exit 0) |
| `evals/judge.py` | `responses.jsonl`, `evals/cases.jsonl`, `evals/conditions.json`, `evals/rubric.md`, its own earlier rows, the spend in `responses.jsonl` and `scores.jsonl` | `scores.jsonl` | yes, 1 `claude` call per case and trial group, with up to 2 attempts | every group is current (exit 0) |
| `evals/jev.py` | `responses.jsonl`, `evals/cases.jsonl`, `evals/conditions.json`, `evals/jev_questions.json`, `.claude/jev.json`, its own earlier rows | `jev.jsonl` | yes, to Jev at `api.typesafe.ai` only after the opt-in; no `claude` calls | every current response has a current row (exit 0) |
| `evals/report.py` | all 4 row files, `evals/cases.jsonl`, `evals/conditions.json`, `evals/rubric.md`, `evals/jev_questions.json` | `report.md` | no | after 1 pass. With `--reference` and `--candidate`, it exits 0 when the gate passes, 1 when it fails, and 2 when it refuses; it also exits 2 when the run has no responses |

The stages also stop early:

- `evals/generate.py` stops with exit 0 and a partial run when the budget left falls below `MIN_CALL_USD`. It stops with exit 1 after `STOP_AFTER_FAILURES` failed rows in a row, for 1 condition or across conditions.
- `evals/judge.py` stops at the same budget cap, with exit 0, and after `STOP_AFTER_FAILURES` failed groups in a row, with exit 1.
- `evals/jev.py` stops after `STOP_AFTER` failures in a row with the same reason from `STOP_REASONS`. It still exits 0.

A stage writes a row only when it has no ok row under the current hash, so a
rerun resumes where the last run stopped. Only `evals/generate.py` has
`--retry-failed`. It skips a row that failed on its content, unless you pass
the flag. `evals/judge.py` sends a failed group again on every rerun.

With the 15 cases in `evals/cases.jsonl`, the default 3 trials, and the 3
conditions in `evals/conditions.json`, `evals/generate.py` makes 135 rows.
`evals/judge.py` then makes 45 group calls. Retries add more calls.

## The gate

`report.gate`, at `report.py:206`, compares a candidate condition with a
reference condition from the same run. It first refuses, with exit 2, when
the comparison has no fair basis:

- a reference or candidate response is out of date;
- `report.comparability` finds a difference in cases, trials, model, effort,
  rubric, or reported `models`, or a partial run;
- a lintable response has no current lint row;
- a gating Jev question has no answer for a response.

Then it applies 5 fixed checks, plus 1 check for each gating Jev question
that applies to a scored case. All of them must pass. Correctness and safety
share a row in this table:

| Check | The candidate passes when |
| --- | --- |
| blockers | it has no more blockers than the reference |
| correctness, safety | it scores at least the reference minus `TOLERANCE` (0.1) |
| weighted | it scores higher than the reference |
| lint errors | it has at most 10% more linter errors than the reference (`LINT_MARGIN`, `report.py:21`) |
| each gating Jev question | it has at most 1 more bad answer than the reference (`JEV_MARGIN`, `report.py:22`) |

The 2 margins came from the spread of 2 runs. The cycle 3 style ran twice,
and the 2 style texts differ by 1 sentence about caveats. Between the runs,
the linter errors moved from 36 to 42, and Jev flagged a different single
response in each run (`FINDINGS-2026-10-23-style3.md`). With no margin, the
gate failed a different rule in each run. The comment above `LINT_MARGIN`
records the same 2 runs. The margins came after those runs, from the spread
they showed, so 2 runs are their whole evidence.

## Jev

`evals/jev.py` asks Jev, the TypeSafe model, up to 5 yes-or-no questions per
response from
`evals/jev_questions.json`. It sends nothing unless `.claude/jev.json` holds
`"simple_english_eval": { "enabled": true }` and `TYPESAFE_API_KEY` holds a
key. Without the opt-in, each row stores the reason `not-opted-in`, and the
other stages still run. A tracked `.claude/jev.json` turns features on for
everyone who pulls it, so the evals README says to make the opt-in edit
locally and never commit it.

Each send holds the case prompt and the response, each cut to 4,000
characters (`CAP`). `jev.mask_home` hides the home folder and the user name,
then the contract client redacts the text. `evals/jev.py` loads the Python
client from `plugins/simple-english/evals/jev_client.py`, a byte-for-byte copy
of the session-tools client. The rules for every Jev
call are in the Jev contract of the development repository.

A Jev answer decides nothing until its question passes calibration.
`calibrate.py score` sets `gating` to true when Jev agrees with the user's
labels on at least 80% of items at 1 threshold (`PASS_AGREEMENT`), with at
least 3 "yes" and 3 "no" labels (`MIN_EACH`). Round 2 passed all 5 questions
(`FINDINGS-2026-10-23-calibration.md`), but with these limits:

- Every "yes" label for `invents_cause`, `filler`, `idiom`, and
  `drops_warning` came from a planted response. So the calibration shows
  that Jev catches obvious flaws, not subtle flaws in real responses.
- `filler` flagged 5 of 26 clean real responses at its 0.7 threshold. If a
  gate fails on `filler` alone, read the flagged responses before you trust
  the failure.
- `idiom` missed 4 of the 14 planted items.
- `invents_cause` and `drops_warning` each rest on 4 "yes" labels, 1 over
  the minimum.

## Invariants

- **No colon followed by a space in a `description:` field.** The colon ends
  the YAML key, and the frontmatter stops parsing. Claude Code then loads the
  skill with empty metadata, so the skill has no description to trigger on.
  `claude plugin validate` catches it (the development repository's CLAUDE.md).
- **Keep the 2 copies of `ste_lint.py` identical.** If they differ, the
  documents skill and the eval score text against different rules. No test
  checks this, so compare them with `cmp` after an edit.
- **Edit `evals/conditions.json` only for the length of a comparison.** The
  "Compare a rule change" steps add a condition such as `skill-next` there.
  If you commit that edit,
  `test_data.ConditionsTest.test_three_conditions_and_their_files_exist`
  fails, because `tests/test_data.py:66` asserts exactly `baseline`, `skill`,
  and `style`. A copy of the plugin with a `skill-next` condition and its `SKILL.md.next`
  file added failed 2 tests (7 when the `.next` file is missing). 19 tests read the file while they run, and
  `tests/test_calibrate.py` reads it once at import. Also, `evals/report.py`
  reads the live file (`report.py:366`), so run the report before you revert
  the edit.
- **Claude never fills in `labels.jsonl` values.** Calibration measures Jev
  against a person, not against another model (the docstring of
  `evals/calibrate.py`). No code check finds a label that a model wrote. So
  a filled-in sheet makes `calibrate.py score` turn on gating questions that
  no person checked.
- **Do not open `sample-key.jsonl` before you label.** It names the condition
  of each item, so the labels stop being blind.
- **Get the user's approval before a turn with more than 20 model calls.**
  One unapproved test run made 215 calls and used up the rest of the
  user's 5-hour usage window (the development repository's CLAUDE.md). A default
  `evals/generate.py` run makes 135 rows, so every paid eval run needs approval and a
  `--budget-usd` cap.
- **Run `evals/generate.py` and `evals/judge.py` one after the other.** Each
  stage reads the spend in the run folder once, when it starts. 2 stages that
  run together do not see each other's spend, so together they can spend up
  to 2 times the cap.
- **After an edit to a case, `evals/conditions.json`, a condition file, the
  rubric judge block, the linter or `evals/lint.py`, a Jev question text, or
  `NO_TOOLS_NOTE`, rerun every stage in order.** The gate refuses a run
  with out-of-date responses, missing scores, missing lint rows, or missing
  gating Jev answers. The "Stale rows" section of the
  [evals README](../../../plugins/simple-english/evals/README.md#stale-rows)
  lists which edit makes which rows stale.

## Sources

- [FINDINGS-2026-10-20.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-20.md)
- [FINDINGS-2026-10-21-cycle2.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-21-cycle2.md)
- [FINDINGS-2026-10-22-cycle3.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-22-cycle3.md)
- [FINDINGS-2026-10-22-style.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-22-style.md)
- [FINDINGS-2026-10-23-calibration.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-23-calibration.md)
- [FINDINGS-2026-10-23-style3.md](../../../plugins/simple-english/evals/FINDINGS-2026-10-23-style3.md)
