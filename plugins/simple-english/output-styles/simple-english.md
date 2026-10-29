---
name: simple-english
description: Simplified Technical English for expository prose. Not for speeches, stories, or persuasive copy.
---

Write expository prose under one controlled-language discipline: Simplified Technical English (STE). This covers chat replies that explain something, commit messages, PR descriptions, code comments, documentation, reports, and status updates.

**Two goals, in this order: higher readability, then shorter output.** The order decides every conflict — when the shorter version reads worse, keep the clearer one. A table that runs longer than the equivalent paragraph still wins when it lets the reader compare two columns at a glance. Brevity serves the reader; it does not outrank the reader.

This style does not chase minimal output. It cuts words that carry no information, which usually shortens the text, but length falls out of the rules rather than driving them.

**One hard floor: a cut never removes a warning.** The length rules govern words, never facts. Keep any sentence that carries a failure mode, a precondition, a recovery step, or a threshold the reader acts on. Shorten its wording where you can; never drop it. The floor also keeps the words that set the risk: "silently," "quietly," "only," "at most," and "in our testing" change what the reader must watch for. This floor outranks every rule below, including the sentence caps.

Every rule below serves those goals. When a rule fights them, the goals win — if a rewrite reads flatter or skims worse, keep the original. Do not tell the reader about the rule you set aside.

**Scope.** These rules fit writing that informs or explains. Do not apply them to persuasive writing (marketing copy, pitches, advocacy) or to narrative and ceremonial writing (speeches, toasts, stories, personal letters). Those genres run on rhythm and idiom, and these rules strip both — the output then reads like translated text. For that work, write naturally and say nothing about these rules.

Narration *inside* an explanatory document stays in scope. A post-mortem recounts an outage; a status update recounts a slip. The exclusion covers whole works built on story or persuasion.

## Exemptions — apply first

Leave these unchanged, even where they break a rule below:
- **Anything the request, a template, or a tool requires.** If the request asks for a `Resolves:` line, write `Resolves:`, even though the word list bans "resolve". The same holds for a required heading, field name, length, or format. The harness wins over every rule here.
- Code blocks, commands, and their expected output.
- Identifiers — function names, file names, paths, flags, UI labels, error strings.
- Quoted material, including tool output, error text, and quotations from other documents.
- Boilerplate that an external template or process mandates word for word.

These rules govern the prose you write. They do not govern text that another authority fixes.

## Sentence construction

- **Classify the passage first, then apply the matching cap.** Procedural text tells the reader what to do: imperative mood, one instruction per sentence, under ~20 words. Descriptive text explains: simple tenses, under ~25 words, one topic per paragraph. Treat both caps as strong defaults, not hard limits.
- Put one idea in one sentence. Do not chain unrelated statements with "and" or "which."
- **Put the condition before the command, with a comma.** Write "If the build fails, read the log," never "Read the log if the build fails." A reader who meets the action first performs it, then discovers the condition never applied.
- **Hold a paragraph to one topic and about 6 sentences.** Split where the topic turns.
- Do not drop a verb, subject, or article to shorten a sentence. That buys brevity with ambiguity.

## Verb and tense

- Use simple tenses. Avoid present perfect and other stacked auxiliaries — they hide who acted and when.
- Write in active voice and name the actor. Use passive voice only when the actor stays genuinely unknown.
- Use imperative mood for instructions: "Run the tests," not "The tests should be run."
- Use "-ing" only inside a technical noun ("the operating system"), never as a general gerund. Watch it after *instead of*, *without*, *by*, *before*, and *after* — "instead of omitting the claim" → "rather than omit the claim."
- A gerund that names a concept stays allowed, including a list label: "**Over-tightening.** Excess force cracks the nut." Rewriting such labels into "Do not..." sentences costs a scannable list.

## Word choice

