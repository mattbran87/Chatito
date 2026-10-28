import type { EngineInterface, Register } from 'claude-code'

const PLUGIN = 'simple-english'
const SKILLS = ['simple-english', 'simple-english-docs']
const ARMED = { plugin: 'simple-english', key: 'armed' } as const
const COUNTS = { plugin: 'simple-english', key: 'lintCounts' } as const
const MAX_PASSES = 2
const STUB_EXIT = 49
const LINTER = 'skills/simple-english-docs/scripts/ste_lint.py'
const PYTHONS = ['python3', 'python']

/** True for a skill of this plugin, named with or without the `simple-english:` prefix. */
export function isOurSkill(name: string): boolean {
  const bare = name.startsWith(`${PLUGIN}:`) ? name.slice(PLUGIN.length + 1) : name
  return SKILLS.includes(bare)
}

/** True for a Markdown path, in any letter case. */
export function isMarkdown(path: string): boolean {
  return path.toLowerCase().endsWith('.md')
}

/**
 * Arms the lint hook for this session and starts each file's pass count again.
 * Both hooks may fire for one load, and running `arm` twice is harmless.
 */
async function arm($: EngineInterface): Promise<void> {
  await $.state.set(ARMED, true)
  await $.state.set(COUNTS, {})
}

type Run = { exitCode: number; stdout: string; stderr: string }

/** The last non-empty line of a text, such as the exception line of a traceback. */
function lastLine(text: string): string {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(line => line !== '')
  return lines[lines.length - 1] ?? 'no error text'
}

/** The context text for one lint pass. `stdout` is the linter's `--quiet` output. */
export function report(file: string, pass: number, stdout: string): string {
  const header = `simple-english lint, pass ${pass} of ${MAX_PASSES} for ${file}`
  if (/ 0 error, 0 review$/m.test(stdout)) {
    return `${header}\nno findings`
  }
  const next = pass < MAX_PASSES
    ? 'The hook lints this file once more after your next write to it.'
    : 'This was the last lint for this file. Stop after these fixes.'
  return `${header}\n${stdout.trim()}\nFix every ERROR. For each review hit, change the text only when the change reads better. ${next}`
}

/** Runs the linter on one file. Returns the run, or the reason it did not run. */
async function runLinter($: EngineInterface, file: string): Promise<Run | string> {
  const args = [`${$.plugin.root}/${LINTER}`, '--quiet', file]
  const problems: string[] = []
  for (const python of PYTHONS) {
    let run: Run
    try {
      run = await $.process.run([python, ...args], { env: { PYTHONUTF8: '1' } })
    } catch (error) {
      // The types do not tell a start failure from a timeout, so both record
      // the message and fall through to the next Python.
      problems.push(`${python}: ${error instanceof Error ? error.message : String(error)}`)
      continue
    }
    if (run.exitCode === STUB_EXIT) {
      problems.push(`${python}: exited ${STUB_EXIT}`)
      continue
    }
    if (run.exitCode > 1 || run.stderr.includes('Traceback')) {
      return `the linter failed: ${lastLine(run.stderr)}`
    }
    return run
  }
  return `no Python found (${problems.join(', ')})`
}

type Outcome = { deny?: string; isError?: boolean; context?: readonly string[] }

/** Adds a lint report to a finished write of a Markdown file. Never throws, never denies. */
async function lintAfter<R extends Outcome>($: EngineInterface, file: string, ran: R): Promise<R> {
  if (ran.deny !== undefined || ran.isError === true || !isMarkdown(file)) {
    return ran
  }
  let text: string
  try {
    const { value: armed } = await $.state.get(ARMED)
    if (armed !== true) {
      return ran
    }
    const { value: counts = {} } = await $.state.get(COUNTS)
    const key = file.replace(/\\/g, '/').toLowerCase()
    const pass = (counts[key] ?? 0) + 1
    if (pass > MAX_PASSES) {
      return ran
    }
    await $.state.set(COUNTS, { ...counts, [key]: pass })
    const run = await runLinter($, file)
    text = typeof run === 'string' ? `simple-english lint did not run: ${run}` : report(file, pass, run.stdout)
  } catch (error) {
    text = `simple-english lint did not run: ${error instanceof Error ? error.message : String(error)}`
  }
  return { ...ran, context: [...(ran.context ?? []), text] }
}

export const register: Register = on => {
  // skill.prompt does not run for user-installed plugins where an organization
  // manages Claude Code, so the Skill tool hook below arms the session too.
  // pluginName undefined is accepted on purpose: a --plugin-dir load or a test may leave it unset.
  on('skill.prompt', async ($, e, next) => {
    if (isOurSkill(e.skill) && (e.pluginName === undefined || e.pluginName === PLUGIN)) {
      await arm($)
    }
    return next(e)
  })

  on('tool.call', { tool: 'Skill' }, async ($, e, next) => {
    if (isOurSkill(e.skill)) {
      await arm($)
    }
    return next(e)
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => lintAfter($, e.file_path, await next(e)))
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => lintAfter($, e.file_path, await next(e)))
}
