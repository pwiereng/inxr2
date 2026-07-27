/**
 * Meta-test for the console guard (#533).
 *
 * This is the test that fails if enforcement regresses. It drives the *live*
 * hook installed by `setup.ts` — every `console.error` below goes through the
 * real collector — and then calls `assertConsoleClean()`, the same function
 * `setup.ts` runs in `afterEach`. If someone removes the hook, stops recording,
 * or stops throwing, these tests go red.
 *
 * Each case that deliberately dirties the guard calls `assertConsoleClean()`
 * itself, which clears the recorded state, so the real `afterEach` that follows
 * sees a clean slate.
 */
import { describe, it, expect } from 'vitest'
import {
  allowConsoleError,
  assertConsoleClean,
  consoleCallArgs,
  consoleCalls,
  expectConsoleError,
  expectConsoleWarn,
  resetConsoleGuard,
} from './consoleGuard'

describe('console guard', () => {
  it('records console.error instead of printing it', () => {
    console.error('probe: recorded, not printed')

    expect(consoleCalls('error').map((call) => call.text)).toEqual(['probe: recorded, not printed'])

    resetConsoleGuard()
  })

  it('fails the test that logged an undeclared console.error', () => {
    console.error('undeclared boom')

    expect(() => assertConsoleClean()).toThrowError(/undeclared boom/)
  })

  it('fails the test that logged an undeclared console.warn', () => {
    console.warn('undeclared murmur')

    expect(() => assertConsoleClean()).toThrowError(/undeclared murmur/)
  })

  it('names the offending test and quotes the full message', () => {
    console.error('Warning: Each child in a list should have a unique "key" prop.', {
      component: 'FileTree',
    })

    let message = ''
    try {
      assertConsoleClean()
    } catch (error) {
      message = error instanceof Error ? error.message : String(error)
    }

    // Attribution: the failure must name the test that produced the output...
    expect(message).toContain(
      'console guard > names the offending test and quotes the full message'
    )
    // ...and reproduce the console text in full, extra arguments included.
    expect(message).toContain('Warning: Each child in a list should have a unique "key" prop.')
    expect(message).toContain('{"component":"FileTree"}')
    // ...and point at the opt-out, so the fix is obvious from the failure alone.
    expect(message).toContain('expectConsoleError')
  })

  it('passes when the message was declared with expectConsoleError', () => {
    expectConsoleError('declared boom', 'the meta-test logs this on purpose')
    console.error('declared boom', new Error('detail'))

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('passes when the message was declared with expectConsoleWarn', () => {
    expectConsoleWarn(/declared \d+ murmur/, 'RegExp matchers are supported')
    console.warn('declared 42 murmur')

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('fails when a declared message never arrives', () => {
    expectConsoleError('never logged', 'proves expectConsoleError also asserts')

    expect(() => assertConsoleClean()).toThrowError(/never happened/)
  })

  it('tolerates an allowed message that never arrives', () => {
    allowConsoleError('optional log', 'allowConsole* permits without requiring')

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('still fails on a second, undeclared message alongside a declared one', () => {
    expectConsoleError('declared boom', 'the meta-test logs this on purpose')
    console.error('declared boom')
    console.error('sneaky extra warning')

    let message = ''
    try {
      assertConsoleClean()
    } catch (error) {
      message = error instanceof Error ? error.message : String(error)
    }

    expect(message).toContain('sneaky extra warning')
    expect(message).not.toContain('declared boom')
  })

  // Regression cover for the review finding on #536: matching used to be
  // "first registered wins", so a broad declaration could absorb the call a
  // later, more specific one was declared for — and the specific one was then
  // reported as never having happened, purely because of registration order.
  it('satisfies a specific declaration that a broader one would have absorbed', () => {
    expectConsoleError('foo', 'broad declaration, registered first')
    expectConsoleError('foobar extra text', 'specific declaration, registered second')
    console.error('foobar extra text')
    console.error('foo on its own')

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('satisfies duplicate declarations from the same message', () => {
    // Declarations are satisfied as a set, not paired off against calls, so a
    // duplicate declaration is redundant rather than an unmet expectation.
    expectConsoleError('dup', 'first of two identical declarations')
    expectConsoleError('dup', 'second of two identical declarations')
    console.error('dup')

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('permits repeats of a message once its declaration is satisfied', () => {
    expectConsoleError('chatty', 'one declaration covers every repeat')
    console.error('chatty')
    console.error('chatty')
    console.error('chatty')

    expect(() => assertConsoleClean()).not.toThrow()
  })

  it("substitutes React's %o/%s format specifiers into the message text", () => {
    // React reports a caught error as console.error('%o\n\n%s\n\n%s', …), so the
    // guard has to format it or declarations would have to match punctuation.
    expectConsoleError(
      'The above error occurred in the <Widget> component',
      'the meta-test logs this on purpose'
    )
    console.error(
      '%o\n\n%s\n\n%s',
      new Error('kaboom'),
      '\n    at Widget',
      'The above error occurred in the <Widget> component.'
    )

    expect(consoleCalls('error')[0]?.text).toContain('kaboom')
    expect(consoleCalls('error')[0]?.text).not.toContain('%o')
    expect(() => assertConsoleClean()).not.toThrow()
  })

  it('exposes the raw arguments for assertions', () => {
    const detail = new Error('detail')
    expectConsoleError('args probe', 'the meta-test logs this on purpose')
    console.error('args probe:', detail)

    expect(consoleCallArgs('error')).toContainEqual(['args probe:', detail])
    expect(consoleCallArgs('warn')).toEqual([])

    assertConsoleClean()
  })

  // The pair below pins the *wiring*, not just the logic. Every case above calls
  // assertConsoleClean() itself, so they would all still pass if someone dropped
  // the call from setup.ts's afterEach. This one deliberately does not clean up:
  // only setup.ts can clear what it leaves behind.
  it('leaves a declared message recorded, without cleaning up after itself', () => {
    expectConsoleError('wiring probe', 'the meta-test logs this on purpose')
    console.error('wiring probe')

    expect(consoleCalls('error')).toHaveLength(1)
  })

  it('starts clean, because setup.ts runs assertConsoleClean after every test', () => {
    // Fails if the afterEach wiring in setup.ts is removed: the message the
    // previous test left recorded would still be here.
    expect(consoleCalls()).toEqual([])
  })
})
