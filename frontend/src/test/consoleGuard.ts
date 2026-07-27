/**
 * Console guard — an unexpected `console.error` / `console.warn` fails the test
 * that produced it (#533).
 *
 * React and MUI report developer mistakes through `console.error` /
 * `console.warn`. Those calls return normally, so without this guard the suite
 * stays green and the warning is only visible to a human reading scrollback.
 * That is how #517, #527, #528/#530 and #531 each sat in green output for
 * months.
 *
 * How it works
 * ------------
 * `installConsoleGuard()` (called once from `setup.ts`) replaces
 * `console.error` / `console.warn` with collectors. Nothing is printed and
 * nothing throws at call time — React invokes `console.error` mid-render, and
 * throwing there cascades into misleading failures pointing at the wrong
 * component. Instead every call is recorded, and `assertConsoleClean()` runs at
 * the end of `setup.ts`'s `afterEach`, so a failure is attributed to the test
 * that finished, with the full console text quoted.
 *
 * Writing a test that logs on purpose
 * -----------------------------------
 * Declare it *before* the code that logs. The declaration both permits the
 * message and asserts it actually happened (`expectConsole*`), so a log that
 * silently stops happening is a failure too:
 *
 *     expectConsoleError('MermaidDiagram render failed:', 'the fallback path logs — #532')
 *     render(<MermaidDiagram code="invalid mermaid" />)
 *
 * Use `allowConsole*` for a log that is permitted but not guaranteed (for
 * example a React error-boundary message declared once in `beforeEach` for a
 * describe block where only some tests throw).
 *
 * To assert on what was logged, read the recorded calls rather than spying:
 *
 *     expect(consoleCallArgs('error')).toContainEqual(['Failed to load:', expect.any(Error)])
 *
 * `vi.spyOn(console, 'error')` still works and still hides output from the
 * guard, but it hides *everything* the test logs — including unrelated React
 * warnings the guard exists to catch — so prefer the declarations above.
 */
import { expect } from 'vitest'

export type ConsoleLevel = 'error' | 'warn'

/** A single recorded `console.error` / `console.warn` call. */
export interface ConsoleCall {
  level: ConsoleLevel
  /** The arguments exactly as passed, for `toContainEqual`-style assertions. */
  args: unknown[]
  /** The arguments rendered to a single string, used for matching. */
  text: string
}

/** A message a test declared it expects (`expectConsole*` / `allowConsole*`). */
interface Declaration {
  level: ConsoleLevel
  matcher: string | RegExp
  reason: string
  /** `true` for `expectConsole*`: the message must actually be logged. */
  required: boolean
  matched: boolean
}

/** A message tolerated suite-wide, for third-party logs we cannot fix. */
interface AllowlistEntry {
  level: ConsoleLevel
  /** A substring of, or narrow pattern for, the message text. Never a filename. */
  matcher: string | RegExp
  /** Why this cannot be fixed, plus a link to the upstream issue tracking it. */
  reason: string
}

/**
 * Suite-wide allowlist. Intentionally empty — the suite is silent today and the
 * point of #533 is to keep it that way.
 *
 * An allowlist nobody reviews is where warnings hide, so every entry must:
 *   1. match the specific message text — a substring or a narrow RegExp, never a
 *      file, component or test name; and
 *   2. carry a `reason` naming the third-party source and linking to the
 *      upstream issue that will let us delete the entry again.
 *
 * If the log comes from our own code, fix the code, or declare it in the test
 * with `expectConsoleError` / `expectConsoleWarn`. Do not add it here.
 */
const GLOBAL_ALLOWLIST: AllowlistEntry[] = []

let captured: ConsoleCall[] = []
let declarations: Declaration[] = []
let installed = false

function formatArg(arg: unknown): string {
  if (typeof arg === 'string') return arg
  if (arg instanceof Error) return arg.stack ?? `${arg.name}: ${arg.message}`
  if (arg === null) return 'null'
  if (arg === undefined) return 'undefined'
  if (typeof arg === 'object') {
    try {
      return JSON.stringify(arg)
    } catch {
      return String(arg)
    }
  }
  return String(arg)
}

/**
 * Render console arguments to the string the guard matches against and quotes
 * back on failure.
 *
 * Format specifiers are substituted the way a console would, because React
 * passes its warnings that way — its error-boundary report is literally
 * `console.error('%o\n\n%s\n\n%s', error, componentStack, message)`. Leaving
 * `%o` in place would force declarations to match punctuation instead of words.
 * Anything left over is appended, so no argument is ever dropped.
 */
export function formatConsoleArgs(args: unknown[]): string {
  const [first, ...rest] = args
  if (typeof first !== 'string' || !/%[sdifoOjc%]/.test(first)) {
    return args.map(formatArg).join(' ')
  }

  const remaining = [...rest]
  const formatted = first.replace(/%([sdifoOjc%])/g, (match: string, specifier: string): string => {
    if (specifier === '%') return '%'
    if (remaining.length === 0) return match
    const arg = remaining.shift()
    // %c carries CSS for browser devtools and renders as nothing.
    if (specifier === 'c') return ''
    if (specifier === 'd' || specifier === 'i') return String(Math.trunc(Number(arg)))
    if (specifier === 'f') return String(Number(arg))
    return formatArg(arg)
  })

  return [formatted, ...remaining.map(formatArg)].join(' ')
}

