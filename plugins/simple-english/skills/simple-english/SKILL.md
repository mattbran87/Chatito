---
name: simple-english
description: Use for expository writing — prose that informs or explains. Covers chat replies that explain something, commit messages, PR descriptions, code comments, documentation, READMEs, specs, design docs, bug reports, post-mortems, status updates, and business reports. Applies Simplified Technical English to raise readability first, and to cut length second. Do NOT use for persuasive writing (marketing copy, pitches, advocacy) or for narrative and ceremonial writing (speeches, toasts, stories, personal letters, condolences) — the rules strip the rhythm and idiom those genres depend on. Choose this instead of a document-only style skill, not alongside one.
---

# Simple English

## Overview

This skill applies one controlled-language discipline: Simplified Technical English (STE, adapted from ASD-STE100). STE governs sentence length, verb forms, word choice, and structure. It exists to make technical prose fast to read and hard to misread.

The rules cover chat replies, commit messages, PR descriptions, code comments, and project documents alike. Documents allow a search-based check that a chat reply does not, so load `references/documents.md` before you finalize one.

## What This Skill Optimizes For

Two goals, in this order:

1. **Higher readability.** A reader finds the answer fast and misreads nothing.
2. **Shorter output.** Cut words that carry no information.

**The order decides every conflict.** When the shorter version reads worse, keep the clearer one. A table that runs longer than the equivalent paragraph still wins when it lets the reader compare two columns at a glance. Brevity serves the reader. It does not outrank the reader.

This skill does not chase minimal output. It cuts words that carry no information, which usually shortens the text — but length falls out of the rules rather than driving them.

**One hard floor on goal 2: a cut never removes a warning.** The length rules govern words. They never govern facts. Before you delete a sentence, ask what it tells the reader. Keep it when it carries any of these:

- A failure mode, or what breaks.
- A precondition, a prerequisite, or a constraint.
- A recovery step, a rollback caveat, or an escape hatch.
- A threshold, a limit, or a number the reader acts on.

Any one of those makes the sentence content, not padding. Shorten its wording where you can. Never drop it.

**The floor also keeps the words that set the risk.** "Silently", "quietly", "only", "at most", and "in our testing" change what the reader must watch for. "The client falls back to 60 seconds" and "the client quietly falls back to 60 seconds" are 2 different warnings. Keep the word, not only the sentence. A document that reads well and omits the rollback caveat costs the reader more than any paragraph you cut to save space.

This floor outranks every rule below it, including the sentence caps and the paragraph limit.

Every rule below serves those goals. **When a rule fights them, the goals win.** If a rewrite reads flatter or skims worse, keep the original. Do not tell the reader about the rule you set aside. A rule that costs the reader more than it saves defeats its own purpose.

That tiebreaker matters more than any single rule. Most bad outcomes here come from a rule applied past the point where it helps.

## Scope — Expository Writing Only

Apply this skill to **expository writing**: prose whose job is to inform or explain.

**In scope:** documentation, READMEs, specs, design docs, bug reports, post-mortems, status updates, code comments, commit messages, PR descriptions, technical explanations, business reports, process guides, and chat replies that explain something.

**Out of scope — do not apply these rules:**

- **Persuasive writing** — marketing copy, pitches, fundraising appeals, advocacy, opinion pieces.
- **Narrative and ceremonial writing** — speeches, toasts, stories, personal letters, condolences, eulogies.

Those genres run on rhythm, idiom, and cadence. The sentence caps strip exactly those qualities, and the output then reads like translated text — short declarative sentences, no subordination, near-miss idiom. For that work, write naturally and say nothing about these rules. A remark about writing rules at the top of a toast spoils the toast.

**Expository documents often contain narration, and that narration stays in scope.** A post-mortem recounts an outage. A status update recounts a slip. The exclusion covers whole works built on story or persuasion, never a passage that reports events inside an explanatory document.

## Exemptions (read first)

Leave these unchanged, even where they break a rule below:

- **Anything the request, a template, or a tool requires.** If the request asks for a `Resolves:` line, write `Resolves:`, even though the word table bans "resolve". The same holds for a required heading, field name, length, or format. The harness wins over every rule here.
- Code blocks, commands, and their expected output.
- Identifiers — function names, file names, paths, flags, UI labels, error strings.
- Quoted material, including tool output, error text, and quotations from other documents.
- Boilerplate that an external template, house style guide, or process mandates word for word.

These rules govern the prose you write. They do not govern text that another authority fixes, and an edit there breaks the thing the text names.

