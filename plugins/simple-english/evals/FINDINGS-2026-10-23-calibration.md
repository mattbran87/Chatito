# Findings: Jev calibration round 2, 2026-10-23

Run id `2026-10-23-calibration`. All 5 Jev questions passed calibration, so each one now gates.

## Method

Round 1 (`2026-10-20-baseline-2`) judged no question, because the 20 real responses held almost no "yes" labels. Round 2 kept those 20 items and their labels and added 21 items:

- 7 real baseline responses, picked by hash, not by Jev score.
- 14 hand-written responses from `calibration/planted-2026-10-23.jsonl`. Most hold planted flaws, and 2 are clean controls.

The new items came in a hashed order, and the person who labelled them did not see which were planted. Claude wrote the planted responses but no labels. 40 of 41 items carry labels.

## Result

| Question | Agreement | Threshold | Real items | Planted items |
| --- | ---: | ---: | --- | --- |
| `answers_first` | 90% | 0.5 | 11 of 13 | 8 of 8 |
| `invents_cause` | 100% | 0.5 | 8 of 8 | 5 of 5 |
| `filler` | 88% | 0.7 | 21 of 26 | 14 of 14 |
| `idiom` | 85% | 0.5 | 24 of 26 | 10 of 14 |
| `drops_warning` | 95% | 0.5 | 13 of 13 | 5 of 6 |

## Limits

- **Every "yes" for `invents_cause`, `filler`, `idiom`, and `drops_warning` comes from a planted response.** The real responses were all labelled "no". So the calibration shows that Jev catches obvious flaws. It does not show that Jev catches subtle flaws in real responses.
- **`filler` gives false alarms.** Jev flagged 5 of 26 clean real responses at the 0.7 threshold. A false alarm can now fail the gate for a good rule change. If a gate fails on `filler` alone, read the flagged responses before you trust the failure.
- **`idiom` misses idioms.** Jev missed 4 of the 14 planted items.
- **`invents_cause` and `drops_warning` rest on 4 "yes" labels each**, just over the minimum of 3.

## Cost

14 Jev calls, under $0.01. No Claude calls.
