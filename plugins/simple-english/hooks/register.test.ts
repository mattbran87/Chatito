import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { isMarkdown, isOurSkill } from './register'

const ok = <T>(value: T) => ({ value }) as never

const DOC = '/repo/docs/guide.md'
const FINDINGS = `${DOC}   1 error, 0 review\n  ERROR  L1    [perfect] 'has been'  stacked auxiliary\n`
const CLEAN = `${DOC}   0 error, 0 review\n  clean on the rules this linter reaches\n`

type Mode = 'ok' | 'stub' | 'missing'
type World = {
  /** How `python3` behaves. By default it runs. */
  python3?: Mode
  /** How `python` behaves. By default it runs. */
  python?: Mode
  /** The linter's standard output. By default 1 ERROR finding. */
  stdout?: string
  stderr?: string
  /** By default 1, the linter's exit code when it finds an ERROR. */
  exitCode?: number
  /** The write returns an error result. */
  writeFails?: boolean
}
type Seen = { argvs: string[][]; inits: unknown[] }

// Stands in for the engine beneath the plugin.
function engine(on: On, world: World = {}): Seen {
  const seen: Seen = { argvs: [], inits: [] }
  on('process.run', (_$, e) => {
    const argv = [...(e as unknown as { argv: string[] }).argv]
    seen.argvs.push(argv)
    seen.inits.push((e as unknown as { init?: unknown }).init)
    const mode = argv[0] === 'python3' ? (world.python3 ?? 'ok') : (world.python ?? 'ok')
    if (mode === 'missing') {
      throw new Error(`spawn ${argv[0]} ENOENT`)
    }
    if (mode === 'stub') {
      return ok({ exitCode: 49, stdout: '', stderr: 'Python was not found' })
    }
    return ok({ exitCode: world.exitCode ?? 1, stdout: world.stdout ?? FINDINGS, stderr: world.stderr ?? '' })
  })
  on('skill.prompt', (_$, e) => ({ text: (e as unknown as { text: string }).text }) as never)
  on('tool.call', () => (world.writeFails ? { result: 'File has not been read yet', isError: true } : { result: {} }) as never)
  return seen
}

type Api = {
  skill: { prompt: (input: { skill: string; text: string; pluginName?: string }) => Promise<unknown> }
  tool: { call: (input: unknown) => Promise<unknown> }
}
const api = ($: unknown) => $ as Api

const loadSkill = ($: unknown, skill: string, pluginName?: string) =>
  api($).skill.prompt({ skill, text: 'x', ...(pluginName ? { pluginName } : {}) })
const write = ($: unknown, file = DOC) => api($).tool.call({ tool: 'Write', file_path: file, content: 'x' })
const edit = ($: unknown, file = DOC) => api($).tool.call({ tool: 'Edit', file_path: file, old_string: 'a', new_string: 'b' })
const said = (out: unknown): string => ((out as { context?: string[] }).context ?? []).join('\n')

describe('isOurSkill', () => {
  test('takes both skills, with or without the plugin prefix', () => {
    expect(isOurSkill('simple-english')).toBe(true)
    expect(isOurSkill('simple-english-docs')).toBe(true)
    expect(isOurSkill('simple-english:simple-english-docs')).toBe(true)
    expect(isOurSkill('superpowers:brainstorming')).toBe(false)
    expect(isOurSkill('other:simple-english')).toBe(false)
  })
})

describe('isMarkdown', () => {
  test('takes .md in any letter case and nothing else', () => {
    expect(isMarkdown('/a/README.md')).toBe(true)
    expect(isMarkdown('C:\\a\\NOTES.MD')).toBe(true)
    expect(isMarkdown('/a/notes.txt')).toBe(false)
    expect(isMarkdown('/a/md')).toBe(false)
  })
})

test('a .md write before any skill load gets no lint', async ($, on) => {
  const seen = engine(on)
  const out = await write($)
  expect(said(out)).toBe('')
  expect(seen.argvs).toHaveLength(0)
})

test('skill.prompt from another plugin does not arm', async ($, on) => {
  const seen = engine(on)
  await loadSkill($, 'simple-english', 'other-plugin')
  await write($)
  expect(seen.argvs).toHaveLength(0)
})

