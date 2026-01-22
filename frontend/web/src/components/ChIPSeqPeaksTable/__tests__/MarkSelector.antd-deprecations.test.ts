import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('AntD deprecations (MarkSelector)', () => {
  it('does not use deprecated dropdownMatchSelectWidth prop', () => {
    const sourcePath = join(process.cwd(), 'src/components/ChIPSeqPeaksTable/MarkSelector.tsx')
    const source = readFileSync(sourcePath, 'utf-8')
    expect(source).not.toMatch(/\bdropdownMatchSelectWidth\b/)
  })
})
