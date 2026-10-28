# simple-english workflows

This page holds 6 diagrams in 5 sections: the runtime path that puts the rules in context,
the eval pipeline, row reuse and stale rows, the rule-change cycle, and Jev
calibration. The file and entity names match the
[data model](data-model.md).

## Runtime path

A reply gets the rules by 1 of 2 routes. In route 1, a skill triggers on its
`description`. In route 2, the user selects the output style. Only a document
written under a skill gets a linter pass. A chat reply gets none, and the
output style has no lint step.

```mermaid
flowchart TD
    P["User prompt"] --> R1{"Route 1: does a skill description match the task, or /simple-english:simple-english?"}
    P --> R2{"Route 2: is outputStyle set to simple-english:simple-english?"}
    R1 -->|"any expository prose"| S1["skills/simple-english/SKILL.md loads"]
    R1 -->|"project document only"| S2["skills/simple-english-docs/SKILL.md loads"]
    R2 -->|"yes, from /output-style"| OS["output-styles/simple-english.md applies to every reply"]
    S1 --> C["Rules in context"]
    S2 --> C
    OS --> C
    C --> D["Claude drafts the text under the rules"]
    D -->|"chat reply"| F(["Reply sent"])
    D -->|"document, output style only"| F
    D -->|"document, from simple-english"| REF["load skills/simple-english/references/documents.md"]
    D -->|"document, from simple-english-docs"| L
    REF --> L["Self-Check: ste_lint.py, fix ERRORs, judge reviews, rerun with --quiet"]
    S1 -.->|"Claude Code: arms"| H["hooks/register.ts lints each .md Write or Edit, 2 passes per file"]
    S2 -.->|"Claude Code: arms"| H
    H -.-> L
    L --> F
```

The rules live in `skills/simple-english/SKILL.md`,
`skills/simple-english-docs/SKILL.md`, and `output-styles/simple-english.md`.
Each skill carries its own copy of the linter, in
`skills/simple-english/scripts/ste_lint.py` and
`skills/simple-english-docs/scripts/ste_lint.py`. Neither SKILL.md sets
`allowed-tools`.

In Claude Code, `hooks/register.ts` runs the linter without a step from
Claude. A `skill.prompt` hook, or a `tool.call` hook on the `Skill` tool, arms
it when either skill loads. Then a `tool.call` hook on `Write` and `Edit` runs
`skills/simple-english-docs/scripts/ste_lint.py --quiet` on each Markdown file,
at most 2 times per file, and adds the output to the tool result's `context`.
The armed flag and the pass counts live in `$.state`, declared in
`types/index.d.ts`.

## Eval pipeline

5 stages run in order. The first 4 stages append rows to the run folder.
`report.py` rewrites `report.md`.

```mermaid
flowchart TB
    subgraph repo["Repository: plugins/simple-english/"]
        cf["skills/simple-english/SKILL.md and output-styles/simple-english.md"]
        lt["skills/simple-english/scripts/ste_lint.py"]
        rq["evals/rubric.md and evals/jev_questions.json"]
        jc[".claude/jev.json"]
    end
    subgraph run["Run folder: ~/.claude/simple-english-evals/#lt;run-id#gt;/"]
        resp["responses.jsonl"]
        lintj["lint.jsonl"]
        scores["scores.jsonl"]
        jevj["jev.jsonl"]
        rep["report.md"]
    end
    gen["generate.py --budget-usd"]
    lint["lint.py"]
    judge["judge.py --budget-usd"]
    jev["jev.py"]
    report["report.py --reference --candidate"]
    api["api.typesafe.ai"]
    gate(["exit code: 0 passed or no gate, 1 failed, 2 refused or no responses"])

    cf --> gen
    gen --> resp
    resp --> lint
    lt --> lint
    lint --> lintj
    resp --> judge
    rq -->|"rubric.md"| judge
    judge --> scores
    resp --> jev
    rq -->|"jev_questions.json"| jev
    jc -->|"opt-in"| jev
    jev <-->|"prompt and response, cut and redacted"| api
    jev --> jevj
    resp & lintj & scores & jevj & rq --> report
    report --> rep
    report --> gate
```

Every stage reads `evals/cases.jsonl` and `evals/conditions.json`. Every stage
also reads the condition files: `lint.py`, `judge.py`, `jev.py`, and
`report.py` read them through `common.split_out_of_date`, which calls
`common.condition_text`. `generate.py` and `judge.py` read the spend of the
run from `common.spent`, which adds the cost in both `responses.jsonl` and
`scores.jsonl`. The stages are `evals/generate.py`, `evals/lint.py`,
`evals/judge.py`, `evals/jev.py`, and `evals/report.py`. Shared code is in
`evals/common.py`.

## Row reuse and stale rows

A rerun makes a call only for a row that is missing, failed, or out of date.
The first diagram follows `generate.py`. The second follows the later stages
and `report.py`.

```mermaid
flowchart TD
    G["generate.py: next case_id, trial, condition"] --> H{"stored input_hash =<br/>common.response_hash?"}
    H -->|"no, or no row"| B
    H -->|"yes"| OK{"Row ok?"}
    OK -->|"yes"| SKIP(["Skip: keep the row, no call"])
    OK -->|"no"| CE{"error in CONTENT_ERRORS<br/>and no --retry-failed?"}
    CE -->|"yes, counted as skipped"| SKIP
    CE -->|"no"| B{"budget_usd - spent<br/>below MIN_CALL_USD?"}
    B -->|"yes"| STOPB(["Stop: budget cap, run is partial, exit 0"])
    B -->|"no"| CALL["claude call, up to 3 tries, with --max-budget-usd from common.call_budget,<br/>then append a row to responses.jsonl"]
    CALL --> FS{"STOP_AFTER_FAILURES failed rows<br/>in a row, for 1 condition<br/>or across conditions?"}
    FS -->|"yes"| STOPF(["Stop: print common.stop_message, exit 1"])
    FS -->|"no"| MADE(["Call made: append a row, go to the next row"])
```

