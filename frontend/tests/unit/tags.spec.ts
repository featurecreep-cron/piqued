import { describe, expect, it } from 'vitest'
import { humanizeTag } from '@/utils/tags'

describe('humanizeTag', () => {
  it('converts single snake_case word to Title Case', () => {
    expect(humanizeTag('finance')).toBe('Finance')
  })

  it('converts multi-word snake_case to Title Case', () => {
    expect(humanizeTag('securities_fraud_humor')).toBe('Securities Fraud Humor')
  })

  it('handles empty string', () => {
    expect(humanizeTag('')).toBe('')
  })

  it('handles single character', () => {
    expect(humanizeTag('a')).toBe('A')
  })

  it('handles consecutive underscores without crashing', () => {
    expect(humanizeTag('foo__bar')).toBe('Foo  Bar')
  })

  it('handles trailing/leading underscores', () => {
    expect(humanizeTag('_foo_')).toBe(' Foo ')
  })

  it('does not lowercase already-uppercase letters mid-word', () => {
    // Tags from the LLM are conventionally lowercase snake_case, but
    // mixed-case input shouldn't be destroyed.
    expect(humanizeTag('iOS_apps')).toBe('IOS Apps')
  })
})
