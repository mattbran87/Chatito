# simple-english architecture

The simple-english plugin ships 2 skills and 1 output style. All 3 apply the same Simplified Technical English rules to expository writing. The plugin also holds an eval harness that measures how well the rules work. These pages explain how the parts fit together.

## Reading order

| Page | Question it answers |
| --- | --- |
| [workflows.md](workflows.md) | How do the rules reach Claude, and how does the eval pipeline run? |
| [data-model.md](data-model.md) | Which eval data files exist, and what keys and hashes do they hold? |
| [deep-dive.md](deep-dive.md) | How does each part work, and why does it work that way? |

## Last checked

These pages match commit `e486a75`, the last commit that changed the plugin's code, rules, or evals. We reviewed them against the code on 2026-10-23. On 2026-10-26, a commit deleted the unused function `done_keys` from `common.py`, and [workflows.md](workflows.md) changed to match.

`plugins/simple-english/tests/test_architecture_docs.py` fails when a page names a missing file, constant, or dotted function name, or cites a line that does not hold the name beside it. No test checks whether a description is still true.
