---
name: simple-english-docs
description: Use when writing or editing prose in an expository project document — README, docs/*.md, design doc, spec, requirements doc, post-mortem, or status report. Applies Simplified Technical English to raise readability first, and to cut length second. Covers a full rewrite (restructuring sections or replacing most of the prose) and a smaller partial edit alike. Skip for typo fixes, link updates, and formatting-only changes. Do NOT use for persuasive documents (marketing copy, pitches, proposals that sell) or narrative and ceremonial writing (speeches, stories, personal letters) — the rules strip the rhythm those genres depend on.
---

# Simple English Docs

## Overview

This skill applies one controlled-language discipline to document writing: Simplified Technical English (STE, adapted from ASD-STE100). STE governs sentence length, verb forms, word choice, and structure. It exists to make a document fast to read and hard to misread.

## What This Skill Optimizes For

Two goals, in this order:

1. **Higher readability.** A reader finds the answer fast and misreads nothing.
2. **Shorter documents.** Cut words that carry no information.

**The order decides every conflict.** When the shorter version reads worse, keep the clearer one. A table that runs longer than the equivalent paragraph still wins when it lets the reader compare two columns at a glance. Brevity serves the reader. It does not outrank the reader.

This skill does not chase minimal output. It cuts words that carry no information, which usually shortens the document — but length falls out of the rules rather than driving them.

**One hard floor on goal 2: a cut never removes a warning.** The length rules govern words. They never govern facts. Before you delete a sentence, ask what it tells the reader. Keep it when it carries any of these:

- A failure mode, or what breaks.
- A precondition, a prerequisite, or a constraint.
- A recovery step, a rollback caveat, or an escape hatch.
- A threshold, a limit, or a number the reader acts on.

Any one of those makes the sentence content, not padding. Shorten its wording where you can. Never drop it.

**The floor also keeps the words that set the risk.** "Silently", "quietly", "only", "at most", and "in our testing" change what the reader must watch for. "The client falls back to 60 seconds" and "the client quietly falls back to 60 seconds" are 2 different warnings. Keep the word, not only the sentence. A document that reads well and omits the rollback caveat costs the reader more than any paragraph you cut to save space.

This floor outranks every rule below it, including the sentence caps and the paragraph limit. No pattern in the self-check reaches it, so step 5 checks it by hand.

Every rule below serves those goals. **When a rule fights them, the goals win.** If a rewrite reads flatter or skims worse, keep the original. Do not tell the reader about the rule you set aside. A rule that costs the reader more than it saves defeats its own purpose.

## When to Use

Apply this skill to a new document, or to a substantial rewrite of an existing one: a README, docs/*.md, a design doc, a spec, a requirements doc, a post-mortem, or a status report. Skip it for minor edits such as typo fixes, link updates, and small clarifications, where the overhead outweighs the benefit.

**Expository documents only.** These rules fit prose that informs or explains. Do not apply them to a persuasive document (marketing copy, a pitch deck, a proposal written to sell) or to narrative and ceremonial writing (a speech, a story, a personal letter). Those genres run on rhythm, idiom, and cadence, and these rules strip all three — the output then reads like translated text. For that work, write naturally and say nothing about these rules.

Narration *inside* an expository document stays in scope. A post-mortem recounts an outage. A status update recounts a slip. The exclusion covers whole documents built on story or persuasion.

**Partial edits.** Treat a change as a substantial rewrite when you restructure sections or replace most of the prose. Treat everything else as a partial edit. Most rules here work sentence by sentence, so they apply cleanly to the lines you change. One rule does not: "one term per concept" scopes to the whole document. On a partial edit, match the vocabulary the document already uses, even where you would pick different terms in a new draft. Two vocabularies in one file cost the reader more than either style alone. Unify vocabulary only when you convert the whole document.

## Exemptions (read first)

Leave these unchanged, even where they break a rule below:

- **Anything the request, a template, or a tool requires.** If a template asks for a `Resolves:` field, write `Resolves:`, even though the word table bans "resolve". The same holds for a required heading, field name, length, or format. The harness wins over every rule here.
- Code blocks, commands, and their expected output.
- Identifiers — function names, file names, paths, flags, UI labels, error strings.
- Quoted material, including quotations from other documents and error text.
- Boilerplate that an external template, house style guide, or process mandates word for word.

These rules govern the prose you write. They do not govern text that another authority fixes, and an edit there breaks the thing the text names.

## Sentence Construction

- **Classify the passage first, then apply the matching cap.** Procedural text tells the reader what to do: imperative mood, one instruction per sentence, under ~20 words. Descriptive text explains: simple tenses, under ~25 words, one topic per paragraph. The caps differ because a reader acting on a step has less attention to spare than a reader taking in an explanation. Treat both as strong defaults, not hard limits.
- Put one idea in one sentence. Do not chain unrelated statements with "and" or "which."
- **Put the condition before the command, and separate them with a comma.** Write "If the build fails, read the log," never "Read the log if the build fails." A reader who meets the action first performs it, then discovers the condition never applied. The order costs nothing and prevents a wrong action.
- **Hold a paragraph to one topic and about 6 sentences.** A longer block hides its own structure and the reader loses the thread. Split where the topic turns.
- Do not drop a verb, subject, or article to shorten a sentence. That buys brevity with ambiguity.

## Verb and Tense

- Use simple tenses: infinitive, imperative, simple present, simple past, simple future. Use a past participle as an adjective only.
- Avoid present perfect and other stacked auxiliaries. "has been configured" → "you configured it" or "it configures on startup". Stacked auxiliaries hide who acted and when.
- Write in active voice and name the actor. Use passive voice only when the actor stays genuinely unknown.
- Use imperative mood for instructions: "Run the tests," not "The tests should be run."
- Use "-ing" only as a technical noun, or as a modifier inside one ("the operating system"). Do not use it as a general gerund: "by clicking the button" → "click the button."
- Watch the gerund that follows a preposition — *instead of*, *without*, *by*, *before*, *after*, *rather than*:
  - "instead of omitting the claim" → "rather than omit the claim"
  - "without checking the token" → "and never checks the token"
  - "before running the migration" → "before you run the migration"
- **A gerund that names a concept stays allowed, and that includes list labels.** "**Over-tightening.** Excess force cracks the nut." names a failure mode, which is the noun use this rule permits. The ban targets a gerund that stands in for a verb, never one that heads a list item.

## Word Choice

- **Use one term per concept, and pick the canonical word.** A rule that says "stay consistent" without naming the winner produces three writers and three vocabularies. Hold the chosen word for the whole document.

| Concept | Use | Not |
|---|---|---|
| test a condition | check | verify, confirm, validate, ensure |
| stored settings | configuration | config, settings, options |
| destroy data | delete | remove, erase, purge |
| repair a defect | fix | repair, correct, resolve, address |
| begin | start | begin, launch, initiate, commence |
| cease | stop | halt, terminate, end, cancel |
| put to work | use | utilize, leverage, employ, harness |
| make visible | show | display, render, present, surface |
| alter | change | modify, alter, amend, adjust |
| bring into being | create | make, generate, produce |
| acquire | get | obtain, retrieve, fetch |
| find necessary | need | require |
| aid | help | assist, facilitate, enable |
| locate | find | locate, discover, identify |
| in addition | also | additionally, furthermore, moreover |
| contrast | but | however, although, whereas |
| consequence | so | therefore, thus, hence, consequently |
| earlier than | before | prior to, in advance of |
| on the topic of | about | regarding, concerning, with respect to |
| cause | because | due to, owing to, on account of |

  Three cases override the table:
  - **The interface wins.** If the UI reads "Settings", write Settings. The rule that matches code and interface terminology outranks this one.
  - **Distinguish rather than collapse when the words mean different things.** An *error* names the message, a *failure* names the event, a *defect* names the flaw in the code. Same for *user*, *customer*, and *caller* — pick the word that names the role, then hold it.
  - **Some near-synonyms are not synonyms.** "update" means a change to a newer version. "build" in a CI sense names a noun.

- **Prefer three modals: can, will, must.** A "should" that states a requirement becomes "must". Delete a "should" that states an option. "cannot" stays. Two cases keep the other modals: a genuine counterfactual ("a bounded cache would flatten instead") and permission ("the role may read the bucket"). A modal that softens a fact you can state firmly still goes.
- Keep noun clusters to 3 words or fewer: "the user session token cache" → "the cache of user session tokens."
- **Define a concept term at its first use, in ten words or fewer, one definition per sentence.** Write "idempotent (safe to run twice)". Do not define product names, standard names such as Postgres, S3, or HTTP, or the tool the document describes. A definition longer than ten words becomes a digression; give it its own sentence or its own section.
- State a firm fact firmly: "this fails if the token expires," not "this may fail if..."
  - **Exception — RFC 2119 documents.** If the document declares RFC 2119 / RFC 8174 keywords, MUST / SHOULD / MAY carry defined normative force. Keep them exactly as the author graded them. Never promote a deliberate SHOULD to a MUST to satisfy this rule.
- Give a precise count instead of "some," "several," or "a few," whenever a precise count exists **and you know it**. Never invent a number to replace a vague word. A wrong number is worse than no number.
- **Do not state a configurable default, limit, timeout, or retention period from memory.** These values change between versions and configurations. State one only when the request, the code, or a cited source gives it. Otherwise, name the setting that holds the value: "check `gc.reflogExpireUnreachable`", not "Git keeps them for 90 days". A fixed, well-known value needs no check. HTTPS uses port 443, so write "443".
- **Use the literal word, not a picture.** If a word makes the reader picture something that is not there, write what the thing does or what state it is in:
  - "the old key is dead" → "the old key no longer works"
  - "leaves the old price live" → "the old price still shows"
  - "ran clean for hours" → "ran for 3 hours with no errors"
  - "Browsers check back on each visit" → "The browser sends a new request on each visit"
  - "out of the box" → "by default"

  A term that is the field's name for a thing stays, even when it began as a picture: "race condition," "bottleneck," "cache lifetime." An ordinary word that you put on a technical noun as a description does not stay, even when the field uses it in another term. A figurative word makes a reader who learned English as a second language guess.
- **Use American English spelling.** "color" not "colour," "organize" not "organise," "center" not "centre," "traveled" not "travelled," "defense" not "defence," "catalog" not "catalogue," "analyze" not "analyse," "gray" not "grey." Two cases override this rule:
  - An identifier, a quoted string, or a proper noun keeps its own spelling. The exemptions cover these already.
  - A document that already uses another convention consistently keeps that convention. This follows the partial-edit rule: one file with two spellings costs the reader more than either convention alone.
- **Name the mechanism behind a claim, or the check that proves it. Never assert a bare state.**
  - "The build fails on the auth suite," not "the build is broken."
  - "The config passes schema validation," not "the config is valid."
  - "The refresh logic races when two requests arrive together," not "there is a race condition."

  A bare state-claim hides the one thing the reader needs: what makes it true, or how to verify it. In a spec, a plan, or a design doc that vagueness costs the most, so spend your attention here first.

## Structure

- Match the exact terminology used in code or the interface. Do not paraphrase a function name, a file name, or a UI label.
- Front-load the most important information. Put conclusions, warnings, and requirements first, never buried at the end.
- Keep list items grammatically parallel — all imperative verbs, or all noun phrases, not mixed.
- **No preamble, no recap, no closer.** Open a document or a section with its point, not with "This document describes". Do not end a section with a summary of what it just said. When you return a rewrite, return only the document. List your changes only when the request asks for them.
  - **A caveat is not a closer.** A note that flags a guess, names what you could not check, or asks the reader to check something before they act is content. Keep it, even at the end. The hard floor protects it.
- **Put the preview before a destructive command.** When a procedure deletes or overwrites data, give its dry run or preview first. Then tell the reader to read that output. Give the real command last. A reader who copies the first command they see must not lose data.
- **The rules hold for the whole document.** They apply to the last section as much as to the first.

## Emphasis

**Keyword labels mark what the reader must act on.** A label is one of 6 fixed uppercase words in bold, followed by a colon, at the start of a paragraph or list item, such as `**WARNING:** this deletes the remote branch.`

| Label | Marks |
| --- | --- |
| `WARNING` | Harm the reader cannot undo: data loss, deleted history, a secret pushed to a public repository, a change to production |
| `CAUTION` | Harm the reader can undo, at a cost: a broken build, spent quota, a long cleanup |
| `BLOCKED` | Work that cannot continue, and the cause |
| `ACTION` | A step only the user can take |
| `UNVERIFIED` | A fact you did not check |
| `ASSUMED` | A decision you made for the user without asking |

- **Most replies need no label.** A label marks the exception. If every reply carries one, the reader stops seeing them.
- **A label marks a risk or a gap, never advice.** "Log purge failures" is advice, so write it as a plain sentence. Before you add a label, name the harm or the unknown that it marks.
- **Use only these 6 words.** Never invent a label such as NOTE or IMPORTANT. The reader has no way to learn its meaning.
- **Give 1 label to 1 sentence or 1 short paragraph.** When 2 labels fit, use the one higher in the table.
- **A label adds to a warning. It never replaces the warning's words.** The hard floor still applies.
- **`BLOCKED` names why the work stopped, and `ACTION` names the step that clears it.** Use them as a pair when a block needs the user.
- **`ACTION` covers tasks, not questions.** A question stays a question.
- **4 labels speak only to the user.** Put `BLOCKED`, `ACTION`, `UNVERIFIED`, and `ASSUMED` in a reply, never in a commit message, a code comment, or a document for other readers. `WARNING` and `CAUTION` can go in any of them.
- **In a commit message, write the label without bold.** Git shows no bold.

**Bold inside a sentence marks one word the reader must not miss.** Bold that opens a paragraph or list item and ends with a full stop or colon is a lead-in. It names the topic and stays allowed. Any other bold is emphasis:

- Bold a word that sets the risk of its sentence: "silently," "only," "at most," "never," a negation the reader could miss, or a number the reader acts on.
- Bold a word or a short phrase, never a whole sentence. If a sentence needs that weight, give it a label.
- Use at most 1 emphasis bold span per paragraph.

## Choose the form

Pick the form from the reader's task, not from the length it saves.

| Form | Use it when | Do not use it when |
| --- | --- | --- |
| Prose | Each sentence depends on the one before: a cause, then its effect, then the fix | The items stand alone, and the reader must find one |
| Bulleted list | 3 or more parallel items, in no fixed order | 2 items, which fit in one sentence with "and" |
| Numbered list | Steps the reader does in order, or items you refer to later by number | The order carries no meaning |
| Table | 2 or more items compared on 2 or more attributes | Only 1 attribute, which is a list, or cells that need full sentences |
| Heading | A reply or document with 3 or more separate topics | A chat reply with one topic |
| Code block | A command, code, or exact output | Never skip it for these |

- **Nest a list 1 level deep at most.** A third level means the content needs a heading or a table.
- **Hold a table cell to one short phrase or one sentence.** A cell that needs 2 sentences belongs in prose under the table.
- **Do not break a causal chain into bullets.** A list drops the "because" and "so" that carry the reasoning, and the reader then cannot see the mechanism.

## Self-Check Before Finalizing

1. Run any other review this document needs first — spec coverage, template conformance, naming consistency. This style pass goes last, so it cannot invalidate a check that ran before it.
2. Read for the rules a search cannot reach: long sentences, passive voice used where you know the actor, ambiguous modals, noun clusters over 3 words, undefined jargon, non-parallel lists, and bare state-claims that name no mechanism.
3. **Lint the document from a file.** If the document exists only in your reply, write it to a file before you show it. Use the outputs folder when the environment gives one, or a scratch folder. Run `python3 "<base>/scripts/ste_lint.py" <file>` once, and fall back to `python` on Windows. `<base>` is the base directory for this skill, given to you when the skill loads; a relative `scripts/` path resolves inside the user's project, where the script does not exist. Fix everything it found in one pass: resolve every ERROR, judge each review hit. Run it once more with `--quiet` to confirm, then stop. A third pass rarely finds what a careful second pass missed.

   If a `simple-english lint` message follows your write, the plugin's hook ran the linter for you, unless the message says `did not run`. When it ran, do not run the linter yourself on that file. Fix what the message lists, and make all the fixes in one write. The hook's message after that write is the second pass, and it checks the finished file. When it did not run, run the linter yourself as above.

   Run `--selftest` only after an install, after anyone edits the linter, or when a clean result looks wrong.
4. For each hit, apply the rewrite. Re-read the result. If the rewrite reads more stilted or circuitous than the original, keep the clearer sentence. Do not revert the whole document.
5. **Account for every warning in the source.** When you edited an existing document, list each warning, caveat, failure mode, precondition, and recovery step the original carried. Check that each one survives. A style pass may reword a warning. It may never delete one, or a word such as "silently" or "only" that sets its risk. No linter reaches this check. Reading your own draft does not reach it either. Only a comparison against the source text does.
6. Confirm that no edit changed an identifier. A style pass that renames something breaks the naming consistency step 1 approved.
7. **Read only the first line of each section, then only the last line of the document.** Each first line gives the section's point. If the last line is a recap or a pleasantry, delete it.
8. Read each verb and adjective that describes a technical noun as a reader who translates word by word. If the literal meaning is wrong for that noun, replace the word. Check that the document holds every word, field, and format that the request or the template requires.
9. Finalize only once the scans come back clean, or each remaining hit is one you chose to keep.
10. End your reply with one line that gives the lint result, in one of these forms:

    ```
    Lint: ste_lint.py ran on <file> — <n> errors fixed, <m> review hits kept.
    Lint: did not run — <reason>.
    ```

    `<n>` is the ERROR count of the first run, by you or by the hook. `<m>` is the review hits you left unchanged after the last run. This line is for documents only. A commit message or a chat reply gets no `Lint:` line.

### Tier 1 — resolve every hit

Stacked auxiliaries — present perfect and past perfect. A suffix rule alone misses irregular participles such as "flown" and "met," so this pattern lists them:

```
\b(has|have|had)\b(\s+\b(not|never|already|just|also|only|recently|always)\b)?\s+(\w+ed|been|become|begun|broken|brought|built|bought|caught|chosen|come|done|drawn|driven|eaten|fallen|felt|flown|forgotten|found|given|gone|got|gotten|grown|heard|held|kept|known|laid|led|left|lent|lost|made|meant|met|paid|put|read|risen|run|said|seen|sent|set|shown|sold|spoken|spent|stood|taken|taught|told|thought|thrown|understood|won|written)\b
```

Labels that are not on the list. Search case-insensitively, because `**Note:**` breaks the rule as much as `**NOTE:**`. Replace each hit with a listed label, or delete the label:

```
\*\*(NOTE|NB|IMPORTANT|TIP|HINT|INFO|FYI|DANGER|ALERT|ATTENTION|CRITICAL|TODO):\*\*
```

### Tier 2 — review each hit, then keep or rewrite

These patterns match correct usage often enough that a "drive it to zero" habit teaches you to ignore the output. Judge each hit.

Gerund after a preposition:

```
\b(instead of|without|by|before|after|rather than|prior to)\s+\w+ing\b
```

Vague quantifiers:

```
\b(some|several|many|most|a few|a number of|various|a handful of|a couple of)\b
```

Bare state-claims. This one flags far more than it catches, so treat every hit as a question rather than a defect: does this sentence name what makes it true?

```
\b(is|are|was|were)\b
```

Trailing conditions in instructions. Each hit puts the action before the condition, so a reader performs it and then learns it never applied. Rewrite as "If X, do Y":

```
^\s*(?:[-*+]|\d+\.)\s+(?!(?:The|A|An|This|That|These|Those|It|They|We|You|Because|Since|If|When|Unless|Every|Each|Our|Your|Their)\b)([A-Z][a-z]+)\b([^.\n]*?)\s(if|when|unless)\s([^.\n]*)\.
```

The negative lookahead skips descriptive list items, which this rule does not govern. One known miss stays: a "when" inside an object clause reads as a condition to the pattern and needs a human to dismiss.

Modals outside the preferred set. Keep a hit that states a genuine counterfactual or a permission. Rewrite or delete a hit that softens a fact you can state firmly. In an RFC 2119 document, keep every graded keyword exactly as the author wrote it:

```
\b(should|would|may|might|could)\b
```

Case matters for one word: a case-insensitive search also matches the month "May".

British spellings. Rewrite each hit in American English, unless it sits in an identifier, a quoted string, or a proper noun, or unless the document already uses British spelling throughout:

```
\b(colour|colours|coloured|colouring|colourful|behaviour|behaviours|behavioural|favour|favours|favoured|favourite|favourites|labour|labours|laboured|neighbour|neighbours|neighbouring|honour|honours|honoured|honourable|humour|humourless|organise|organised|organising|organisation|organisations|organisational|recognise|recognised|recognising|apologise|apologised|apologising|realise|realised|realising|analyse|analysed|analysing|summarise|summarised|summarising|prioritise|prioritised|utilise|utilised|centre|centres|centred|theatre|theatres|metre|metres|litre|litres|defence|defences|offence|offences|licence|licences|catalogue|catalogues|analogue|travelled|travelling|traveller|cancelled|cancelling|modelling|labelled|labelling|fuelled|grey|programme|programmes|whilst|amongst|enrol|enrolment|fulfil|fulfilment|instalment|skilful|marvellous)\b
```

This pattern lists whole words rather than suffixes on purpose. A suffix rule such as `analys\w*` also matches "analysis," and `organis\w*` matches "organism" — both correct American spellings.

### Reading the results

**Zero matches clears the 3 rules these patterns reach. It proves nothing about the rest.** Noun clusters, list parallelism, one term per concept, undefined jargon, front-loading, and every warning the source carried all need a read. No regex reaches them without part-of-speech tagging.

If your search tool reports a pattern as invalid, it lacks `\b` support. Fall back to searching each word on its own, or use the word-boundary syntax your tool documents.

## Common Mistakes

These nine catch misreadings the rules above do not prevent on their own.

| Mistake | Reality |
|---|---|
| Dropping a warning, a caveat, or a failure mode to make the document shorter | The hard floor forbids this, so shorten the wording and keep the fact: blind judges caught a shorter version that dropped a rollback warning about silent fallback to smaller pool defaults. |
| Flattening a table or list into prose because prose runs shorter | Keep structure that does work prose cannot, such as two dimensions of data in a table. |
| Skipping the search because the document reads clean | The search costs one command and finds the stacked auxiliary that a read misses in a long sentence. The reply's `Lint:` line shows the user whether the check ran. |
| Driving tier 2 hits to zero | "Pay by standing order" and "the case is closed" both match a tier 2 pattern, and both read correctly. |
| Running `--selftest` before every document | The code is deterministic, so run it only after an install, after an edit, or when a clean result looks wrong. |
| Stripping gerund labels out of a list | "**Over-tightening.**" names a failure mode, and a rewrite into "Do not..." sentences flattens a scannable list. |
| Enforcing STE's ~900-word controlled dictionary | This skill omits the dictionary, so only the structural rules above apply. |
| Labeling every reply, or every risk in a reply | A label marks the exception, so most replies need none, and the reader stops seeing labels that appear everywhere. |
| Bolding a whole sentence for weight | A bold sentence is a label without a name, so give it the label that fits, or bold only the word that sets its risk. |

## Attribution

The AeroSpace and Defence Industries Association of Europe publishes and maintains ASD-STE100, the Simplified Technical English specification. This skill paraphrases structural principles from that standard. It reproduces no part of the specification, and it omits the controlled dictionary. A document that follows the rules here does not thereby conform to ASD-STE100. Do not describe such a document as STE-compliant.
