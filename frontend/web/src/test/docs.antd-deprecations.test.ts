import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('AntD deprecations (docs)', () => {
  it('does not use deprecated Alert.message in docs snippets', () => {
    const sourcePath = join(
      process.cwd(),
      '..',
      '..',
      'docs',
      'api',
      'SANKEY_FRONTEND_INTEGRATION_GUIDE.md',
    )
    const source = readFileSync(sourcePath, 'utf-8')
    expect(source).not.toMatch(/<Alert[^>]*\bmessage\s*=/)
  })
})

