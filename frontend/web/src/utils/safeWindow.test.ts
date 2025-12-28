import { describe, expect, it, vi } from 'vitest'

import { openInNewTab } from './safeWindow'

describe('safeWindow.openInNewTab', () => {
  it('blocks javascript: URLs and does not call window.open', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const result = openInNewTab('javascript:alert(1)')

    expect(result.blocked).toBe(true)
    expect(result.reason).toBe('invalid_url')
    expect(openSpy).not.toHaveBeenCalled()

    warnSpy.mockRestore()
    openSpy.mockRestore()
  })

  it('redacts query strings/fragments in console warning (defense-in-depth)', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    openInNewTab('javascript:alert(1)?token=secret#frag')

    expect(openSpy).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalled()
    const warnText = warnSpy.mock.calls.flat().join(' ')
    expect(warnText).not.toContain('token=secret')
    expect(warnText).not.toContain('#frag')

    warnSpy.mockRestore()
    openSpy.mockRestore()
  })

  it('opens https URL and nulls out opener', () => {
    const fakeWindow = { closed: false, opener: {} } as unknown as Window
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow)

    const result = openInNewTab('https://example.com/file.csv?token=secret')

    expect(openSpy).toHaveBeenCalledWith(
      'https://example.com/file.csv?token=secret',
      '_blank',
      'noopener,noreferrer'
    )
    expect(fakeWindow.opener).toBe(null)
    expect(result.blocked).toBe(false)
    expect(result.reason).toBeUndefined()

    openSpy.mockRestore()
  })
})

