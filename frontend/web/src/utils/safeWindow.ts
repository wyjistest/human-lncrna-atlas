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
export interface SafeWindowResult {
  /** The opened window reference, or null if blocked */
  window: Window | null
  /** Whether the popup was blocked by the browser */
  blocked: boolean
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
