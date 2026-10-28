# Documents

Load this file before you finalize a project document — README, docs/*.md, design doc, spec, or requirements doc. It extends `SKILL.md`; it does not replace it. The rules and the exemptions all still apply as written there.

A document differs from a chat reply in one way that matters: you can search the text before you finalize it. That makes a mechanical check possible, and this file defines it.

## When This File Applies

- Apply to a new document, or to a substantial rewrite of an existing one.
- Skip for minor edits (typo fixes, link updates, small clarifications) — the overhead outweighs the benefit on trivial changes.

**Partial edits.** Treat a change as a substantial rewrite when you restructure sections or replace most of the prose. Treat everything else as a partial edit. Most rules work sentence by sentence, so they apply cleanly to the lines you change. One rule does not: "one term per concept" scopes to the whole document. On a partial edit, match the vocabulary the document already uses, even where you would pick different terms in a new draft. Two vocabularies in one file cost the reader more than either style alone. Unify vocabulary only when you convert the whole document.

## Document-Only Rules

**Exception — RFC 2119 documents.** The rule against ambiguous modals has one exception in documents. If the document declares RFC 2119 / RFC 8174 keywords, MUST / SHOULD / MAY carry defined normative force. Keep them exactly as the author graded them. Never promote a deliberate SHOULD to a MUST to satisfy the modal rule.

**Claims inside a document.** Every assertion names a mechanism or a check — task and step bodies included. Assertions include the goal, the architecture, acceptance criteria, rationale, and any note on current state. Imperative step instructions carry no claim, so they need no rewrite.

## Self-Check Before Finalizing

1. Run any other review this document needs first — spec coverage, template conformance, naming consistency. This style pass goes last, so it cannot invalidate a check that ran before it.
2. If the document exists only in your reply, write it to a file before you show it. Use the outputs folder when the environment gives one, or a scratch folder. Run the linter once on that file. `<base>` is the base directory for this skill, given to you when the skill loads. A path relative to the working directory resolves inside the user's project, where the script does not exist. Quote the script path and write it with forward slashes, because on Windows the base directory can hold backslashes or spaces. Use `python3`, and fall back to `python` on Windows.

   ```
   python3 "<base>/scripts/ste_lint.py" path/to/document.md
   ```

   If a `simple-english lint` message follows your write, the plugin's hook ran the linter for you, unless the message says `did not run`. When it ran, do not run the linter yourself on that file. Fix what the message lists, and make all the fixes in one write. The hook's message after that write is the second pass, and it checks the finished file. Skip the command in step 4 too. When it did not run, run the linter yourself as in step 2, or follow "Without Python" when Python is missing.

3. Fix everything it found in one pass. Resolve every `ERROR`. Judge each `review` hit and keep the ones that read better — a counterfactual keeps its "would", a UI label keeps its own word.
4. Run it once more to confirm, with `--quiet` to skip the footer you already read:

   ```
   python3 "<base>/scripts/ste_lint.py" --quiet path/to/document.md
   ```

   **Stop after this second pass.** If anything remains, fix what reads better and keep the rest, rather than loop again. A third pass rarely finds what a careful second pass missed, and each pass costs a round trip.
5. Read for the rules the linter cannot reach. It says nothing about noun clusters, list parallelism, one term per concept beyond its fixed table, front-loading, jargon left undefined, or whether a claim names its mechanism.
6. For each fix, re-read the result. If the rewrite reads more stilted or circuitous than the original, keep the clearer sentence. Do not revert the whole document.
7. Confirm that no edit changed an identifier. A style pass that renames something breaks the naming consistency step 1 approved.
8. End your reply with one line that gives the lint result, in one of these forms:

   ```
   Lint: ste_lint.py ran on <file> — <n> errors fixed, <m> review hits kept.
   Lint: did not run — <reason>.
   ```

   `<n>` is the ERROR count of the first run, by you or by the hook. `<m>` is the review hits you left unchanged after the last run. This line is for documents only. A commit message or a chat reply gets no `Lint:` line.

## Verifying the Linter Itself

`python3 "<base>/scripts/ste_lint.py" --selftest` runs 19 planted cases and reports pass or fail for each. It exists because a linter that finds nothing looks identical to one that fails silently.

Run it in three cases only:

- After you install or upgrade this skill.
- After anyone edits `scripts/ste_lint.py`, including a change to the word lists.
- When a clean result looks wrong — you expected a messy document to flag something and it reported nothing.

**Do not run it per document.** The code is deterministic and reads no configuration, so a second run on an unchanged file returns the same 19 passes and tells you nothing.

## What the Linter Reaches

Ten rules, in two tiers.

**Resolve every hit:** stacked auxiliaries (perfect tense), passive voice, British spelling.

**Review each hit, then keep or rewrite:** gerund after a preposition, vague quantifiers, modals outside can/will/must, non-canonical terms, trailing conditions in instructions, sentence length, paragraph length.

Tier 2 patterns match correct usage often enough that a "drive it to zero" habit teaches you to ignore the output. Judge each one. A counterfactual keeps its "would". A UI label keeps its own word. "The sink is granite or quartz" reads correctly.

**Exception — present perfect in first-person recollection.** A sentence such as "I have flown with them on 14 trips since 2019" carries meaning no simple tense reproduces, and a forced rewrite reads worse. Keep it. A claim about a system almost always rewrites cleanly.

## Without Python

The linter needs Python 3.8 and the standard library only. If neither is available, search for this one pattern by hand — it catches the most common defect and no suffix rule finds it, because "flown", "met", and "known" carry no `-ed`:

```
\b(has|have|had)\b(\s+\b(not|never|already|just|also|only|recently|always)\b)?\s+(\w+ed|been|become|begun|broken|brought|built|bought|caught|chosen|come|done|drawn|driven|eaten|fallen|felt|flown|forgotten|found|given|gone|got|gotten|grown|heard|held|kept|known|laid|led|left|lent|lost|made|meant|met|paid|put|read|risen|run|said|seen|sent|set|shown|sold|spoken|spent|stood|taken|taught|told|thought|thrown|understood|won|written)\b
```

Then read for the rest.

## Common Mistakes

| Mistake | Reality |
|---|---|
| Reading a clean linter run as a clean document | It reaches 10 rules. Noun clusters, parallelism, front-loading, and undefined jargon still need a read. |
| Running `--selftest` before every document | The code is deterministic. Run it after an install, after an edit, or when a clean result looks wrong. |
| Driving tier 2 hits to zero | "Pay by standing order" and "the case is closed" both match a pattern, and both read correctly. |
| Skipping the check because the document reads clean | A stacked auxiliary hides easily in a long sentence. The check costs one command. The reply's `Lint:` line shows the user whether the check ran. |
