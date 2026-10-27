# Findings: skill caveat line, 2026-10-26

The `simple-english` skill does not get the style's caveat line. The gate failed on linter errors, and the user chose to follow the gate.

The candidate added 1 sentence to check item 1 of `skills/simple-english/SKILL.md`. It copied the sentence from the output style: "A caveat about what you cannot see, such as "I cannot see your code," comes after the first sentence, never before it." The style got this line in cycle 3, after a `diagnose-clear` response opened with that caveat (`FINDINGS-2026-10-23-style3.md`).

## Run: `2026-10-26-caveat`

15 cases, 4 trials, `claude-opus-5-5` at `medium` effort, conditions `skill` and `skill-next` only. The 60 `skill` responses are the `skill-next` rows of `2026-10-22-cycle3b`, copied under the name `skill`. Each one matched the current `SKILL.md` through `response_hash` before the copy.

| Rule | skill | skill-next | Result |
| --- | ---: | ---: | --- |
| Blockers | 9 | 7 | pass |
| Correctness | 4.217 | 4.450 | pass |
| Safety | 4.933 | 4.950 | pass |
| Weighted score | 4.532 | 4.671 | pass |
| Linter errors | 34 | 42 | **fail**, the margin allows 37 |
| Jev `answers_first` | 1 of 20 | 0 of 20 | pass |
| Jev `filler` | 3 of 52 | 1 of 52 | pass |

The other 3 Jev questions passed with equal or lower rates.

## Where the linter errors came from

The 8 extra errors fall in 5 cases: `explain-rebase` +3, `diagnose-partial` +2, `diagnose-clear` +1, `doc-postmortem` +1, and `doc-british` +1. None of them is in a sentence that the new line governs. The `passive` and `perfect` counts rose, and `canonical`, `modal`, and `vague` fell.

This spread matches the noise that set `LINT_MARGIN`: 2 style runs on near-identical text moved from 36 to 42 errors. So the result does not show that the sentence harms the skill. It also does not show a benefit large enough to clear the gate. The `answers_first` gain is 1 response in 20.

## Decision

Follow the gate. The skill keeps its current check item 1. Revisit only if a real reply shows the skill opening with a caveat. A second run of `skill-next`, about 120 calls, would settle whether the linter result is noise.

## Cost

120 new Claude calls, 0 failed: $4.53 for generation and $2.43 for the judge, $6.97 against an $8 cap. The run folder also records $4.50 of cost on the copied rows, so `--budget-usd` was 12.5. Jev scored 104 responses on TypeSafe.
