/**
 * CSV escaping utilities (security-focused).
 *
 * Prevents:
 * - CSV injection / formula injection (Excel/Sheets interpreting cell as formula)
 * - Broken CSV formatting due to quotes/newlines/commas
 */
export function escapeCSV(val: unknown): string {
  let str = String(val ?? '')

  // Prevent CSV formula injection: Excel/Sheets interprets these as formulas
  if (/^[=+\-@\t\r]/.test(str)) {
    str = "'" + str
  }

  // Quote fields that contain special characters
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }

  return str
}

