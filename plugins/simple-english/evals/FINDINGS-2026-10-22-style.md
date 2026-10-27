# Findings: style run, 2026-10-22

Run id `2026-10-22-style` tests `output-styles/simple-english.md.next` against the current style. 15 cases, 4 trials, `claude-opus-5-5` at `medium` effort. The run reused the 45 `style` responses from `2026-10-20-baseline-2` for trials 1 to 3. The full report stays in `~/.claude/simple-english-evals/2026-10-22-style/report.md`.

## Result

The gate passed. The draft carries the same edits as the cycle 2 skill. See `FINDINGS-2026-10-21-cycle2.md`.

| Measure | style | style-next |
| --- | ---: | ---: |
| Weighted judge score | 4.312 | 4.668 |
| Correctness | 4.050 | 4.483 |
| Readability | 4.517 | 4.833 |
| Concision | 3.717 | 4.433 |
| Safety | 4.867 | 4.800 |
| Blockers | 17 | 4 |
| Linter errors (56 responses) | 42 | 40 |

- **The `toast` failure is fixed.** It scores 5.00, against 3.94.
- `doc-british` rises by 1.00, `commit-bugfix` by 1.06, and `casual-thanks` by 0.60.

## Limits

- **`commit-refactor` falls by 0.22.** All 4 draft responses keep the caveat about guessed descriptions. The loss comes from an unflagged claim that `parseConfig` calls the helpers in order. The old style makes the same claim in 2 of 4 responses.
- **`doc-status-rollback` falls by 0.15.** Both versions drop "quietly" from the fallback warning in 3 of 4 responses. That gap is a candidate for the next cycle.
- **`destructive-clean` stays low in both versions, at 3.4.**

## Cost

$6.30 of new calls. The run folder records $8.51, which includes the $2.21 of reused responses.
