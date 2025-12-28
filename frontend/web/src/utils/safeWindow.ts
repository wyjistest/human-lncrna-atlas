/**
 * Safe Window Utilities
 *
 * Provides secure window opening functions to prevent tabnabbing attacks.
 * Phase 9.8: Security hardening for window.open calls.
 *
 * @see https://owasp.org/www-community/attacks/Reverse_Tabnabbing
 */

/**
 * Result of opening a new window
 */
export type SafeWindowBlockReason = 'popup_blocked' | 'invalid_url' | 'no_window'

export interface SafeWindowResult {
  /** The opened window reference, or null if blocked */
  window: Window | null
  /** Whether the popup was blocked by the browser */
  blocked: boolean
  /** Optional reason when blocked=true (best-effort) */
  reason?: SafeWindowBlockReason
}

const MAX_URL_LENGTH = 8192
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'blob:'])

function isSafeUrlToOpen(rawUrl: string): boolean {
  const url = rawUrl.trim()
  if (!url) return false
  if (url.length > MAX_URL_LENGTH) return false
  if (/[\r\n\0]/.test(url)) return false
  if (typeof window === 'undefined') return false
  try {
    const resolved = new URL(url, window.location.href)
    return ALLOWED_PROTOCOLS.has(resolved.protocol)
  } catch {
    return false
  }
}

function redactUrlForLog(rawUrl: string): string {
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''

  // Avoid log injection / multi-line logs
  const singleLine = trimmed.replace(/[\r\n\0]/g, '')
  // Drop query string / fragment to avoid leaking tokens (defense-in-depth)
  const withoutQuery = singleLine.split(/[?#]/, 1)[0]

  const truncated =
    withoutQuery.length > 512 ? `${withoutQuery.slice(0, 512)}...[TRUNC]` : withoutQuery

  if (typeof window === 'undefined') return truncated

  try {
    const resolved = new URL(truncated, window.location.href)
    const protocol = resolved.protocol
    const host = resolved.host
    const pathname = resolved.pathname
    return host ? `${protocol}//${host}${pathname}` : `${protocol}${pathname}`
  } catch {
    return truncated
  }
}

/**
 * Safely open a URL in a new tab/window with tabnabbing protection.
 *
 * This function adds 'noopener,noreferrer' to prevent the opened page
 * from accessing window.opener and potentially redirecting the original page.
 *
 * @param url - The URL to open
 * @returns SafeWindowResult with window reference and blocked status
 *
 * @example
 * ```typescript
 * const result = openInNewTab('https://example.com/file.csv')
 * if (result.blocked) {
 *   message.warning('Please allow popups to download')
 * }
 * ```
 */
export const openInNewTab = (url: string): SafeWindowResult => {
  if (typeof window === 'undefined') {
    return { window: null, blocked: true, reason: 'no_window' }
  }

  if (!isSafeUrlToOpen(url)) {
    console.warn('[safeWindow] Blocked opening unsafe URL:', redactUrlForLog(url))
    return { window: null, blocked: true, reason: 'invalid_url' }
  }

  // Open with noopener,noreferrer to prevent tabnabbing
  const newWindow = window.open(url, '_blank', 'noopener,noreferrer')

  // Additional safety: explicitly null out opener for older browsers
  if (newWindow) {
    newWindow.opener = null
  }

  // Check if popup was blocked
  const blocked = !newWindow || newWindow.closed || typeof newWindow.closed === 'undefined'

  return {
    window: newWindow,
    blocked,
    reason: blocked ? 'popup_blocked' : undefined,
  }
}

/**
 * Open a download URL in a new tab with tabnabbing protection.
 *
 * This is a convenience wrapper for file downloads that uses
 * the same security measures as openInNewTab.
 *
 * @param url - The download URL to open
 * @returns SafeWindowResult with window reference and blocked status
 */
export const openDownloadUrl = (url: string): SafeWindowResult => {
  return openInNewTab(url)
}
