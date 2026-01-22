import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('AntD deprecations (Overlap visualizations)', () => {
  it('does not use deprecated Card.bordered prop', () => {
    const sourcePath = join(process.cwd(), 'src/components/LncRNAChIPSeqOverlapTable/index.tsx')
    const source = readFileSync(sourcePath, 'utf-8')
    expect(source).not.toMatch(/<Card[^>]*\bbordered\s*=/)
  })
})