test('skill.prompt arms the hook, and a .md write gets pass 1 of 2', async ($, on) => {
  const seen = engine(on)
  await loadSkill($, 'simple-english:simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain(`simple-english lint, pass 1 of 2 for ${DOC}`)
  expect(said(out)).toContain("[perfect] 'has been'")
  expect(said(out)).toContain('Fix every ERROR')
  const argv = seen.argvs[0] ?? []
  expect(argv[0]).toBe('python3')
  expect(argv[1]).toMatch(/skills\/simple-english-docs\/scripts\/ste_lint\.py$/)
  expect(argv.slice(2)).toEqual(['--quiet', DOC])
})

test('a Skill tool call arms the hook too', async ($, on) => {
  engine(on)
  await api($).tool.call({ tool: 'Skill', skill: 'simple-english-docs' })
  const out = await write($)
  expect(said(out)).toContain('pass 1 of 2')
})

test('an Edit counts as a write', async ($, on) => {
  engine(on)
  await loadSkill($, 'simple-english-docs')
  const out = await edit($)
  expect(said(out)).toContain('pass 1 of 2')
})

test('a clean file reports no findings', async ($, on) => {
  engine(on, { stdout: CLEAN, exitCode: 0 })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain('pass 1 of 2')
  expect(said(out)).toContain('no findings')
  expect(said(out)).not.toContain('Fix every ERROR')
})

test('the second write is pass 2 of 2, and the third gets no lint', async ($, on) => {
  const seen = engine(on)
  await loadSkill($, 'simple-english-docs')
  await write($)
  const second = await write($)
  expect(said(second)).toContain('pass 2 of 2')
  expect(said(second)).toContain('last lint for this file')
  const third = await write($)
  expect(said(third)).toBe('')
  expect(seen.argvs).toHaveLength(2)
})

test('the pass count is per file', async ($, on) => {
  engine(on)
  await loadSkill($, 'simple-english-docs')
  await write($)
  const other = await write($, '/repo/README.md')
  expect(said(other)).toContain('pass 1 of 2 for /repo/README.md')
})

test('a new skill load starts the count again', async ($, on) => {
  engine(on)
  await loadSkill($, 'simple-english-docs')
  await write($)
  await write($)
  await loadSkill($, 'simple-english')
  const out = await write($)
  expect(said(out)).toContain('pass 1 of 2')
})

test('a .txt write gets no lint', async ($, on) => {
  const seen = engine(on)
  await loadSkill($, 'simple-english-docs')
  const out = await write($, '/repo/notes.txt')
  expect(said(out)).toBe('')
  expect(seen.argvs).toHaveLength(0)
})

test('a write that returns an error gets no lint', async ($, on) => {
  const seen = engine(on, { writeFails: true })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toBe('')
  expect(seen.argvs).toHaveLength(0)
})

test('python3 exit 49 falls back to python', async ($, on) => {
  const seen = engine(on, { python3: 'stub' })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(seen.argvs.map(a => a[0])).toEqual(['python3', 'python'])
  expect(said(out)).toContain('pass 1 of 2')
})

test('python3 that cannot start falls back to python', async ($, on) => {
  const seen = engine(on, { python3: 'missing' })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(seen.argvs.map(a => a[0])).toEqual(['python3', 'python'])
  expect(said(out)).toContain('pass 1 of 2')
})

test('no Python says the lint did not run and keeps the write result', async ($, on) => {
  engine(on, { python3: 'missing', python: 'missing' })
  await loadSkill($, 'simple-english-docs')
  const out = (await write($)) as { result?: unknown; isError?: boolean }
  expect(said(out)).toContain('simple-english lint did not run: no Python found')
  expect(out.isError).not.toBe(true)
  expect(out.result).toEqual({})
})

test('a linter crash says the lint did not run', async ($, on) => {
  engine(on, { stdout: '', stderr: 'Traceback (most recent call last):\nFileNotFoundError: x', exitCode: 1 })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain('simple-english lint did not run: the linter failed: FileNotFoundError: x')
})

test('the linter runs with UTF-8 output, so a non-ASCII file name does not crash it', async ($, on) => {
  const seen = engine(on)
  await loadSkill($, 'simple-english-docs')
  await write($, '/repo/日本.md')
  expect(seen.inits[0]).toMatchObject({ env: { PYTHONUTF8: '1' } })
})

test('the pass count ignores slash direction and letter case', async ($, on) => {
  engine(on)
  await loadSkill($, 'simple-english-docs')
  await write($, 'C:\\a\\b.md')
  const out = await write($, 'c:/a/B.md')
  expect(said(out)).toContain('pass 2 of 2 for c:/a/B.md')
})

test('both Pythons exiting 49 name both in the reason', async ($, on) => {
  engine(on, { python3: 'stub', python: 'stub' })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain('no Python found (python3: exited 49, python: exited 49)')
})

test('a start failure records the python name and a message', async ($, on) => {
  engine(on, { python3: 'missing', python: 'missing' })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain('no Python found (python3: ')
})

test('a clean-looking line inside a finding does not count as clean', async ($, on) => {
  engine(on, { stdout: `${DOC}   1 error, 0 review\n  ERROR  L1  text with 0 error, 0 review inside\n` })
  await loadSkill($, 'simple-english-docs')
  const out = await write($)
  expect(said(out)).toContain('Fix every ERROR')
})
