/**
 * ChIPSeqPeaksTable Main Component
 * Phase 2.2 - Universal ChIP-seq peaks viewer
 *
 * Features:
 * - Support for 15+ histone modification marks
 * - Mark type selector with grouping
 * - Statistics cards with key metrics
 * - Advanced filtering panel
 * - Sortable, paginated data table
 * - Multi-mark comparison mode with charts
 * - Export functionality (BED, CSV)
 *
 * View Modes:
 * - Single mark: Standard table view with one mark
 * - Merged: Combined table with multiple marks
 * - Parallel: Side-by-side comparison (2 marks)
 * - Stats: Statistical comparison charts
 */

import { useState, useMemo, useCallback } from 'react'
import {
  Space,
  Card,
  Tabs,
  Button,
  message,
  Empty,
  Alert,
  Row,
  Col,
  Divider,
} from 'antd'
import {
  DownloadOutlined,
  BarChartOutlined,
  TableOutlined,
  SwapOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { TabsProps } from 'antd'

// Components
import { MarkSelector } from './MarkSelector'
import { StatsCards } from './StatsCards'
import { FilterPanel } from './FilterPanel'
import { PeaksTable } from './PeaksTable'
import { CompareCharts } from './CompareCharts'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'

// Hooks
import {
  useChIPSeqPeaks,
  useChIPSeqSummary,
  useChIPSeqCompare,
  usePrefetchChIPSeqPeaks,
} from '@/hooks/useChIPSeq'

// Config & Types
import { getMarkConfig, getCommonMarks } from '@/config/markConfigs'
import { chipseqApi } from '@/api/chipseq'
import type {
  MarkType,
  ChIPSeqFilters,
  CompareViewMode,
  DEFAULT_CHIPSEQ_FILTERS,
} from '@/types/chipseq'

interface ChIPSeqPeaksTableProps {
  /** Gene ID to display peaks for */
  geneId: number
  /** Initial mark type to select */
  initialMarkType?: MarkType
  /** Available marks (from API, optional) */
  availableMarks?: MarkType[]
  /** Enable comparison mode */
  enableComparison?: boolean
  /** Default flanking region */
  defaultFlanking?: number
  /** Callback when mark changes */
  onMarkChange?: (mark: MarkType | MarkType[]) => void
}

/**
 * ChIPSeqPeaksTable Component
 *
 * A comprehensive, configuration-driven component for displaying ChIP-seq
 * peak data. Supports any histone modification mark type.
 *
 * @example Basic usage
 * ```tsx
 * <ChIPSeqPeaksTable geneId={123} />
 * ```
 *
 * @example With initial mark and comparison
 * ```tsx
 * <ChIPSeqPeaksTable
 *   geneId={123}
 *   initialMarkType="H3K27me3"
 *   enableComparison
 * />
 * ```
 */
export function ChIPSeqPeaksTable({
  geneId,
  initialMarkType,
  availableMarks,
  enableComparison = true,
  defaultFlanking = 10000,
  onMarkChange,
}: ChIPSeqPeaksTableProps) {
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // State
  const [selectedMark, setSelectedMark] = useState<MarkType | undefined>(
    initialMarkType || getCommonMarks()[0]
  )
  const [selectedMarksForCompare, setSelectedMarksForCompare] = useState<MarkType[]>([])
  const [compareMode, setCompareMode] = useState(false)
  const [viewMode, setViewMode] = useState<CompareViewMode>('merged')

  // Filters state with defaults from mark config
  const [filters, setFilters] = useState<ChIPSeqFilters>(() => {
    const markConfig = selectedMark ? getMarkConfig(selectedMark) : null
    return {
      mark_type: selectedMark,
      page: 1,
      page_size: 20,
      flanking: defaultFlanking,
      ...markConfig?.defaultFilters,
    }
  })

  // Prefetch hook for optimization
  const prefetchPeaks = usePrefetchChIPSeqPeaks()

  // Data fetching hooks
  const {
    data: peaksData,
    isLoading: peaksLoading,
    error: peaksError,
    refetch: refetchPeaks,
  } = useChIPSeqPeaks(geneId, filters, {
    enabled: !compareMode && !!selectedMark,
  })

  const {
    data: summaryData,
    isLoading: summaryLoading,
  } = useChIPSeqSummary(geneId, selectedMark, {
    enabled: !compareMode && !!selectedMark,
  })

  const {
    data: compareData,
    isLoading: compareLoading,
    error: compareError,
  } = useChIPSeqCompare(geneId, selectedMarksForCompare, filters.flanking, {
    enabled: compareMode && selectedMarksForCompare.length > 0,
  })

  // Handle mark selection change
  const handleMarkChange = useCallback(
    (mark: MarkType) => {
      setSelectedMark(mark)
      const markConfig = getMarkConfig(mark)

      // Update filters with mark-specific defaults
      setFilters((prev) => ({
        ...prev,
        mark_type: mark,
        page: 1,
        ...markConfig.defaultFilters,
      }))

      onMarkChange?.(mark)
    },
    [onMarkChange]
  )

  // Handle multi-mark selection for comparison
  const handleCompareMarksChange = useCallback(
    (marks: MarkType[]) => {
      setSelectedMarksForCompare(marks)
      onMarkChange?.(marks)
    },
    [onMarkChange]
  )

  // Handle filter changes
  const handleFiltersChange = useCallback((newFilters: ChIPSeqFilters) => {
    setFilters(newFilters)
  }, [])

  // Reset filters to defaults
  const handleResetFilters = useCallback(() => {
    const markConfig = selectedMark ? getMarkConfig(selectedMark) : null
    setFilters({
      mark_type: selectedMark,
      page: 1,
      page_size: 20,
      flanking: defaultFlanking,
      ...markConfig?.defaultFilters,
    })
  }, [selectedMark, defaultFlanking])

  // Toggle comparison mode
  const handleToggleCompareMode = useCallback(() => {
    if (!compareMode) {
      // Entering compare mode - pre-select current mark
      setSelectedMarksForCompare(selectedMark ? [selectedMark] : [])
    }
    setCompareMode(!compareMode)
  }, [compareMode, selectedMark])

  // Handle export
  const handleExport = useCallback(() => {
    if (compareMode && selectedMarksForCompare.length > 0) {
      chipseqApi.exportComparisonToCSV(geneId, selectedMarksForCompare)
      message.success(t('detail.chipseq.exportSuccess', 'Export started'))
    } else if (selectedMark) {
      chipseqApi.exportPeaksToBED(geneId, filters)
      message.success(t('detail.chipseq.exportSuccess', 'Export started'))
    }
  }, [geneId, compareMode, selectedMarksForCompare, selectedMark, filters, t])

  // Prefetch on hover
  const handleMarkHover = useCallback(
    (markType: MarkType) => {
      const markConfig = getMarkConfig(markType)
      prefetchPeaks(geneId, {
        mark_type: markType,
        page: 1,
        page_size: 20,
        flanking: defaultFlanking,
        ...markConfig.defaultFilters,
      })
    },
    [geneId, defaultFlanking, prefetchPeaks]
  )

  // Compare view tabs
  const compareViewTabs: TabsProps['items'] = useMemo(
    () => [
      {
        key: 'merged',
        label: (
          <span>
            <TableOutlined />
            {t('detail.chipseq.mergedView', 'Merged View')}
          </span>
        ),
      },
      {
        key: 'parallel',
        label: (
          <span>
            <SwapOutlined />
            {t('detail.chipseq.parallelView', 'Parallel')}
          </span>
        ),
        disabled: selectedMarksForCompare.length !== 2,
      },
      {
        key: 'stats',
        label: (
          <span>
            <BarChartOutlined />
            {t('detail.chipseq.statsView', 'Statistics')}
          </span>
        ),
      },
    ],
    [t, selectedMarksForCompare.length]
  )

  // Render single mark view
  const renderSingleMarkView = () => {
    if (!selectedMark) {
      return (
        <Empty
          description={t('detail.chipseq.selectMark', 'Select a histone mark to view peaks')}
        />
      )
    }

    if (peaksLoading) {
      return <LoadingState />
    }

    if (peaksError) {
      return <ErrorState error={peaksError} onRetry={() => refetchPeaks()} />
    }

    if (!peaksData || peaksData.total === 0) {
      return (
        <Empty
          description={t('detail.chipseq.noPeaks', 'No peaks found for this gene')}
          style={{ padding: 48 }}
        />
      )
    }

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Statistics Cards */}
        <StatsCards
          markType={selectedMark}
          summary={summaryData}
          loading={summaryLoading}
        />

        {/* Filter Panel */}
        <FilterPanel
          markType={selectedMark}
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onReset={handleResetFilters}
        />

        {/* Data Table */}
        <Card
          title={
            <span>
              {t('detail.chipseq.peaks', 'ChIP-seq Peaks')} (
              {peaksData.total.toLocaleString()})
            </span>
          }
          extra={
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExport}
              disabled={peaksData.total === 0}
            >
              {t('detail.chipseq.exportBED', 'Export BED')}
            </Button>
          }
        >
          <PeaksTable
            markType={selectedMark}
            items={peaksData.items}
            total={peaksData.total}
            page={peaksData.page}
            pageSize={peaksData.page_size}
            loading={peaksLoading}
            filters={filters}
            onFiltersChange={handleFiltersChange}
          />
        </Card>
      </Space>
    )
  }

  // Render comparison view
  const renderCompareView = () => {
    if (selectedMarksForCompare.length === 0) {
      return (
        <Alert
          type="info"
          message={t('detail.chipseq.selectMarksToCompare', 'Select marks to compare')}
          description={t(
            'detail.chipseq.selectMarksDescription',
            'Choose 2 or more marks from the selector above to compare their ChIP-seq profiles.'
          )}
          showIcon
        />
      )
    }

    if (compareLoading) {
      return <LoadingState />
    }

    if (compareError) {
      return <ErrorState error={compareError} />
    }

    // Render based on view mode
    switch (viewMode) {
      case 'stats':
        return (
          <CompareCharts
            compareData={compareData}
            selectedMarks={selectedMarksForCompare}
            loading={compareLoading}
          />
        )

      case 'parallel':
        if (selectedMarksForCompare.length !== 2) {
          return (
            <Alert
              type="warning"
              message={t('detail.chipseq.parallelRequiresTwoMarks', 'Select exactly 2 marks')}
            />
          )
        }
        // Render parallel view with two tables
        return (
          <Row gutter={16}>
            {selectedMarksForCompare.map((mark) => {
              const markData = compareData?.marks.find((m) => m.mark_type === mark)
              return (
                <Col xs={24} lg={12} key={mark}>
                  <Card
                    title={
                      <span style={{ color: getMarkConfig(mark).color }}>
                        {getMarkConfig(mark).displayName}
                      </span>
                    }
                    size="small"
                  >
                    {markData && (
                      <PeaksTable
                        markType={mark}
                        items={markData.top_peaks}
                        total={markData.top_peaks.length}
                        page={1}
                        pageSize={markData.top_peaks.length}
                        filters={filters}
                        onFiltersChange={handleFiltersChange}
                      />
                    )}
                  </Card>
                </Col>
              )
            })}
          </Row>
        )

      case 'merged':
      default:
        // Merge all peaks into one table
        const allPeaks = compareData?.marks.flatMap((m) =>
          m.top_peaks.map((peak) => ({ ...peak, mark_type: m.mark_type }))
        ) || []

        return (
          <Card
            title={t('detail.chipseq.mergedPeaks', 'Merged Peaks')}
            extra={
              <Button
                icon={<DownloadOutlined />}
                onClick={handleExport}
                disabled={allPeaks.length === 0}
              >
                {t('detail.chipseq.exportCSV', 'Export CSV')}
              </Button>
            }
          >
            <PeaksTable
              markType={selectedMarksForCompare[0]}
              items={allPeaks}
              total={allPeaks.length}
              page={1}
              pageSize={allPeaks.length}
              filters={filters}
              onFiltersChange={handleFiltersChange}
              showMarkColumn
            />
          </Card>
        )
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header with mark selector */}
      <Card size="small">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={16}>
            {compareMode ? (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ fontWeight: 500 }}>
                  {t('detail.chipseq.selectMarksToCompare', 'Select marks to compare')}:
                </span>
                <MarkSelector
                  value={selectedMarksForCompare}
                  onChange={(marks) => handleCompareMarksChange(marks as MarkType[])}
                  multiple
                  maxCount={5}
                  availableMarks={availableMarks}
                  onOptionHover={handleMarkHover}
                  style={{ width: '100%' }}
                />
              </Space>
            ) : (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ fontWeight: 500 }}>
                  {t('detail.chipseq.selectMark', 'Select histone mark')}:
                </span>
                <MarkSelector
                  value={selectedMark}
                  onChange={(mark) => handleMarkChange(mark as MarkType)}
                  availableMarks={availableMarks}
                  onOptionHover={handleMarkHover}
                  style={{ width: '100%', maxWidth: 400 }}
                />
              </Space>
            )}
          </Col>
          <Col xs={24} md={8} style={{ textAlign: 'right' }}>
            {enableComparison && (
              <Button
                type={compareMode ? 'primary' : 'default'}
                icon={<ExperimentOutlined />}
                onClick={handleToggleCompareMode}
              >
                {compareMode
                  ? t('detail.chipseq.exitCompare', 'Exit Comparison')
                  : t('detail.chipseq.compareMarks', 'Compare Marks')}
              </Button>
            )}
          </Col>
        </Row>
      </Card>

      {/* Compare mode tabs */}
      {compareMode && selectedMarksForCompare.length > 0 && (
        <Tabs
          activeKey={viewMode}
          onChange={(key) => setViewMode(key as CompareViewMode)}
          items={compareViewTabs}
          type="card"
        />
      )}

      {/* Main content */}
      {compareMode ? renderCompareView() : renderSingleMarkView()}
    </Space>
  )
}

export default ChIPSeqPeaksTable
