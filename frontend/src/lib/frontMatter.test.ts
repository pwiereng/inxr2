import { describe, it, expect } from 'vitest'
import { splitFrontMatter } from './frontMatter'

describe('splitFrontMatter', () => {
  it('returns content unchanged when there is no front matter', () => {
    const content = '# Title\n\nSome text\n'
    expect(splitFrontMatter(content)).toEqual({ frontMatter: null, body: content })
  })

  it('extracts a leading front-matter block and returns the remaining body (#553)', () => {
    const content =
      '---\nname: close\ndescription: "Closes a worktree"\nuser-invocable: true\n---\n# Close Skill\n'
    const result = splitFrontMatter(content)

    expect(result.body).toBe('# Close Skill\n')
    expect(result.frontMatter?.entries).toEqual([
      { key: 'name', value: 'close' },
      { key: 'description', value: 'Closes a worktree' },
      { key: 'user-invocable', value: 'true' },
    ])
  })

  it('leaves a later --- alone (horizontal rule / setext heading)', () => {
    const content = '# Title\n\n---\n\nHeading\n---\n'
    expect(splitFrontMatter(content)).toEqual({ frontMatter: null, body: content })
  })

  it('does not treat a --- that is not on the first line as front matter', () => {
    const content = '\n---\nname: x\n---\n'
    expect(splitFrontMatter(content)).toEqual({ frontMatter: null, body: content })
  })

  it('ignores an unterminated front-matter block', () => {
    const content = '---\nname: close\n# Heading\n'
    expect(splitFrontMatter(content)).toEqual({ frontMatter: null, body: content })
  })

  it('extracts an empty front-matter block with no entries', () => {
    const result = splitFrontMatter('---\n---\n# Title\n')
    expect(result.body).toBe('# Title\n')
    expect(result.frontMatter).toEqual({ raw: '', entries: [] })
  })

  it('handles CRLF line endings', () => {
    const result = splitFrontMatter(
      '---\r\nname: close\r\ntitle: Close\r\n---\r\n# Close Skill\r\n'
    )
    expect(result.body).toBe('# Close Skill\r\n')
    expect(result.frontMatter?.entries).toEqual([
      { key: 'name', value: 'close' },
      { key: 'title', value: 'Close' },
    ])
  })

  it('handles a leading byte-order mark', () => {
    const result = splitFrontMatter('\uFEFF---\nname: close\n---\nBody')
    expect(result.body).toBe('Body')
    expect(result.frontMatter?.entries).toEqual([{ key: 'name', value: 'close' }])
  })

  it('accepts "..." as the closing delimiter', () => {
    const result = splitFrontMatter('---\nname: close\n...\nBody')
    expect(result.body).toBe('Body')
    expect(result.frontMatter?.entries).toEqual([{ key: 'name', value: 'close' }])
  })

  it('handles front matter that ends the file with no trailing newline', () => {
    const result = splitFrontMatter('---\nname: close\n---')
    expect(result.body).toBe('')
    expect(result.frontMatter?.entries).toEqual([{ key: 'name', value: 'close' }])
  })

  it('folds indented and list continuation lines into the preceding value', () => {
    const result = splitFrontMatter('---\ntags:\n  - a\n  - b\nname: x\n---\n')
    expect(result.frontMatter?.entries).toEqual([
      { key: 'tags', value: '- a\n- b' },
      { key: 'name', value: 'x' },
    ])
  })

  it('skips blank lines and comments inside the block', () => {
    const result = splitFrontMatter('---\n# comment\n\nname: x\n---\n')
    expect(result.frontMatter?.entries).toEqual([{ key: 'name', value: 'x' }])
  })

  it('returns null entries (raw only) when the block is not a simple key/value mapping', () => {
    const result = splitFrontMatter('---\njust some text\n---\nBody')
    expect(result.body).toBe('Body')
    expect(result.frontMatter).toEqual({ raw: 'just some text', entries: null })
  })
})
