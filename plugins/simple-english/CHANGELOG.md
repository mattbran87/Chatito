# Changelog

## 2026-10-28

- **A hook lints each Markdown file that Claude writes after a simple-english skill loads, in Claude Code.** It runs `ste_lint.py --quiet` after each `Write` or `Edit` of a `.md` file, at most 2 times per file, and gives Claude the findings. The skills also tell Claude to write a chat-only document to a file first and to end the reply with a `Lint:` line, for Claude Desktop, where chat shows hooks grayed out. In 2 Claude Desktop runs of the same README prompt, run 1 loaded `simple-english-docs` and ran no linter. Live check: a `claude -p --plugin-dir` session on 2026-10-28 (session `597ae804`) got `simple-english lint, pass 1 of 2` with both planted errors. Both the `skill.prompt` hook and the `Skill` tool hook ran, and the debug log had no `bypassed by` line. A `--plugin-dir` load is not a marketplace install, so that run does not test the managed-organization bypass of `skill.prompt`. A Claude Desktop check on 2026-10-28 installed a release zip that holds `hooks/` and `types/`. Desktop accepted the zip, both skills loaded, and the document reply ended with a `Lint:` line.

## 2026-10-27

- **`"simple_english_eval": { "enabled": true }` in `.claude/jev.json` no longer turns the eval's Jev stage on.** Put the same block in `~/.claude/jev-user.json`. Opt one clone out with `git config --local jev.simple_english_eval.optout true`. `evals/jev.py` calls the contract client's `feature_consent`, and a row that sends nothing stores the consent reason, such as `not opted in`, in place of `not-opted-in`.

## 2026-10-23

- The output style puts a caveat about what Claude cannot see after the first sentence of a reply, not before it. A style run tested the cycle 3 style against cycle 2 and found blockers fall from 10 to 5. See `evals/FINDINGS-2026-10-23-style3.md`.
- The eval gate allows for noise. A candidate may have up to 10% more linter errors than the reference, and 1 more bad answer for each gating Jev question. Before this change, 2 runs of near-identical text each failed a different rule by 1 response or 2 errors.
- All 5 Jev questions in the eval now gate. They passed a second calibration round at 85% to 100% agreement with hand labels, and `filler` now uses a 0.7 threshold. Every "yes" label for 4 of the questions came from hand-written planted responses, so a `filler` gate failure needs a read before you trust it. See `evals/FINDINGS-2026-10-23-calibration.md`.

- Architecture docs for the plugin are in `docs/architecture/simple-english/`: workflow diagrams, a data model, and a deep dive. A new test, `tests/test_architecture_docs.py`, fails when a page names a file or constant that no longer exists. It does not check whether a description is still true.

## 2026-10-22

- All 3 parts add 3 rules. A destructive command comes after its dry run, with a step to read that output. A configurable default, limit, or retention period never comes from memory, so a reply names the setting instead, such as `gc.reflogExpireUnreachable`. The hard floor keeps the words that set the risk, such as "quietly" and "only". The skill passed the gate at 4.707 against 4.543, and `destructive-clean` rose from 3.86 to 4.70. The style and `simple-english-docs` got the same text with no run of their own. See `evals/FINDINGS-2026-10-22-cycle3.md`.

- The `simple-english-docs` skill gets the same edits as the `simple-english` skill, adapted to documents. A document or section opens with its point, and the first-line test checks each section. No eval run tests this skill, because only 4 of the 15 cases are documents. The same text passed the gate for the skill and for the style.
- `references/documents.md` no longer tells Claude to note an exception. It keeps the clearer sentence.

- The `simple-english` output style gets the same edits as the skill. Its gate passed at 4.668 against 4.312, with 4 blockers against 17, and the `toast` case now scores 5.00. See `evals/FINDINGS-2026-10-22-style.md`.

- The `simple-english` skill adds 5 rules from ayghri/i-have-adhd. It drops preamble, recaps, and closers, and lists changes after a rewrite only when the request asks. It uses the literal phrase, not an idiom. It checks the first line and the last line before it sends. It holds the rules for the whole conversation. Anything the request, a template, or a tool requires wins over every rule, such as a required `Resolves:` line.
- A caveat that flags a guess stays, even at the end of a reply. A reply to thanks or small talk may open with one warm sentence.
- Out-of-scope work, such as a toast, no longer opens with a remark about the rules. The skill gives a precise count only when Claude knows it.
- The eval gate passed: 4.618 against 4.288, with 6 blockers against 10. See `evals/FINDINGS-2026-10-21-cycle2.md`.
## 2026-10-21

- Records the first baseline run in `evals/FINDINGS-2026-10-20.md`. The rules cut blockers from 9 to 6 and raise fact retention, but they lower concision and break the `toast` and `commit-format` cases.
- Records the first Jev calibration. No question could be judged, because the labeled sample held almost no bad responses. Jev's `filler` question disagreed with the person on 7 of 19 labels. All 5 questions stay report-only.
- The eval adds a no-tools note to every condition. Without it, Claude wrote fake tool calls in a loop on debugging prompts until the call timed out. A reply that holds a fake tool call now counts as a failure.
- Each eval call times out after 180 seconds, down from 600, and costs at most $0.50. A stage stops after 3 failed rows in a row, for one condition or overall.

## 2026-10-20

- Adds `evals/`: 15 cases under 3 conditions, scored by `ste_lint.py`, a blind Claude judge, and Jev. Jev decides nothing until a question passes a hand-labeled calibration. `report.py --reference --candidate` gates a rule change against the current rules.
- First release. Ships the `simple-english` and `simple-english-docs` skills, each with the `ste_lint.py` linter, and the `simple-english` output style. All 3 come from personal copies in `~/.claude/`.
- The linter commands in both skills now build the script path from the skill's base directory. The personal copies used `scripts/ste_lint.py`, which resolves inside the user's project, where the script does not exist.
- The output style shows in `/output-style` as `simple-english:simple-english`. It does not set `force-for-plugin`, so it applies only to a user who selects it.
- README: `/output-style` saves the choice in the current project only. The README now says to set `outputStyle` in `~/.claude/settings.json` for every project.