## Sentence Construction

- **Classify the passage first, then apply the matching cap.** Procedural text tells the reader what to do: imperative mood, one instruction per sentence, under ~20 words. Descriptive text explains: simple tenses, under ~25 words, one topic per paragraph. The caps differ because a reader acting on a step has less attention to spare than a reader taking in an explanation.
- Put one idea in one sentence. Do not chain unrelated statements with "and" or "which."
- **Put the condition before the command, and separate them with a comma.** Write "If the build fails, read the log," never "Read the log if the build fails." A reader who meets the action first performs it, then discovers the condition never applied. The order costs nothing and prevents a wrong action.
- **Hold a paragraph to one topic and about 6 sentences.** A longer block hides its own structure and the reader loses the thread. Split where the topic turns.
- Do not drop a verb, subject, or article to shorten a sentence. That buys brevity with ambiguity, which trades against the first goal.
- Use a numbered or bulleted list for complex or sequential material. A reader scans a list and re-reads a dense paragraph.

Treat the word caps as strong defaults, not hard limits. One longer sentence that carries a single clear idea beats two clipped fragments.

## Verb and Tense

- Use simple tenses: infinitive, imperative, simple present, simple past, simple future. Use a past participle as an adjective only.
- Avoid present perfect and other stacked auxiliaries. "has been configured" → "you configured it" or "it configures on startup". Stacked auxiliaries hide who acted and when.
- Write in active voice and name the actor. Use passive voice only when the actor stays genuinely unknown. A named actor tells the reader who to ask.
- Use imperative mood for instructions: "Run the tests," not "The tests should be run."
- Use "-ing" only as a technical noun, or as a modifier inside one ("the operating system"). Do not use it as a general gerund: "by clicking the button" → "click the button."
- Watch the gerund that follows a preposition — *instead of*, *without*, *by*, *before*, *after*, *rather than*, *for*. That construction reads naturally, so it survives a self-check that catches the obvious cases:
  - "instead of omitting the claim" → "rather than omit the claim"
  - "without checking the token" → "and never checks the token"
  - "before running the migration" → "before you run the migration"
  - "the risk of losing data" → "the risk that you lose data"
- **A gerund that names a concept stays allowed, and that includes list labels.** "**Over-tightening.** Excess force cracks the nut." names a failure mode, which is the noun use this rule permits. The ban targets a gerund that stands in for a verb, never one that heads a list item. Rewriting such labels into "Do not..." sentences costs the reader a scannable list.

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
  - **Some near-synonyms are not synonyms.** "update" means a change to a newer version. "build" in a CI sense names a noun. Neither substitutes for the general word.

- **Prefer three modals: can, will, must.** They carry capability, futurity, and requirement, which covers most technical prose. A "should" that states a requirement becomes "must". Delete a "should" that states an option. "cannot" stays, because it negates "can".

  Two cases keep the other modals, and both state something a firm verb cannot:
  - A genuine counterfactual: "a bounded cache would flatten instead."
  - Permission: "the role may read the bucket."

  Any modal that softens a fact you can state firmly still goes. "This may fail if the token expires" becomes "this fails if the token expires."
- Keep noun clusters to 3 words or fewer: "the user session token cache" → "the cache of user session tokens."
- **Define a concept term at its first use, in ten words or fewer, one definition per sentence.** Write "idempotent (safe to run twice)". Do not define product names, standard names such as Postgres, S3, or HTTP, or the tool the document describes — the reader knows them or can look them up, and a definition there spends the budget for nothing. A definition longer than ten words becomes a digression; give it its own sentence or its own section.
- State a firm fact firmly: "this fails if the token expires," not "this may fail if..."
- Give a precise count instead of "some," "several," or "a few," whenever a precise count exists **and you know it**. Never invent a number to replace a vague word. A wrong number is worse than no number.
- **Do not state a configurable default, limit, timeout, or retention period from memory.** These values change between versions and configurations. State one only when the request, the code, or a cited source gives it. Otherwise, name the setting that holds the value: "check `gc.reflogExpireUnreachable`", not "Git keeps them for 90 days". A fixed, well-known value needs no check and no extra steps. HTTPS uses port 443, so answer "443" and stop.
- **Use the literal phrase, not an idiom.** "out of the box" → "by default". "under the hood" → "inside". "a moving target" → "changes often". An idiom makes a reader who learned English as a second language guess. A standard technical term stays, even when it began as a figure of speech: "race condition", "bottleneck", "cache hit".
- **Use American English spelling.** "color" not "colour," "organize" not "organise," "center" not "centre," "traveled" not "travelled," "defense" not "defence," "catalog" not "catalogue," "analyze" not "analyse," "gray" not "grey." Two cases override this rule:
  - An identifier, a quoted string, or a proper noun keeps its own spelling. The exemptions cover these already.
  - A document that already uses another convention consistently keeps that convention. One file with two spellings costs the reader more than either convention alone.
