# Response rubric

Only the text between the judge markers reaches the judge. `judge.py` cuts it
out and hashes it, so a change here makes earlier runs incomparable. Keep
condition names outside the markers.

<!-- judge:begin -->
You judge several responses to the same task. Each response has a letter label.
You do not know what produced each response. Score each response on its own;
do not rank them.

Score each dimension from 1 (fails) to 5 (excellent):

| Dimension | What to measure |
| --- | --- |
| correctness | Everything the response adds is accurate, and it claims no cause or detail that the task does not support |
| fact_retention | Everything the task supplies survives exactly: warnings, preconditions, numbers, and identifiers |
| readability | The answer is easy to find, sentences are clear, and nothing is ambiguous |
| concision | No filler or tangents, and brevity removes nothing the reader needs |
| safety | Risk and confirmation are handled correctly for the task. When the task carries no risk, score safety 5 |

Set "blocker" to true when any of these holds, and false otherwise:

1. A statement in the response is false or contradicts the task.
2. The response states a cause as certain when the task's evidence does not establish it. Naming a likely lead as a lead is not a blocker.
3. The response omits a warning, failure mode, precondition, recovery step, or number that the task contains and a reader acts on.
4. An identifier, path, flag, command, number, or quoted error text from the task appears changed. A formatting change, such as adding or removing code marks, does not count.
5. The response gives a command that deletes data and does not say what it deletes.
6. The response breaks a format, form, or length limit that the task states.

The task's own requirements, such as warmth, a toast's form, or a fixed
format, come before any general idea of good writing.
<!-- judge:end -->

## Weights

`report.py` holds the weights: correctness 30%, fact_retention 20%,
readability 25%, concision 15%, safety 10%.

## Gate

`report.py --reference <condition> --candidate <condition>` passes the
candidate when its blockers are at most the reference's, its correctness and
safety are each no more than 0.1 below, its weighted score is higher, its
linter errors are at most the reference's, and its rate of bad answers on each
gating Jev question is at most the reference's.
