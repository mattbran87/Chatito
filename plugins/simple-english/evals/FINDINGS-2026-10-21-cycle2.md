# Findings: cycle 2, 2026-10-21

Cycle 2 tests `skills/simple-english/SKILL.md.next` against the current `SKILL.md`. 15 cases, 4 trials, `claude-opus-5-5` at `medium` effort. The full reports stay in `~/.claude/simple-english-evals/2026-10-21-cycle2/` and `2026-10-21-cycle2b/`.

## Result

The gate passed twice. The second draft wins on every gate rule, with a 0.33 gain in the weighted score and 4 fewer blockers.

| Measure | skill | skill-next (run 1) | skill-next (run 2) |
| --- | ---: | ---: | ---: |
| Weighted judge score | 4.288 | 4.508 | 4.618 |
| Correctness | 3.983 | 4.150 | 4.300 |
| Readability | 4.517 | 4.700 | 4.783 |
| Concision | 3.517 | 4.333 | 4.483 |
| Safety | 4.867 | 4.817 | 4.833 |
| Blockers | 10 | 9 | 6 |
| Linter errors (56 responses) | 55 | 35 | 38 |

The `skill` column comes from run 2. Run 2 reused the 60 `skill` responses from run 1, so only the judge scores differ between the runs.

## What the draft changes

1. No preamble, recap, or closer, and no change list after a rewrite unless the request asks for one.
2. The literal phrase, not an idiom.
3. A check of the first line and the last line before you send.
4. The rules hold for the whole conversation.
5. Anything the request, a template, or a tool requires wins over every rule. This covers a required `Resolves:` line.
6. Out-of-scope work, such as a toast, gets no remark about the rules.
7. "Note the exception" changes to "do not tell the reader about the rule you set aside".
8. A precise count only when you know it.

Run 1 found 2 problems, and run 2 tested the fix for both:

- **The no-closer rule dropped caveats.** In `commit-refactor`, 3 of 4 responses stated guessed function roles as fact. The draft now says a caveat is content, not a closer. In run 2, all 4 responses flag the guesses.
- **Social replies read curt.** `casual-thanks` scored 3.95 in run 1. The draft now allows one warm opening sentence. Run 2 scores 4.89.

## Limits

- **Rule 8 had no effect.** 2 of 4 `explain-rebase` responses still give the wrong "90 days" reflog default in both versions.
- **`destructive-clean` stays low in both versions, at 3.8.** The delete command comes before the dry run. Neither version fixes that.
- **The style draft is untested.** `output-styles/simple-english.md.next` carries the same edits, but no run covered it.
- The noise and one-judge limits in `FINDINGS-2026-10-20.md` still apply.

## Cost

Run 1 cost $10.76. Run 2 cost $6.77 of new calls, because it reused the run 1 `skill` responses. Jev cost about $0.02 across both runs.
