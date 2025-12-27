import { describe, expect, it } from 'vitest'

import { queryKeys } from '@/hooks/queryKeys'

describe('hooks/queryKeys', () => {
  it('treats undefined params and empty params object as the same key', () => {
    const keyA = queryKeys.genes.regulations(123)
    const keyB = queryKeys.genes.regulations(123, {})
    expect(keyA).toEqual(keyB)
  })

  it('is order-insensitive for array params (and does not mutate the input)', () => {
    const params = {
      species_ids: [3, 1, 2],
      chromosomes: ['chr2', 'chr1'],
    }

    const key = queryKeys.regulations.list(params)
    const normalizedParams = key[2] as { species_ids?: number[]; chromosomes?: string[] }

    expect(params).toEqual({
      species_ids: [3, 1, 2],
      chromosomes: ['chr2', 'chr1'],
    })
    expect(normalizedParams).toEqual({
      species_ids: [1, 2, 3],
      chromosomes: ['chr1', 'chr2'],
    })
  })

  it('is order-insensitive for analysis mark_names array', () => {
    const keyA = queryKeys.analysis.epigenetic({ mark_names: ['H3K4me3', 'H3K27me3'] })
    const keyB = queryKeys.analysis.epigenetic({ mark_names: ['H3K27me3', 'H3K4me3'] })
    expect(keyA).toEqual(keyB)
  })
})

