import { describe, expect, it } from 'vitest'

import { chipseqQueryKeys } from '@/api/chipseq'
import { globalCompareQueryKeys } from '@/api/globalCompare'

describe('chipseqQueryKeys', () => {
  it('includes flanking in compare keys and does not mutate marks', () => {
    const marks = ['H3K4me3', 'H3K27me3'] as const

    const keyA = chipseqQueryKeys.compare(123, [...marks], 10000)
    const keyB = chipseqQueryKeys.compare(123, [...marks], 20000)

    expect(keyA).not.toEqual(keyB)
    expect(marks).toEqual(['H3K4me3', 'H3K27me3'])
  })

  it('includes flanking in compareCellLines keys and does not mutate cellTypes', () => {
    const cellTypes = ['K562', 'GM12878'] as const

    const key = chipseqQueryKeys.compareCellLines(123, 'H3K27me3', [...cellTypes], 5000)

    expect(key).toEqual(['chipseq', 'gene', 123, 'compare-cell-lines', 'H3K27me3', 'GM12878,K562', 5000])
    expect(cellTypes).toEqual(['K562', 'GM12878'])
  })

  it('includes flanking in heatmapMatrix keys and is order-insensitive for marks/cellTypes', () => {
    const marksA = ['H3K4me3', 'H3K27me3'] as const
    const marksB = ['H3K27me3', 'H3K4me3'] as const
    const cellTypesA = ['K562', 'GM12878'] as const
    const cellTypesB = ['GM12878', 'K562'] as const

    const keyA = chipseqQueryKeys.heatmapMatrix(123, [...marksA], [...cellTypesA], 'median_fold_enrichment', 10000)
    const keyB = chipseqQueryKeys.heatmapMatrix(123, [...marksB], [...cellTypesB], 'median_fold_enrichment', 10000)

    expect(keyA).toEqual(keyB)
    expect(marksA).toEqual(['H3K4me3', 'H3K27me3'])
    expect(cellTypesA).toEqual(['K562', 'GM12878'])
  })
})

describe('globalCompareQueryKeys', () => {
  it('does not mutate marks/cellTypes and includes extra params in key', () => {
    const marks = ['H3K4me3', 'H3K27me3'] as const
    const cellTypes = ['K562', 'GM12878'] as const

    const keyA = globalCompareQueryKeys.compare([...marks], [...cellTypes], {
      min_peaks: 10,
      include_position_distribution: true,
    })
    const keyB = globalCompareQueryKeys.compare([...marks], [...cellTypes], {
      min_peaks: 20,
      include_position_distribution: true,
    })

    expect(keyA).not.toEqual(keyB)
    expect(marks).toEqual(['H3K4me3', 'H3K27me3'])
    expect(cellTypes).toEqual(['K562', 'GM12878'])
  })

  it('includes bins in signalDistribution keys', () => {
    const key = globalCompareQueryKeys.signalDistribution(['H3K27me3'], ['K562'], 50)
    expect(key).toEqual(['globalCompare', 'distribution', 'H3K27me3', 'K562', 50])
  })
})

