import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('AntD deprecations (BatchGeneHeatmap docs)', () => {
  it('does not use deprecated Alert.message in README snippets', () => {
    const sourcePath = join(process.cwd(), 'src/components/BatchGeneHeatmap/README.md')
    const source = readFileSync(sourcePath, 'utf-8')
    expect(source).not.toMatch(/<Alert[^>]*\bmessage\s*=/)
  })
})

