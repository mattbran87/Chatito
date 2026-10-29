# Findings: structure rules, 2026-10-29

This cycle tests keyword labels, an emphasis rule, and a form table in `output-styles/simple-english.md.next` against the shipped style. All runs use `claude-opus-5-5` at `medium` effort, with 4 trials. The full reports stay in `~/.claude/simple-english-evals/`, in `structure-run1/`, `structure-run2/`, and `structure-run1b/`.

| Run | Cases | Draft |
| --- | --- | --- |
| `structure-run1` | The 5 new structure cases | First draft |
| `structure-run2` | The 15 old cases | First draft |
| `structure-run1b` | The 5 new structure cases | Draft after `9f6585f`, which limits labels |

## Decision

**The user shipped the draft over a failed gate.** Every run failed 1 or more gate rules, and every run raised the weighted judge score. Each failed rule differs by 1 to 5 answers. The `idiom` rule failed twice, and a chunk test traced it to real idioms that the shipped rules already ban. The fix for those belongs to the word rules, so it moves to a separate cycle.

## Result

| Measure | Run 1: style | Run 1: next | Run 2: style | Run 2: next | Run 1b: style | Run 1b: next |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Weighted judge score | 4.560 | 4.680 | 4.598 | 4.653 | 4.600 | 4.715 |
| Correctness | 4.600 | 4.700 | 4.317 | 4.400 | 4.800 | 4.800 |
| `structure` dimension | 4.100 | 4.350 | 4.733 | 4.650 | 3.950 | 4.350 |
| Blockers | 1 | 0 | 6 | 5 | 0 | 1 |
| Linter errors | 2 | 6 | 36 | 36 | 2 | 4 |
| Jev `idiom` bad answers | 2 of 20 | 2 of 20 | 5 of 52 | 7 of 52 | 2 of 20 | 5 of 20 |
| Gate | Failed: lint | — | Failed: `idiom` | — | Failed: blockers, lint, `idiom` | — |

Run 1b judged the `style` responses again, so its `style` scores differ from run 1.

## What failed, and why

- **Linter errors in runs 1 and 1b.** No error comes from a structure rule. All are passive voice, present perfect, or modal hits. The gate allows 10% more errors than the reference. On a base of 2, that margin allows 0.2, so 1 extra error fails. Run 2 has a base of 36, and there the 2 styles tie.
- **The blocker in run 1b.** 1 draft response claimed that `docker volume ls -f dangling=true` lists every volume a prune deletes. The prune first deletes stopped containers, which frees their volumes too. This is a factual slip that no label rule causes.
- **Jev `idiom` in runs 2 and 1b.** Pooled over the 3 runs, the draft has 14 flags in 92 answers and `style` has 9. At a cut of 0.6, both have 5. All of the draft's extra flags score from 0.50 to 0.59.

## The idiom tests

**Labels do not cause the flags.** 16 Jev calls asked the `idiom` question on 8 flagged draft responses, with and without the label words. Removing the labels moved each answer by 0.06 or less.

**Real idioms cause most flags.** 62 Jev calls split 5 flagged responses into paragraphs and list items. 8 chunks scored 0.5 or above:

| Score | Phrase |
| ---: | --- |
| 0.77 | "the old key is dead" |
| 0.76 | "the fastest path to a firm answer" |
| 0.66 and 0.65 | "Split the browser and CDN lifetimes" |
| 0.58 | "leaves the old price live" |
| 0.56 | "Browsers check back on each visit" |
| 0.52 | "ran clean for hours, look harder at" |
| 0.51 | "can run side by side" |

"lifetimes" is a likely false positive, because cache lifetime is a standard term. "old key" and "rollback" are not triggers: chunks that use them in plain sentences score 0.26 to 0.36. A short chunk gives Jev less context than a whole reply, so a chunk score shows where a flag comes from, not how much it adds.

## Labels

- Run 1 used 26 labels in 20 draft responses, and 3 CAUTION labels gave advice rather than mark a risk. Run 2 put a plain `UNVERIFIED:` line in a commit message.
- Commit `9f6585f` adds 2 limits. A label marks a risk or a gap, never advice. `BLOCKED`, `ACTION`, `UNVERIFIED`, and `ASSUMED` stay out of commits, code comments, and documents for other readers.
- Run 1b still used 26 labels, but most CAUTION labels now name the harm. 1 rate-limit CAUTION is still close to advice.
- No `plain-answer` response in any run carries a label.

## Limits

- **Jev `table_missed` gives false answers.** It flagged all 8 `compare-options` responses in run 1, and each of them holds a table. Rewrite the question before anyone uses its rate.
- **Jev `label_misgraded` disagrees with a hand read.** It flagged 3 of 4 draft `risky-unverified` responses in run 1, but the WARNING and CAUTION grades in them follow the table.
- **The `risky-unverified` criteria do not ask for labels.** Only the `structure` dimension and Jev see label use there.
- **The draft labels more often than the spec intends.** About 1.3 labels per response on the 5 new cases, which all carry risk by design. Run 2 does not count labels.

## Cost

| Item | Cost |
| --- | --- |
| Run 1 | $2.63 generation, $0.93 judge |
| Run 2 | $7.14 generation, $2.49 judge |
| Run 1b, new calls only | $2.38 generation, $0.92 judge |
| Jev | 242 calls: 40, 104, and 20 in the runs, 16 in the label test, 62 in the chunk test |

The 3 runs cost $16.49 in subscription calls.
