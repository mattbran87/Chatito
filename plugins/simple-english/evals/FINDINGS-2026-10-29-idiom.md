# Findings: idiom rule, 2026-10-29

This cycle tests a new idiom rule in `output-styles/simple-english.md.next` against the shipped style. The rule replaces the fixed-phrase idiom bullet with a picture test, and its Self-Check step uses a word-by-word translation test. The run uses `claude-opus-5-5` at `medium` effort, all 20 cases, and 4 trials. The full report stays in `~/.claude/simple-english-evals/idiom-run1/`.

Design: `docs/superpowers/specs/2026-10-29-simple-english-idiom-design.md`, in the development repository.

## Decision

**The user shipped the rule.** It passed all 3 success measures in the spec. The `report.py` gate failed on lint only. The lint rise comes from passive voice and present perfect in the replies, not from the rule.

**The run does not show that the new rule beats the shipped style on the Jev `idiom` rate.** The shipped style drew 5 flags in 72 answers in this run, against 14 in 92 pooled over the structure runs. A gap of 1 flag is noise.

## Result

| Measure | `style` | `style-next` |
| --- | ---: | ---: |
| Jev `idiom` flags at 0.5 | 5 of 72 (6.9%) | 4 of 72 (5.6%) |
| Jev `idiom` flags at 0.6 | 3 of 72 | 0 of 72 |
| Mean Jev `idiom` score | 0.289 | 0.275 |
| Weighted judge score | 4.651 | 4.686 |
| Readability | 4.737 | 4.787 |
| Blockers | 6 | 6 |
| Linter errors | 37 | 43 |
| Gate | — | Failed: lint |

| Success measure | Pass condition | Result |
| --- | --- | --- |
| Jev `idiom`, `style-next` | 7 or fewer flags in 72 answers at 0.5 | Pass: 4 |
| Weighted judge score | `style-next` at or above `style` | Pass: 4.686 against 4.651 |
| Over-correction | No standard term rewritten in the hand-read set | Pass, with 1 borderline case |

## The flagged replies

All 4 flagged `style-next` replies score from 0.50 to 0.52. A hand read found these likely triggers:

| Reply | Score | Likely phrases |
| --- | ---: | --- |
| `explain-rebase` trial 2 | 0.52 | "Clean up a private branch," which is standard git wording |
| `causal-chain` trial 2 | 0.51 | "the stale window," "the old price returns to its full one-hour window" |
| `risky-unverified` trial 2 | 0.50 | "where the nightly database lives," "it lives outside Docker" |
| `diagnose-clear` trial 3 | 0.50 | "the defect sits between the helper call and the request" |

"Lives" and "sits" are the clearest misses. They describe data and a defect as if each had a home, and the translation test did not catch them.

## Over-correction

The hand read covered the 4 `plain-answer` replies and the 10 replies that the judge scored lower than their `style` pair on readability.

- **"Code path" fell from 5 uses to 0.** `style-next` writes "input path" in its place, as in "One input path breaks." The new term is less standard, but it is not a long paraphrase.
- **"Stale" fell from 14 uses to 7,** and the remaining uses are field terms, such as "the stale window." The rule did not strip the term.
- **The judge's notes name no lost technical term.** They name factual slips, wordiness, and 1 unclear tense.
- **2 cases dropped for a reason that the rule does not cause.** `plain-answer` fell from 4.925 to 4.625, because 2 of 4 replies added a paragraph about 410 Gone. `casual-thanks` fell from 4.975 to 4.575, because 1 reply added an explanation that the user did not ask for.

## Lint

The gate allows 10% more linter errors than the reference, and `style-next` has 16% more. `doc-british` holds 27 and 28 of the errors, because the case plants British spellings on purpose. Outside that case, the rise comes from passive voice (11 against 8) and present perfect (4 against 2). The new rule text holds neither construction.

## The probe before the run

A probe on 6 cases at 2 trials compared 2 versions of the rule. Both used the picture test in the rule. The check step used the picture test in one version and the translation test in the other. The translation-test version drew 0 flags in 12 answers, the picture-test version 2, and the shipped style 3. In a hand read, the picture-test version wrote "live checkout behavior," and "live" is one of the rule's own examples. The design records the probe in full.

## Cost

| Item | Cost |
| --- | --- |
| Probe | $2.82 generation, 36 Jev requests |
| Run | $11.01 generation, $3.38 judge |
| Jev | 144 requests in the run, because `toast` and `casual-thanks` send none |
| Jev decision run | 18 requests |