function matches(matcher: string | RegExp, text: string): boolean {
  return typeof matcher === 'string' ? text.includes(matcher) : matcher.test(text)
}

function describeMatcher(matcher: string | RegExp): string {
  return typeof matcher === 'string' ? JSON.stringify(matcher) : String(matcher)
}

function indent(text: string): string {
  return text.split('\n').join('\n    ')
}

function declare(
  level: ConsoleLevel,
  matcher: string | RegExp,
  reason: string,
  required: boolean
): void {
  declarations.push({ level, matcher, reason, required, matched: false })
}

/**
 * Declare that this test expects a `console.error` matching `matcher`. The
 * message is permitted, and the test fails if it never arrives.
 *
 * @param matcher Substring of, or pattern for, the expected message.
 * @param reason Why logging here is correct — shown when the log goes missing.
 */
export function expectConsoleError(matcher: string | RegExp, reason: string): void {
  declare('error', matcher, reason, true)
}

/** `expectConsoleError` for `console.warn`. */
export function expectConsoleWarn(matcher: string | RegExp, reason: string): void {
  declare('warn', matcher, reason, true)
}

/**
 * Permit a `console.error` matching `matcher` without requiring it — for logs
 * that only some tests in a shared `beforeEach` will trigger. Prefer
 * `expectConsoleError` when the log is guaranteed.
 */
export function allowConsoleError(matcher: string | RegExp, reason: string): void {
  declare('error', matcher, reason, false)
}

/** `allowConsoleError` for `console.warn`. */
export function allowConsoleWarn(matcher: string | RegExp, reason: string): void {
  declare('warn', matcher, reason, false)
}

/** Calls recorded so far in the current test, optionally filtered by level. */
export function consoleCalls(level?: ConsoleLevel): ConsoleCall[] {
  return level === undefined ? [...captured] : captured.filter((call) => call.level === level)
}

/** The argument lists recorded so far for `level`, for assertions on them. */
export function consoleCallArgs(level: ConsoleLevel): unknown[][] {
  return consoleCalls(level).map((call) => call.args)
}

/** Drop everything recorded and declared. Called for you after each test. */
export function resetConsoleGuard(): void {
  captured = []
  declarations = []
}

/**
 * Replace `console.error` / `console.warn` with collectors. Idempotent, and
 * called once from `setup.ts` before any test file is evaluated.
 */
export function installConsoleGuard(): void {
  if (installed) return
  installed = true
  console.error = (...args: unknown[]): void => {
    captured.push({ level: 'error', args, text: formatConsoleArgs(args) })
  }
  console.warn = (...args: unknown[]): void => {
    captured.push({ level: 'warn', args, text: formatConsoleArgs(args) })
  }
}

/**
 * Throw if the finished test logged anything it did not declare, or declared a
 * message with `expectConsole*` that never arrived. Recorded state is cleared
 * either way, so one failing test does not contaminate the next.
 *
 * Called at the end of `setup.ts`'s `afterEach` — after RTL `cleanup()`, so
 * warnings logged during unmount are attributed to the right test.
 */
export function assertConsoleClean(): void {
  const testName = expect.getState().currentTestName ?? 'unknown test'
  const unexpected: ConsoleCall[] = []

  for (const call of captured) {
    const declaration = declarations.find(
      (candidate) => candidate.level === call.level && matches(candidate.matcher, call.text)
    )
    if (declaration) {
      declaration.matched = true
      continue
    }
    const allowed = GLOBAL_ALLOWLIST.some(
      (entry) => entry.level === call.level && matches(entry.matcher, call.text)
    )
    if (!allowed) unexpected.push(call)
  }

  const missing = declarations.filter((declaration) => declaration.required && !declaration.matched)

  resetConsoleGuard()

  const problems: string[] = []

  if (unexpected.length > 0) {
    const quoted = unexpected.map((call) => `    console.${call.level}: ${indent(call.text)}`)
    problems.push(
      [
        `Unexpected console output during "${testName}":`,
        '',
        ...quoted,
        '',
        'Fix the code that logged it. If this test logs on purpose, declare it first:',
        `    expectConsole${unexpected[0]?.level === 'warn' ? 'Warn' : 'Error'}('some of the message above', 'why logging here is correct')`,
        'See frontend/src/test/consoleGuard.ts.',
      ].join('\n')
    )
  }

  if (missing.length > 0) {
    const quoted = missing.map(
      (declaration) =>
        `    console.${declaration.level} matching ${describeMatcher(declaration.matcher)} — ${declaration.reason}`
    )
    problems.push(
      [
        `Declared console output never happened during "${testName}":`,
        '',
        ...quoted,
        '',
        'Either the code stopped logging (fix the test or the code), or the',
        'declaration no longer matches the message text.',
      ].join('\n')
    )
  }

  if (problems.length > 0) throw new Error(problems.join('\n\n'))
}