```mermaid
flowchart TD
    LS["lint.py, judge.py, jev.py: next response"] --> SO{"common.split_out_of_date:<br/>input_hash current?"}
    SO -->|"no"| SKIPO(["Skip: no call and no row, rerun generate.py"])
    SO -->|"yes"| TH{"stored row ok, and its<br/>text_hash or group_hash<br/>equals the current hash?"}
    TH -->|"yes"| SKIP(["Skip: keep the row, no call"])
    TH -->|"no"| MADE(["Call made: append a row, go to the next row"])
    RG["report.py --reference --candidate"] --> LEAVE["Leave out stale score, lint, Jev rows and count them"]
    LEAVE --> RO{"out-of-date response,<br/>partial run or mismatch,<br/>missing lint row, or<br/>missing gating Jev answer?"}
    RO -->|"yes"| REF(["Refuse: gate exit 2"])
    RO -->|"no"| CHK(["The gate checks: exit 0 if all pass, exit 1 if not"])
```

`report.py` leaves out the stale rows before the gate runs. So a stale lint
row counts as a missing lint row, and the gate refuses. A stale score row
makes the run partial, and `comparability` refuses.

`generate.py` compares `input_hash` itself. `judge.py` has the same budget
check and the same `STOP_AFTER_FAILURES` stop, with 1 count, but it has no
`--retry-failed` flag: it sends a failed group again on every rerun. `jev.py`
stops after `STOP_AFTER` failures in a row with the same reason from
`STOP_REASONS`. `calibrate.py sample` also leaves out out-of-date responses,
but it keeps no rows: it rewrites its 3 files each time it picks at least 1
item. The code is in
`evals/generate.py`, `evals/judge.py`, `evals/jev.py`, `evals/report.py`, and
`evals/common.py`.

## Rule-change cycle

A rule change runs as a new condition beside the current one. The gate in
`report.py` decides if the new text ships.

```mermaid
flowchart TD
    E["Edit a copy of the rule file, such as skills/simple-english/SKILL.md.next"] --> C["Add a condition to evals/conditions.json, such as skill-next"]
    C --> R["Run generate.py, lint.py, judge.py, jev.py (new run id the first time)"]
    R --> G["report.py --run-id id --reference skill --candidate skill-next"]
    G --> X{"Gate exit code"}
    X -->|"2: refused"| FIX["Fix the cause that the gate names, such as an out-of-date response"]
    FIX --> R
    X -->|"0: passed, or 1: failed"| FD["Write evals/FINDINGS-date.md"]
    FD -->|"passed"| SHIP(["Ship: copy .next into the rule file, delete .next, carry the text to the other rule files, add a CHANGELOG.md entry"])
    FD -->|"failed, revise the draft"| E
```

The steps are in the "Compare a rule change" and "Results" sections of
`evals/README.md`. The gate rules, `LINT_MARGIN`, and `JEV_MARGIN` are in
`evals/report.py`. The ship step comes from commit `b368a57`. It copied the
cycle 3 draft into `skills/simple-english/SKILL.md`, deleted the draft, and
carried the same text to `output-styles/simple-english.md` and
`skills/simple-english-docs/SKILL.md`. It also added a `CHANGELOG.md` entry.
Both failed gates so far led to a revised draft, so the diagram shows no
other path.

## Jev calibration

`calibrate.py` has 2 subcommands, `sample` and `score`. The user labels the
sheet between them.

```mermaid
sequenceDiagram
    participant Claude
    participant C as calibrate.py
    participant User
    Note over C: sample reads responses.jsonl, score also reads jev.jsonl
    Claude->>C: calibrate.py sample --run-id id
    C->>C: drop out-of-date responses, pick up to 20 items with diagnose-clear and diagnose-partial under every condition
    alt no current response
        C-->>Claude: exit 1, nothing written
    else items picked
        C-->>Claude: write sheet.md, blank labels.jsonl, and sample-key.jsonl, exit 0
    end
    Claude->>User: read sheet.md, then fill in labels.jsonl
    Note over Claude: Claude never fills in label values. A model must not fill in this sheet.
    User->>User: set each label to yes, no, or blank, without opening sample-key.jsonl
    User->>Claude: the labels are done
    Claude->>C: calibrate.py score --run-id id
    C->>C: validate_labels, then changed_items against text_hash in sample-key.jsonl
    alt missing file, bad value, no yes or no label, or changed response
        C-->>Claude: exit 1, nothing written
    else labels valid
        C-->>Claude: 1 line per question, write gating and threshold into jev_questions.json, exit 0
    end
    Claude->>User: commit the changed jev_questions.json
```

The code is in `evals/calibrate.py`: `write_sample` for `sample`, and
`validate_labels`, `changed_items`, `score`, and `apply` for `score`. A
question passes at `PASS_AGREEMENT` agreement with at least `MIN_EACH` "yes"
and `MIN_EACH` "no" labels. The steps are in the "Calibrate Jev" section of
`evals/README.md`.
