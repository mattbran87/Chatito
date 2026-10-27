# Findings: cycle 3, 2026-10-22

Cycle 3 tests 3 new rules in `skills/simple-english/SKILL.md.next` against the shipped cycle 2 skill. 15 cases, 4 trials, `claude-opus-5-5` at `medium` effort. Both runs reused 60 `skill` responses from `2026-10-21-cycle2b`, which came from the same text. The full reports stay in `~/.claude/simple-english-evals/2026-10-22-cycle3/` and `2026-10-22-cycle3b/`.

## Result

Run 1 failed the gate on linter errors, 43 against 38, and passed the 4 judge rules. Run 2 narrowed one rule and passed every gate rule.

| Measure | skill | skill-next (run 2) |
| --- | ---: | ---: |
| Weighted judge score | 4.543 | 4.707 |
| Correctness | 4.283 | 4.533 |
| Safety | 4.833 | 4.983 |
| Blockers | 5 | 3 |
| Linter errors (56 responses) | 38 | 34 |

## The 3 rules

1. **A destructive command comes after its preview, with a step to read the output.** `destructive-clean` rises from 3.86 to 4.70. Every earlier run scored this case lowest.
2. **No configurable default, limit, timeout, or retention period from memory.** All 4 `explain-rebase` responses name `gc.reflogExpireUnreachable`, and none says "90 days". In run 1 the rule also made `direct-answer` add a check query to a well-known value, and that case fell by 0.45. Run 2 limits the rule to configurable values, and `direct-answer` scores 4.96. The rule's example uses HTTPS port 443, not the Postgres port in the test case.
3. **The hard floor keeps the words that set the risk, such as "quietly" and "only".** All 4 `doc-status-rollback` responses keep "quietly", against 3 of 4 for the reference. The case score did not move, because the reference scored 4.95 in this run.

## Limits

- **The linter gap in run 1 looks like noise.** The 5 extra errors spread across 3 cases that no new rule targets. Run 2 reversed the gap.
- **Jev's `idiom` rate rose from 0.077 to 0.135.** Jev is not calibrated, so this rate decides nothing.
- `diagnose-clear` stays near 4.0 in both versions.

## Cost

Run 1 cost $6.84 of new calls, and run 2 cost $6.93.
