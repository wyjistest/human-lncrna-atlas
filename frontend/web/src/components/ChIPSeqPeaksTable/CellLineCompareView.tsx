/**
 * CellLineCompareView Component
 * Phase 2.6 - Container component for cell line comparison feature
 *
 * Combines CellLineComparePanel and CellLineHeatmap into a cohesive view
 * that allows users to compare the same histone mark across different cell lines.
 */

import { useState, useCallback } from 'react'
import { Space, Alert, Empty } from 'antd'
import { useTranslation } from 'react-i18next'

import { CellLineComparePanel } from './CellLineComparePanel'
import { CellLineHeatmap } from './CellLineHeatmap'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { useChIPSeqCellLineCompare } from '@/hooks/useChIPSeq'
import type { MarkType } from '@/types/chipseq'

type MetricType = 'signal' | 'fold_enrichment' | 'peak_count' | 'coverage'

interface CellLineCompareViewProps {
  /** Gene ID */
  geneId: number
  /** Current mark type to compare */
  currentMarkType: MarkType
  /** Flanking region in bp */
  flanking?: number
  /** Callback when comparison is closed */
  onClose?: () => void
}

/**
 * CellLineCompareView Component
 *
 * Provides the complete cell line comparison experience:
 * 1. Selection panel for choosing cell lines
 * 2. Data fetching via React Query
 * 3. Visualization with heatmap and charts
 *
 * @example
 * ```tsx
 * <CellLineCompareView
 *   geneId={123}
 *   currentMarkType="H3K27me3"
 *   onClose={() => setShowCompare(false)}
 * />
 * ```
 */
export function CellLineCompareView({
  geneId,
  currentMarkType,
  flanking = 10000,
  onClose: _onClose, // Keep for future use
}: CellLineCompareViewProps) {
  const { t } = useTranslation('genes')

  // State for selected cell types
  const [selectedCellTypes, setSelectedCellTypes] = useState<string[]>([])
  const [comparisonStarted, setComparisonStarted] = useState(false)
  const [metric, setMetric] = useState<MetricType>('fold_enrichment')

  // Data fetching hook
  const {
    data: compareData,
    isLoading,
    isError,
    error,
    refetch,
  } = useChIPSeqCellLineCompare(
    geneId,
    currentMarkType,
    selectedCellTypes,
    flanking,
    { enabled: comparisonStarted && selectedCellTypes.length >= 2 }
  )

  // Handle compare button click
  const handleCompare = useCallback((cellTypes: string[]) => {
    setSelectedCellTypes(cellTypes)
    setComparisonStarted(true)
  }, [])

  // Handle metric change
  const handleMetricChange = useCallback((newMetric: MetricType) => {
    setMetric(newMetric)
  }, [])

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* Selection Panel - always visible */}
      <CellLineComparePanel
        geneId={geneId}
        currentMarkType={currentMarkType}
        onCompare={handleCompare}
        initialSelectedCellTypes={selectedCellTypes}
        loading={isLoading}
      />

      {/* Comparison Results */}
      {comparisonStarted && (
        <>
          {isLoading && <LoadingState />}

          {isError && (
            <ErrorState
              error={error}
              onRetry={() => refetch()}
            />
          )}

          {!isLoading && !isError && compareData && (
            <CellLineHeatmap
              data={compareData}
              metric={metric}
              onMetricChange={handleMetricChange}
              loading={isLoading}
            />
          )}

          {!isLoading && !isError && !compareData && (
            <Empty
              description={t(
                'detail.chipseq.cellLineCompare.noResults',
                'No comparison data available for the selected cell lines'
              )}
            />
          )}
        </>
      )}

      {/* Initial State - before comparison started */}
      {!comparisonStarted && (
        <Alert
          message={t('detail.chipseq.cellLineCompare.getStarted', 'Get Started')}
          description={t(
            'detail.chipseq.cellLineCompare.getStartedDescription',
            'Select 2 or more cell lines from the panel above and click Compare to see how the same histone mark behaves across different cell types.'
          )}
          type="info"
          showIcon
        />
      )}
    </Space>
  )
}

export default CellLineCompareView
