# Chatito

Chatito is a Simplified Technical English plugin for Claude. It puts
readability first. Output gets shorter as a side effect of the language
rules, not as a goal.

The plugin, `simple-english`, holds 2 skills, a linter, and an opt-in output
style. The [plugin README](plugins/simple-english/README.md) describes the
rules and their use.

## Install in Claude Code

```
/plugin marketplace add mattbran87/Chatito
/plugin install simple-english@chatito
```

Skills load when the session starts. In a session already running, use
`/reload-plugins`, or restart Claude Code.

## Install in Claude Desktop

Use one of 2 routes in the Chat tab:

- **Marketplace.** Open **Customize → Plugins → Add → Add marketplace**,
  choose **Add from a repository**, and enter `mattbran87/Chatito`. Then
  install `simple-english`.
- **Zip.** Download `simple-english-<version>.zip` from the latest
  [release](https://github.com/mattbran87/Chatito/releases). Open
  **Customize → Plugins → Add**, and upload the zip. A zip install gets no
  updates, so upload each new release by hand.

In Desktop chat, the rules apply only when a skill triggers. The output style
does not load there. The nearest equivalent is a line in your Project
instructions that asks Claude to use the simple-english skill for every
reply. That route has no test yet.

The linter needs code execution. If it does not run, check **Settings →
Capabilities**.

## Versions

Each release sets `version` in `plugins/simple-english/.claude-plugin/plugin.json`.
Claude Code updates an installed plugin only when that number goes up. The
[CHANGELOG](plugins/simple-english/CHANGELOG.md) lists the changes.

## Contributions

Chatito is a release mirror. Development happens in a private repository, and
each release replaces every file here. So a commit made here does not survive
the next release.

- Issues are welcome.
- A pull request gets a hand port into the development repository. Its change
  ships in the next release, not as a merge here.

## License

MIT. See [LICENSE](LICENSE).
