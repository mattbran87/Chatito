# simple-english

Applies Simplified Technical English (STE) to expository writing: chat replies
that explain something, commit messages, PR descriptions, code comments, and
documents. It raises readability first and cuts length second. When the shorter
version reads worse, Claude keeps the clearer one.

The plugin ships the same rules in 3 forms:

| Component | Applies to | Turns on |
| --- | --- | --- |
| `simple-english:simple-english` skill | Chat replies and documents | When Claude invokes it, or when you type `/simple-english:simple-english` |
| `simple-english:simple-english-docs` skill | Project documents only | When Claude invokes it for a README, spec, design doc, or report |
| `simple-english:simple-english` output style | Every reply in the session | When you select it in `/output-style` |

**Use one skill, not both.** The two skills carry the same rules with a
different scope, and `simple-english` says to choose it instead of a
document-only skill. If you want the rules in documents only, turn off
`simple-english:simple-english` (see [Turn a skill off](#turn-a-skill-off)).
Otherwise, turn off `simple-english:simple-english-docs`.

## Install

With the `chatito` marketplace added (`/plugin marketplace add mattbran87/Chatito`):

```
/plugin install simple-english@chatito
```

Skills load when the session starts. In a session already running, use
`/reload-plugins`, or restart Claude Code.

**If you have personal copies, delete them after you install.** The personal
copies live in `~/.claude/skills/simple-english/`,
`~/.claude/skills/simple-english-docs/`, and
`~/.claude/output-styles/simple-english.md`. If you keep them, Claude sees each
skill twice, and the two copies drift apart.

## Install in Claude Desktop

In the Chat tab of Claude Desktop, open **Customize → Plugins → Add → Add
marketplace**, and add the marketplace from its repository. A private
repository needs the GitHub connector. If your organization has it off,
Desktop refuses the repository with "GitHub is not enabled for your
organization."

Without the connector, install from a zip:

1. Download `simple-english-<version>.zip` from the
   [Chatito releases](https://github.com/mattbran87/Chatito/releases).
2. Open **Customize → Plugins → Add**, and upload the zip.

A zip install gets no updates. Upload each new release by hand.

The skills and the linter work in Desktop chat. The linter needs code
execution, which **Settings → Capabilities** turns on. The output style does
not load in Desktop chat, so the rules apply only when a skill triggers.

## Turn on the output style

The output style does not turn on by itself. Run the picker and select
`simple-english:simple-english`:

```
/output-style
```

The picker saves your choice in the current project only, in
`.claude/settings.local.json`. To use the style in every project, set it in
`~/.claude/settings.json`:

```json
{
  "outputStyle": "simple-english:simple-english"
}
```

If that file sets `"outputStyle": "simple-english"`, the value points at the
personal copy. After you delete the personal copy, change the value as shown
above. Otherwise, every other project falls back to the default style.

## What changes

| Without the rules | With the rules |
| --- | --- |
| The build is broken. | The build fails on the auth suite. |
| Several tests are failing. | Three tests fail in `auth_test.py`. |
| The migration has been applied to staging by the deploy job. | The deploy job applied the migration to staging. |

Code blocks, commands, identifiers, quoted output, and error text stay
unchanged.

The rules do not apply to persuasive writing (marketing copy, pitches) or to
narrative and ceremonial writing (speeches, stories, personal letters). They
strip the rhythm those genres depend on.

## The linter

Each skill carries its own copy of `scripts/ste_lint.py`, because a skill
cannot read files from another skill's folder. The two copies must stay
identical. If you change one, copy it over the other.

The linter checks the 16 rules that a search can reach: 10 about words and sentences, and 6 about labels, emphasis, lists, and tables. It needs Python 3.8
and the standard library only. Without Python, the skills still work and fall
back to search patterns that Claude runs by hand.

Run the self-test after you change the linter. It must report
`32 passed, 0 failed`:

```
python3 plugins/simple-english/skills/simple-english/scripts/ste_lint.py --selftest
```

A clean linter run does not mean a clean document. Noun clusters, list
parallelism, front-loading, and undefined jargon still need a read.

## Lint hook

In Claude Code, a hook runs the linter for you. It starts after Claude loads `simple-english` or `simple-english-docs` in a session. From then on, each `Write` or `Edit` of a `.md` file runs `skills/simple-english-docs/scripts/ste_lint.py --quiet` on that file. Claude reads the findings after the tool result. You do not see them.

The hook lints each file at most 2 times, the same limit as the skills' "stop after this second pass". A new skill load starts the count again. If no Python starts, or the linter fails, Claude reads `simple-english lint did not run` and the reason. Then the skills tell Claude to run the linter itself. A pass that did not run still counts toward the 2. The write always completes.

The hook does not see a file that a shell command writes, such as `cat > notes.md`. Where an organization manages Claude Code, a skill started by its slash command does not start the hook. The hook starts when Claude loads the skill through the Skill tool. Once a skill loads, the hook lints every Markdown file Claude writes in that session, such as a CHANGELOG or a plan, not only the document you asked for.

Claude Desktop shows hooks grayed out in chat, so Desktop chat users get the skill wording and the `Lint:` line, not the hook. There, the skills tell Claude to write the document to a file, lint it, and end the reply with a `Lint:` line. A reply with no `Lint:` line tells you the check did not run.

## Turn a skill off

Add this to `~/.claude/settings.json`, or to `.claude/settings.json` in one
project. Merge the key into the file; do not replace the file.

```json
{
  "skillOverrides": {
    "simple-english:simple-english-docs": "off"
  }
}
```

`off` hides the skill completely. `user-invocable-only` stops Claude from
invoking it and keeps the slash command. Restart Claude Code after the edit.

## Evals

`evals/` holds a harness that runs 20 cases with and without the rules, and
scores the responses with the linter, a blind Claude judge, and Jev. Use it
before you change a rule. See [evals/README.md](evals/README.md).

## Attribution

The AeroSpace and Defence Industries Association of Europe publishes and
maintains ASD-STE100, the Simplified Technical English specification. These
skills paraphrase structural principles from that standard. They reproduce no
part of the specification and omit the controlled dictionary. Prose that
follows these rules does not thereby conform to ASD-STE100.