- **Name the mechanism behind a claim, or the check that proves it. Never assert a bare state.**
  - "The build fails on the auth suite," not "the build is broken."
  - "The token expires after one hour," not "the token is expired."
  - "The refresh logic races when two requests arrive together," not "there is a race condition."

  A bare state-claim hides the one thing the reader needs: what makes it true, or how to verify it. This rule does most of the work that makes technical prose useful, so spend your attention here before anywhere else.

## Structure

- Match the exact terminology used in the code or the interface. Do not paraphrase a function name, a file name, or a UI label.
- Front-load the most important information. Put conclusions, warnings, and requirements first, never buried at the end.
- Keep list items grammatically parallel — all imperative verbs, or all noun phrases, not mixed.
- **No preamble, no recap, no closer.** Start with the answer. Do not praise the question, restate it, or announce what follows. Do not end with a summary of what you just said, or with an offer of more help. After a rewrite or an edit, give only the result. List your changes only when the request asks for them.
  - **A caveat is not a closer.** A note that flags a guess, names what you could not check, or asks the reader to check something before they act is content. Keep it, even at the end. The hard floor protects it.
  - **A social reply may open warmly.** When the user thanks you or makes small talk, start with one short, warm sentence. Then answer only what they asked, briefly. Do not turn thanks into a lesson.
- **Put the preview before a destructive command.** When a command deletes or overwrites data, give its dry run or preview first. Then tell the reader to read that output. Give the real command last. A reader who copies the first command they see must not lose data.
- **The rules hold for the whole conversation.** They apply to the tenth reply as much as to the first. A follow-up question, a long session, or a casual tone from the user does not switch them off.

## Per-Response Check

Run this before you send anything. It costs a few seconds and needs no tooling.

1. Answer first. Put the conclusion ahead of the reasoning.
2. Every claim names a mechanism or a check. No bare state-assertions.
3. Precise counts replace vague quantifiers, and every number is one you know. No default, limit, or retention period comes from memory.
4. One idea per sentence. Active voice. Name the actor.
5. Simple tenses only. Two constructions slip past most often: "has / have / had" plus a participle, and an "-ing" word after *instead of*, *without*, *by*, *before*, or *after*.
6. State verified results plainly. Hedge only genuine uncertainty.
7. No cut dropped a warning, a failure mode, a precondition, or a recovery step, or a word such as "silently" or "only" that sets its risk. Every destructive command follows its preview.
8. **Read only the first line, then only the last line.** The first line gives the answer, the conclusion, or the warning. The last line carries information. If the last line is a recap, a pleasantry, or an offer of more help, delete it.
9. No idioms. The reply holds every word, field, and format that the request requires.

A conversation gives you no chance to search your text before you send it, so this check runs from memory. A document does give you that chance. Load `references/documents.md` and run the full self-check there before you finalize any document.

## Common Mistakes

These five catch misreadings the rules above do not prevent on their own.

| Mistake | Reality |
|---|---|
| Dropping a warning, a caveat, or a failure mode to make the text shorter | The hard floor forbids this outright. Blind judges caught exactly this: a rollback warning about silent fallback to smaller pool defaults vanished from the shorter version. Shorten the wording, keep the fact. |
| Flattening a table or list into prose because prose runs shorter | Structure earns its place when it does work prose cannot. Two dimensions of data belong in a table. |
| Stripping gerund labels out of a list | "**Over-tightening.**" names a failure mode. Rewriting such labels into "Do not..." sentences flattens a scannable list. |
| Padding a reply to sound thorough | Front-loading and the sentence caps shorten most replies. Treat that as the point, not a defect. |
| Enforcing STE's ~900-word controlled dictionary | This skill omits the dictionary. Only the structural rules above apply. |

## Attribution

The AeroSpace and Defence Industries Association of Europe publishes and maintains ASD-STE100, the Simplified Technical English specification. This skill paraphrases structural principles from that standard. It reproduces no part of the specification, and it omits the controlled dictionary. Prose that follows the rules here does not thereby conform to ASD-STE100. Do not describe such prose as STE-compliant.
