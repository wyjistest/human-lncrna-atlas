import { describe, expect, it } from 'vitest'

import { normalizeApiBaseUrl, validateApiBaseUrl } from '@/config/api'

describe('API base URL helpers', () => {
  it('normalizes trailing slashes', () => {
    expect(normalizeApiBaseUrl('https://example.com///')).toBe('https://example.com')
  })

  it('accepts origin-only URLs', () => {
    expect(validateApiBaseUrl('https://example.com')).toBe('https://example.com')
  })

  it('rejects /api suffixes to avoid double prefixes', () => {
    expect(() => validateApiBaseUrl('https://example.com/api')).toThrow(/already include \/api\/v1/i)
  })
})
