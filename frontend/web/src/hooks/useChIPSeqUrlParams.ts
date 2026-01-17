/**
 * useChIPSeqUrlParams Hook
 * Phase 2.5 - URL parameter synchronization for ChIP-seq comparison view
 *
 * Enables sharing URLs with specific marks and filters preserved.
 * Uses React Router's useSearchParams for URL state management.
 *
 * @example
 * ```tsx
 * // URL: /genes/123?marks=H3K27me3,H3K4me3&flanking=20000&viewMode=stats
 * const {
 *   selectedMarks,
 *   setSelectedMarks,
 *   filters,
 *   setFilters,
 *   viewMode,
 *   setViewMode,
 * } = useChIPSeqUrlParams()
 * ```
 */

import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { MarkType, ChIPSeqFilters, CompareViewMode } from '@/types/chipseq'

// Valid mark types for validation
const VALID_MARKS: MarkType[] = [
  'H3K27me3', 'H3K9me3', 'H3K9me2', 'H3K4me3', 'H3K4me2',
  'H3K4me1', 'H3K27ac', 'H3K9ac', 'H3K36me3', 'H3K79me2',
  'H2AZ', 'H2BK120ub', 'H4K20me1', 'H3K4ac', 'H3K14ac',
  'H3K18ac', 'DNase-HS',
]

// Valid view modes
const VALID_VIEW_MODES: CompareViewMode[] = ['merged', 'parallel', 'stats']

// URL parameter keys
const PARAM_KEYS = {
  MARKS: 'marks',
  VIEW_MODE: 'viewMode',
  FLANKING: 'flanking',
  COMPARE_MODE: 'compare',
  MIN_FOLD: 'minFold',
  MAX_FOLD: 'maxFold',
  MAX_QVALUE: 'maxQ',
  POSITION: 'position',
  CELL_TYPE: 'cellType',
} as const

interface UseChIPSeqUrlParamsOptions {
  /** Default marks to use if none in URL */
  defaultMarks?: MarkType[]
  /** Default view mode */
  defaultViewMode?: CompareViewMode
  /** Default flanking region */
  defaultFlanking?: number
  /** Whether to enable URL sync (default: true) */
  enabled?: boolean
}

interface UseChIPSeqUrlParamsReturn {
  /** Currently selected marks from URL */
  selectedMarks: MarkType[]
  /** Update selected marks in URL */
  setSelectedMarks: (marks: MarkType[]) => void
  /** Current view mode from URL */
  viewMode: CompareViewMode
  /** Update view mode in URL */
  setViewMode: (mode: CompareViewMode) => void
  /** Whether compare mode is active from URL */
  compareMode: boolean
  /** Update compare mode in URL */
  setCompareMode: (enabled: boolean) => void
  /** Filter values from URL */
  filters: Partial<ChIPSeqFilters>
  /** Update filters in URL */
  setFilters: (filters: Partial<ChIPSeqFilters>) => void
  /** Clear all URL parameters */
  clearParams: () => void
  /** Get shareable URL with current state */
  getShareableUrl: () => string
}

/**
 * Hook for synchronizing ChIP-seq view state with URL parameters
 */
