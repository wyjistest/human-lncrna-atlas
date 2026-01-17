/**
 * RepeatMasker color constants and configuration
 * UCSC Genome Browser compatible color scheme for repeat elements
 */

/**
 * Repeat class color mapping (UCSC compatible)
 */
export const REPEAT_CLASS_COLORS: Record<string, string> = {
  SINE: '#FF0000',
  LINE: '#0000CC',
  LTR: '#00CC00',
  DNA: '#CC00CC',
  Simple_repeat: '#000000',
  Low_complexity: '#666666',
  Satellite: '#CC6600',
  Other: '#888888',
}

/**
 * Ordered list of repeat classes for display
 */
export const REPEAT_CLASS_ORDER = [
  'SINE',
  'LINE',
  'LTR',
  'DNA',
  'Simple_repeat',
  'Low_complexity',
  'Satellite',
  'Other',
] as const

export type RepeatClass = typeof REPEAT_CLASS_ORDER[number]
