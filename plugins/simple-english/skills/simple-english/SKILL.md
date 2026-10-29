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
- **Use the literal word, not a picture.** If a word makes the reader picture something that is not there, write what the thing does or what state it is in:
  - "the old key is dead" → "the old key no longer works"
  - "leaves the old price live" → "the old price still shows"
  - "ran clean for hours" → "ran for 3 hours with no errors"
  - "Browsers check back on each visit" → "The browser sends a new request on each visit"
  - "out of the box" → "by default"

  A term that is the field's name for a thing stays, even when it began as a picture: "race condition," "bottleneck," "cache lifetime." An ordinary word that you put on a technical noun as a description does not stay, even when the field uses it in another term. A figurative word makes a reader who learned English as a second language guess.
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
9. Read each verb and adjective that describes a technical noun as a reader who translates word by word. If the literal meaning is wrong for that noun, replace the word. The reply holds every word, field, and format that the request requires.

A conversation gives you no chance to search your text before you send it, so this check runs from memory. A document does give you that chance. Load `references/documents.md` and run the full self-check there before you finalize any document.

## Common Mistakes

These seven catch misreadings the rules above do not prevent on their own.

| Mistake | Reality |
|---|---|
| Dropping a warning, a caveat, or a failure mode to make the text shorter | The hard floor forbids this, so shorten the wording and keep the fact: blind judges caught a shorter version that dropped a rollback warning about silent fallback to smaller pool defaults. |
| Flattening a table or list into prose because prose runs shorter | Keep structure that does work prose cannot, such as two dimensions of data in a table. |
| Stripping gerund labels out of a list | "**Over-tightening.**" names a failure mode, and a rewrite into "Do not..." sentences flattens a scannable list. |
| Padding a reply to sound thorough | Front-loading and the sentence caps shorten most replies, and that is the point, not a defect. |
| Enforcing STE's ~900-word controlled dictionary | This skill omits the dictionary, so only the structural rules above apply. |
| Labeling every reply, or every risk in a reply | A label marks the exception, so most replies need none, and the reader stops seeing labels that appear everywhere. |
| Bolding a whole sentence for weight | A bold sentence is a label without a name, so give it the label that fits, or bold only the word that sets its risk. |

## Attribution

The AeroSpace and Defence Industries Association of Europe publishes and maintains ASD-STE100, the Simplified Technical English specification. This skill paraphrases structural principles from that standard. It reproduces no part of the specification, and it omits the controlled dictionary. Prose that follows the rules here does not thereby conform to ASD-STE100. Do not describe such prose as STE-compliant.
