import { describe, expect, it } from 'vitest'

import { overlapQueryKeys } from '@/api/lncRNAChIPSeqOverlapApi'

describe('overlapQueryKeys', () => {
  it('normalizes comma-separated mark_type/cell_type and default sort params', () => {
    const keyA = overlapQueryKeys.overlaps({
      mark_type: 'H3K27me3,H3K4me3',
      cell_type: 'K562,GM12878',
      page: 1,
      page_size: 20,
    })
    const keyB = overlapQueryKeys.overlaps({
      mark_type: 'H3K4me3,H3K27me3',
      cell_type: 'GM12878,K562',
      page: 1,
      page_size: 20,
      sort_by: 'binding_affinity',
      sort_order: 'desc',
      max_qvalue: 0.05,
    })

    expect(keyA).toEqual(keyB)
  })

  it('does not include pagination/sort-only fields in summary keys', () => {
    const keyA = overlapQueryKeys.summary({
      mark_type: 'H3K27me3,H3K4me3',
      page: 1,
      page_size: 20,
      sort_by: 'overlap_length',
      sort_order: 'asc',
    })
    const keyB = overlapQueryKeys.summary({
      mark_type: 'H3K4me3,H3K27me3',
      page: 99,
      page_size: 1000,
    })

    expect(keyA).toEqual(keyB)
  })
})

