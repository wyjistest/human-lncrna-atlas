/**
 * HTML Escape Utility
 *
 * Provides secure HTML escaping to prevent XSS attacks when rendering
 * user-supplied or API-sourced data in HTML contexts (e.g., ECharts tooltips).
 *
 * Phase 9.10: Security hardening for XSS prevention in chart tooltips.
 *
 * @see https://owasp.org/www-community/xss-filter-evasion-cheatsheet
 */

/**
 * HTML entity map for escaping special characters.
 * These are the 5 characters that have special meaning in HTML.
 */
const HTML_ENTITIES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#x27;',
}

/**
 * Regex pattern matching any HTML special character that needs escaping.
 */
const HTML_ESCAPE_REGEX = /[&<>"']/g

/**
 * Escape HTML special characters to prevent XSS attacks.
 *
 * This function converts the 5 HTML special characters to their entity equivalents:
 * - & -> &amp;
 * - < -> &lt;
 * - > -> &gt;
 * - " -> &quot;
 * - ' -> &#x27;
 *
 * Use this function when interpolating untrusted data (API responses, user input)
 * into HTML strings, such as ECharts tooltip formatters.
 *
 * @param str - The string to escape (handles null/undefined gracefully)
 * @returns The escaped string safe for HTML insertion
 *
 * @example
 * ```typescript
 * // In ECharts tooltip formatter:
 * formatter: (params) => {
 *   return `<strong>${escapeHtml(params.name)}</strong>: ${escapeHtml(params.value)}`
 * }
 *
 * // Handles malicious input:
 * escapeHtml('<script>alert("xss")</script>')
 * // Returns: '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
 *
 * // Handles null/undefined:
 * escapeHtml(null)      // Returns: ''
 * escapeHtml(undefined) // Returns: ''
 * ```
 */
export function escapeHtml(str: string | null | undefined): string {
  if (str == null) {
    return ''
  }

  // Convert to string in case a non-string is passed
  const stringValue = String(str)

  return stringValue.replace(HTML_ESCAPE_REGEX, (char) => HTML_ENTITIES[char])
}

/**
 * Escape multiple values at once, useful for tooltip formatters with many fields.
 *
 * @param values - Object with string values to escape
 * @returns Object with the same keys but escaped values
 *
 * @example
 * ```typescript
 * const safe = escapeHtmlValues({ name: '<script>', value: '100' })
 * // Returns: { name: '&lt;script&gt;', value: '100' }
 * ```
 */
export function escapeHtmlValues<T extends Record<string, string | null | undefined>>(
  values: T
): Record<keyof T, string> {
  const result = {} as Record<keyof T, string>
  for (const key in values) {
    if (Object.prototype.hasOwnProperty.call(values, key)) {
      result[key] = escapeHtml(values[key])
    }
  }
  return result
}
