# simple-english enhancement ideas

Updated: 2026-10-26

This list holds 17 candidate enhancements for the simple-english plugin. The first draft comes from the limits sections of the 6 findings files in `plugins/simple-english/evals/` and the 2026-10-23 handoff. Add a row when real use shows a rule that reads wrong.

The **Cost** column says what an idea needs before it can ship:

- **free**: edits and unit tests only.
- **paid run**: a generate and judge run, which the user approves and caps.
- **labels**: the user labels a calibration sheet.

## Rules and wording

| Idea | Evidence | Cost |
| --- | --- | --- |
| Add the style's caveat line to the skill: a caveat about what you cannot see comes after the first sentence | The style failed `jev answers_first` on a `diagnose-clear` reply that opened with "I cannot see your code". The skill's cycle 3 gate passed without the line. | paid run |
| Lift `diagnose-clear` above its score of about 4.0 | It stays near 4.0 in cycle 3 for both rule versions. No rule targets it yet. | paid run |
| Give replies that mix a social sentence with an explanation their own guidance | Cycle 2 added one warm opening sentence for `casual-thanks`, which rose from 3.95 to 4.89. Mixed replies have no case. | paid run |
| Collect rules that read wrong in real use | The handoff's next step: 2 or 3 real replies over about one week. | free |

## Eval harness

| Idea | Evidence | Cost |
| --- | --- | --- |
| Revisit `LINT_MARGIN` and `JEV_MARGIN` in `report.py` against the spread of later runs | Both margins came from the spread of 2 style runs, and were set after those runs. | free, once later runs exist |
| Add more trials per case, or report a per-case confidence interval | The 2026-10-20 baseline showed a per-case standard deviation up to 0.95. 3 trials cannot separate overall gaps of 0.08 to 0.10 from noise. | paid run |
| Add a second judge model | The judge is the same model that writes the responses. Jev is the only cross-model check, and it is only partly calibrated. | paid run |
| Add a non-circular readability measure, for example a reading-grade score | The linter checks the skill's own rules. It shows that a rule took effect, not that the prose reads better. | free |
| Make the rule-text comparison a flag, not a hand edit of `conditions.json` | A temporary condition makes 2 tests fail, or 7 if its new file is missing, as measured in `docs/architecture/simple-english/deep-dive.md`, and `report.py` needs the run's own copy of the file. | free |
| Copy reusable rows automatically when a condition's text matches an earlier run | `input_hash` depends on the text, not the name. Rows are copied by hand today, and the copied cost still counts against `--budget-usd`. | free |
| Add a test that fails when the 2 copies of `ste_lint.py` differ | `README.md` says the copies in `skills/simple-english/scripts/` and `skills/simple-english-docs/scripts/` must stay identical, but no test compares them. The Jev client copies each have such a test. | free |

## Jev calibration

| Idea | Evidence | Cost |
| --- | --- | --- |
| Label real responses that carry subtle flaws | Every "yes" label for `invents_cause`, `filler`, `idiom`, and `drops_warning` came from a planted response. | labels |
| Raise the `filler` threshold, or reword its question | Jev flagged 5 of 26 clean real responses as filler at 0.7. A false alarm can fail the gate for a good rule change. | labels, then free |
| Reword the `idiom` question, or add idiom examples to it | Jev missed 4 of 14 planted idioms. | labels |
| Add "yes" labels for `invents_cause` and `drops_warning` | Each rests on 4 "yes" labels, just over the minimum of 3. | labels |

## Coverage gaps

| Idea | Evidence | Cost |
| --- | --- | --- |
| Run `simple-english-docs` and `references/documents.md` as their own condition | Neither has had its own run. Their edits copy text that passed the skill and style gates. | paid run |
| Add more document cases | Only 4 of the 15 cases are documents. | free to write, paid to run |

## Open questions

- [ ] Does Jev catch subtle flaws in real responses? The "subtle flaws" labeling row answers it.
- [ ] Is a gate failure on `filler` alone ever real? Read the flagged responses at the next failure.
- [ ] Which ideas are worth a paid run? Pick after the week of real use, and state a cap per run.
