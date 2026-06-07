import { describe, it, expect } from 'vitest'
import {
  splitCommitMessage,
  makeLoadKey,
  shouldLoadCommits,
  buildCommitBrowseTarget,
} from './commitHistory'

describe('splitCommitMessage', () => {
  it('returns summary only when there is no body', () => {
    expect(splitCommitMessage('Fix the bug')).toEqual({ summary: 'Fix the bug', body: '' })
  })

  it('splits summary and multiline body', () => {
    const msg = 'Add feature\n\nThis is the body.\nWith two lines.'
    expect(splitCommitMessage(msg)).toEqual({
      summary: 'Add feature',
      body: 'This is the body.\nWith two lines.',
    })
  })

  it('handles an empty string', () => {
    expect(splitCommitMessage('')).toEqual({ summary: '', body: '' })
  })

  it('trims leading and trailing blank lines from the body', () => {
    const msg = 'Summary\n\n\n  Body text  \n\n'
    expect(splitCommitMessage(msg)).toEqual({ summary: 'Summary', body: 'Body text' })
  })

  it('keeps a summary line with no following body as empty body', () => {
    const msg = 'Summary\n'
    expect(splitCommitMessage(msg)).toEqual({ summary: 'Summary', body: '' })
  })

  it('handles CRLF line endings (summary keeps trailing CR, body trimmed)', () => {
    const msg = 'Summary\r\nBody line'
    // split('\n') leaves a trailing \r on the summary; body is trimmed.
    expect(splitCommitMessage(msg)).toEqual({ summary: 'Summary\r', body: 'Body line' })
  })
})

describe('makeLoadKey', () => {
  it('includes the branch when present', () => {
    expect(makeLoadKey('myrepo', 'main')).toBe('myrepo:main')
  })

  it('collapses null branch to an empty segment', () => {
    expect(makeLoadKey('myrepo', null)).toBe('myrepo:')
  })

  it('collapses undefined branch to an empty segment', () => {
    expect(makeLoadKey('myrepo', undefined)).toBe('myrepo:')
  })
})

describe('shouldLoadCommits', () => {
  it('returns true when the previous key is null', () => {
    expect(shouldLoadCommits(null, 'myrepo:main')).toBe(true)
  })

  it('returns false when the keys are identical', () => {
    expect(shouldLoadCommits('myrepo:main', 'myrepo:main')).toBe(false)
  })

  it('returns true when the keys differ', () => {
    expect(shouldLoadCommits('myrepo:main', 'myrepo:dev')).toBe(true)
  })
})

describe('buildCommitBrowseTarget', () => {
  it('includes the branch when present', () => {
    expect(buildCommitBrowseTarget('myrepo', 'main', 'abc123')).toBe(
      '/browse/myrepo?branch=main&commit=abc123&co=1'
    )
  })

  it('omits the branch when absent', () => {
    expect(buildCommitBrowseTarget('myrepo', null, 'abc123')).toBe(
      '/browse/myrepo?commit=abc123&co=1'
    )
  })

  it('always sets co=1 and the correct commit hash', () => {
    const target = buildCommitBrowseTarget('repo', undefined, 'deadbeef')
    expect(target).toContain('commit=deadbeef')
    expect(target).toContain('co=1')
  })
})
