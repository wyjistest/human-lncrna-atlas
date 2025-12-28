import { describe, expect, it } from 'vitest'

import { escapeCSV } from './csv'

describe('escapeCSV', () => {
  it('prevents formula injection for direct formula prefix', () => {
    expect(escapeCSV('=1+1')).toBe("'=1+1")
    // Contains comma => must be quoted for valid CSV.
    expect(escapeCSV('+SUM(1,2)')).toBe("\"'+SUM(1,2)\"")
    expect(escapeCSV('-1+2')).toBe("'-1+2")
    expect(escapeCSV('@cmd')).toBe("'@cmd")
  })

  it('prevents formula injection with leading whitespace/BOM bypass', () => {
    expect(escapeCSV('   =1+1')).toBe("'   =1+1")
    expect(escapeCSV('\t=1+1')).toBe("'\t=1+1")
    expect(escapeCSV('\ufeff=1+1')).toBe("'\ufeff=1+1")
    expect(escapeCSV('\ufeff   =1+1')).toBe("'\ufeff   =1+1")
  })

  it('quotes fields containing commas/quotes/newlines', () => {
    expect(escapeCSV('a,b')).toBe('"a,b"')
    expect(escapeCSV('a"b')).toBe('"a""b"')
    expect(escapeCSV('a\nb')).toBe('"a\nb"')
  })
})