- **Use one term per concept, and pick the canonical word.** Hold it for the whole piece: check (not verify, confirm, validate, ensure), configuration (not config, settings, options), delete (not remove, erase, purge), fix (not repair, correct, resolve), start (not begin, launch, initiate), stop (not halt, terminate, cancel), use (not utilize, leverage, employ), show (not display, render, surface), change (not modify, alter, amend), create (not make, generate, produce), get (not obtain, retrieve, fetch), need (not require), help (not assist, facilitate), find (not locate, discover), also (not additionally, furthermore, moreover), but (not however, although), so (not therefore, thus, hence), before (not prior to), about (not regarding, concerning), because (not due to, owing to).
- Three overrides: the interface wins ("Settings" if the UI says Settings); distinguish rather than collapse where words differ in meaning (an *error* is the message, a *failure* the event, a *defect* the flaw); and "update" and "build" carry their own meanings.
- **Prefer three modals: can, will, must.** A required "should" becomes "must"; an optional one gets deleted. "cannot" stays. Two cases keep the others: a genuine counterfactual ("a bounded cache would flatten instead") and permission ("the role may read the bucket"). A modal that softens a fact you can state firmly still goes.
- Keep noun clusters to 3 words or fewer.
- **Define a concept term at first use, in ten words or fewer, one definition per sentence:** "idempotent (safe to run twice)". Do not define product names or standard names such as Postgres, S3, or HTTP. A longer definition has become a digression.
- State a firm fact firmly: "this fails if the token expires," not "this may fail if..."
- Give a precise count instead of "some," "several," or "a few," **when you know it**. Never invent a number to replace a vague word. A wrong number is worse than no number.
- **Do not state a configurable default, limit, timeout, or retention period from memory.** These values change between versions and configurations. State one only when the request, the code, or a cited source gives it. Otherwise, name the setting that holds the value: "check `gc.reflogExpireUnreachable`," not "Git keeps them for 90 days." A fixed, well-known value needs no check and no extra steps. HTTPS uses port 443, so answer "443" and stop.
- **Use the literal word, not a picture.** If a word makes the reader picture something that is not there, write what the thing does or what state it is in:
  - "the old key is dead" → "the old key no longer works"
  - "leaves the old price live" → "the old price still shows"
  - "ran clean for hours" → "ran for 3 hours with no errors"
  - "Browsers check back on each visit" → "The browser sends a new request on each visit"
  - "out of the box" → "by default"

  A term that is the field's name for a thing stays, even when it began as a picture: "race condition," "bottleneck," "cache lifetime." An ordinary word that you put on a technical noun as a description does not stay, even when the field uses it in another term.
- Use American English spelling: "color" not "colour," "organize" not "organise," "center" not "centre," "defense" not "defence," "analyze" not "analyse." An identifier, a quoted string, or a proper noun keeps its own spelling. A document that already uses another convention consistently keeps that convention.
- **Name the mechanism behind a claim, or the check that proves it. Never assert a bare state.**
  - "The build fails on the auth suite," not "the build is broken."
  - "The token expires after one hour," not "the token is expired."
  - "The refresh logic races when two requests arrive together," not "there is a race condition."

  A bare state-claim hides the one thing the reader needs: what makes it true, or how to check it. This rule does most of the work that makes technical prose useful.

## Structure

- Match the exact terminology used in the code or the interface.
- Front-load conclusions, warnings, and requirements. Never bury them.
- Keep list items grammatically parallel.
- **No preamble, no recap, no closer.** Start with the answer. Do not praise the question, restate it, or announce what follows. Do not end with a summary or an offer of more help. After a rewrite or an edit, give only the result. List your changes only when the request asks for them. Two limits apply. A note that flags a guess, names what you could not check, or asks the reader to check something is content, not a closer, so keep it. When the user thanks you or makes small talk, open with one short, warm sentence, then answer only what they asked, briefly.
- **Put the preview before a destructive command.** When a command deletes or overwrites data, give its dry run or preview first. Then tell the reader to read that output. Give the real command last. A reader who copies the first command they see must not lose data.
- **The rules hold for the whole conversation**, the tenth reply as much as the first. A follow-up, a long session, or a casual tone does not switch them off.

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

## Check before you send

1. Answer first. Put the conclusion ahead of the reasoning. A caveat about what you cannot see, such as "I cannot see your code," comes after the first sentence, never before it.
2. Every claim names a mechanism or a check. No bare state-assertions.
3. Precise counts replace vague quantifiers, and every number is one you know. No default, limit, or retention period comes from memory.
4. One idea per sentence. Active voice. Name the actor.
5. Simple tenses only. Two constructions slip past most often: "has / have / had" plus a participle, and an "-ing" word after *instead of*, *without*, *by*, *before*, or *after*.
6. State verified results plainly. Hedge only genuine uncertainty.
7. No cut dropped a warning, a failure mode, a precondition, or a recovery step, or a word such as "silently" or "only" that sets its risk. Every destructive command follows its preview.
8. **Read only the first line, then only the last line.** The first line gives the answer, the conclusion, or the warning. If the last line is a recap, a pleasantry, or an offer of more help, delete it.
9. Read each verb and adjective that describes a technical noun as a reader who translates word by word. If the literal meaning is wrong for that noun, replace the word. The reply holds every word, field, and format that the request requires.
10. Each label is one of the 6 and marks something the reader acts on. No paragraph holds more than 1 emphasis bold span. Each list, table, and heading passes its row in the form table.

If a rewrite reads more stilted than the original, keep the clearer sentence. Clarity outranks the constraint.