export function useChIPSeqUrlParams(
  options: UseChIPSeqUrlParamsOptions = {}
): UseChIPSeqUrlParamsReturn {
  const {
    defaultMarks = [],
    defaultViewMode = 'merged',
    defaultFlanking = 10000,
    enabled = true,
  } = options

  const [searchParams, setSearchParams] = useSearchParams()

  // Parse marks from URL
  const selectedMarks = useMemo<MarkType[]>(() => {
    if (!enabled) return defaultMarks

    const marksParam = searchParams.get(PARAM_KEYS.MARKS)
    if (!marksParam) return defaultMarks

    const parsedMarks = marksParam
      .split(',')
      .map((m) => m.trim())
      .filter((m): m is MarkType => VALID_MARKS.includes(m as MarkType))

    return parsedMarks.length > 0 ? parsedMarks : defaultMarks
  }, [searchParams, defaultMarks, enabled])

  // Parse view mode from URL
  const viewMode = useMemo<CompareViewMode>(() => {
    if (!enabled) return defaultViewMode

    const modeParam = searchParams.get(PARAM_KEYS.VIEW_MODE)
    if (modeParam && VALID_VIEW_MODES.includes(modeParam as CompareViewMode)) {
      return modeParam as CompareViewMode
    }
    return defaultViewMode
  }, [searchParams, defaultViewMode, enabled])

  // Parse compare mode from URL
  const compareMode = useMemo<boolean>(() => {
    if (!enabled) return false
    return searchParams.get(PARAM_KEYS.COMPARE_MODE) === 'true'
  }, [searchParams, enabled])

  // Parse filter values from URL
  const filters = useMemo<Partial<ChIPSeqFilters>>(() => {
    if (!enabled) return { flanking: defaultFlanking }

    const result: Partial<ChIPSeqFilters> = {}

    // Flanking
    const flankingParam = searchParams.get(PARAM_KEYS.FLANKING)
    if (flankingParam) {
      const flanking = parseInt(flankingParam, 10)
      if (!isNaN(flanking) && flanking > 0 && flanking <= 100000) {
        result.flanking = flanking
      }
    } else {
      result.flanking = defaultFlanking
    }

    // Min fold enrichment
    const minFoldParam = searchParams.get(PARAM_KEYS.MIN_FOLD)
    if (minFoldParam) {
      const minFold = parseFloat(minFoldParam)
      if (!isNaN(minFold) && minFold >= 0) {
        result.min_fold_enrichment = minFold
      }
    }

    // Max fold enrichment
    const maxFoldParam = searchParams.get(PARAM_KEYS.MAX_FOLD)
    if (maxFoldParam) {
      const maxFold = parseFloat(maxFoldParam)
      if (!isNaN(maxFold) && maxFold > 0) {
        result.max_fold_enrichment = maxFold
      }
    }

    // Max q-value
    const maxQParam = searchParams.get(PARAM_KEYS.MAX_QVALUE)
    if (maxQParam) {
      const maxQ = parseFloat(maxQParam)
      if (!isNaN(maxQ) && maxQ >= 0 && maxQ <= 1) {
        result.max_qvalue = maxQ
      }
    }

    // Relative position
    const positionParam = searchParams.get(PARAM_KEYS.POSITION)
    if (positionParam) {
      result.relative_position = positionParam
    }

    // Cell type
    const cellTypeParam = searchParams.get(PARAM_KEYS.CELL_TYPE)
    if (cellTypeParam) {
      result.cell_type = cellTypeParam
    }

    return result
  }, [searchParams, defaultFlanking, enabled])

  // Update marks in URL
  const setSelectedMarks = useCallback(
    (marks: MarkType[]) => {
      if (!enabled) return

      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev)
        if (marks.length > 0) {
          newParams.set(PARAM_KEYS.MARKS, marks.join(','))
        } else {
          newParams.delete(PARAM_KEYS.MARKS)
        }
        return newParams
      }, { replace: true })
    },
    [setSearchParams, enabled]
  )

  // Update view mode in URL
  const setViewMode = useCallback(
    (mode: CompareViewMode) => {
      if (!enabled) return

      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev)
        if (mode !== defaultViewMode) {
          newParams.set(PARAM_KEYS.VIEW_MODE, mode)
        } else {
          newParams.delete(PARAM_KEYS.VIEW_MODE)
        }
        return newParams
      }, { replace: true })
    },
    [setSearchParams, defaultViewMode, enabled]
  )

  // Update compare mode in URL
  const setCompareMode = useCallback(
    (enabled_: boolean) => {
      if (!enabled) return

      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev)
        if (enabled_) {
          newParams.set(PARAM_KEYS.COMPARE_MODE, 'true')
        } else {
          newParams.delete(PARAM_KEYS.COMPARE_MODE)
        }
        return newParams
      }, { replace: true })
    },
    [setSearchParams, enabled]
  )

  // Update filters in URL
  const setFilters = useCallback(
    (newFilters: Partial<ChIPSeqFilters>) => {
      if (!enabled) return

      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev)

        // Flanking
        if (newFilters.flanking !== undefined && newFilters.flanking !== defaultFlanking) {
          newParams.set(PARAM_KEYS.FLANKING, String(newFilters.flanking))
        } else if (newFilters.flanking === defaultFlanking) {
          newParams.delete(PARAM_KEYS.FLANKING)
        }

        // Min fold enrichment
        if (newFilters.min_fold_enrichment !== undefined && newFilters.min_fold_enrichment > 0) {
          newParams.set(PARAM_KEYS.MIN_FOLD, String(newFilters.min_fold_enrichment))
        } else {
          newParams.delete(PARAM_KEYS.MIN_FOLD)
        }

        // Max fold enrichment
        if (newFilters.max_fold_enrichment !== undefined && newFilters.max_fold_enrichment < 100) {
          newParams.set(PARAM_KEYS.MAX_FOLD, String(newFilters.max_fold_enrichment))
        } else {
          newParams.delete(PARAM_KEYS.MAX_FOLD)
        }

        // Max q-value
        if (newFilters.max_qvalue !== undefined) {
          newParams.set(PARAM_KEYS.MAX_QVALUE, String(newFilters.max_qvalue))
        } else {
          newParams.delete(PARAM_KEYS.MAX_QVALUE)
        }

        // Relative position
        if (newFilters.relative_position) {
          newParams.set(PARAM_KEYS.POSITION, newFilters.relative_position)
        } else {
          newParams.delete(PARAM_KEYS.POSITION)
        }

        // Cell type
        if (newFilters.cell_type) {
          newParams.set(PARAM_KEYS.CELL_TYPE, newFilters.cell_type)
        } else {
          newParams.delete(PARAM_KEYS.CELL_TYPE)
        }

        return newParams
      }, { replace: true })
    },
    [setSearchParams, defaultFlanking, enabled]
  )

  // Clear all ChIP-seq related URL parameters
  const clearParams = useCallback(() => {
    if (!enabled) return

    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev)
      Object.values(PARAM_KEYS).forEach((key) => {
        newParams.delete(key)
      })
      return newParams
    }, { replace: true })
  }, [setSearchParams, enabled])

  // Get shareable URL with current state
  const getShareableUrl = useCallback(() => {
    return window.location.href
  }, [])

  return {
    selectedMarks,
    setSelectedMarks,
    viewMode,
    setViewMode,
    compareMode,
    setCompareMode,
    filters,
    setFilters,
    clearParams,
    getShareableUrl,
  }
}

export default useChIPSeqUrlParams
