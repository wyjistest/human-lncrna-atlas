/**
 * LncRNAChIPSeqOverlapTable Main Component
 * Phase 3.0 - Task 1.8 (Updated Phase 3.0 Phase 2)
 *
 * Main container component for lncRNA-ChIP-seq overlap analysis.
 * Displays overlaps between lncRNA binding sites and ChIP-seq peaks.
 *
 * Features:
 * - Advanced filtering (mark type, cell type, chromosome, thresholds)
 * - Statistics cards (Phase 2)
 * - Visualization charts (Phase 3.0 Phase 2)
 *   - Mark type distribution bar chart
 *   - Cell type distribution pie chart
 *   - Overlap heatmap matrix (collapsible)
 * - Sortable, paginated data table
 * - Export functionality (BED, CSV) (Phase 2)
 * - Responsive design
 *
 * Backend Integration:
 * - GET /api/v1/lncrna-chipseq-overlap (paginated query)
 * - GET /api/v1/lncrna-chipseq-overlap/summary (Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/heatmap (Phase 3.0 Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/export (Phase 2)
 */

import { useState, useCallback } from 'react'
import {
  Space,
  Card,
  Button,
  message,
  Empty,
  Alert,
  Switch,
  Row,
  Col,
  Tabs,
} from 'antd'
import {
  DownloadOutlined,
  ReloadOutlined,
  FilterOutlined,
  BarChartOutlined,
  HeatMapOutlined,
  PieChartOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

// Components
import { OverlapFilterPanel } from './OverlapFilterPanel'
import { OverlapTable } from './OverlapTable'
import { OverlapStatsCards } from './OverlapStatsCards'
import { OverlapMarkDistChart } from './OverlapMarkDistChart'
import { OverlapCellTypeChart } from './OverlapCellTypeChart'
import { OverlapHeatmapMatrix } from './OverlapHeatmapMatrix'
import { LoadingState } from '@/components/LoadingState'

// Hooks
import {
  useLncRNAChIPSeqOverlaps,
  useLncRNAChIPSeqOverlapSummary,
} from '@/hooks/useLncRNAChIPSeqOverlap'

// Types
import type { OverlapFilters } from '@/types/lncRNAChIPSeqOverlap'

interface LncRNAChIPSeqOverlapTableProps {
  /** Optional: Pre-filter by lncRNA gene ID */
  lncrnaGeneId?: number
  /** Optional: Pre-filter by target gene ID */
  targetGeneId?: number
  /** Optional: Initial mark types (comma-separated) */
  initialMarkTypes?: string
  /** Optional: Initial cell types (comma-separated) */
  initialCellTypes?: string
  /** Optional: Initial chromosome filter (defaults to 'chr22' - smaller dataset, loads faster ~4s vs chr1's ~48s) */
  initialChromosome?: string
  /** Default page size */
  defaultPageSize?: number
  /** Enable statistics cards (Phase 2 feature) */
  enableStats?: boolean
  /** Enable export functionality (Phase 2 feature) */
  enableExport?: boolean
  /** Enable visualization charts (Phase 3.0 Phase 2 feature) */
  enableVisualization?: boolean
}

/**
 * LncRNAChIPSeqOverlapTable Component
 *
 * Comprehensive viewer for lncRNA-ChIP-seq overlap analysis.
 * Allows filtering, sorting, and browsing overlap data.
 *
 * @example Basic usage
 * ```tsx
 * <LncRNAChIPSeqOverlapTable />
 * ```
 *
 * @example Pre-filtered by lncRNA
 * ```tsx
 * <LncRNAChIPSeqOverlapTable
 *   lncrnaGeneId={123}
 *   initialMarkTypes="H3K27me3,H3K4me3"
 * />
 * ```
 *
 * @example With statistics (Phase 2)
 * ```tsx
 * <LncRNAChIPSeqOverlapTable
 *   enableStats
 *   enableExport
 * />
 * ```
 */
export function LncRNAChIPSeqOverlapTable({
  lncrnaGeneId,
  targetGeneId,
  initialMarkTypes,
  initialCellTypes,
  initialChromosome = 'chr22',  // Changed from chr1 - chr22 loads much faster (~4s vs ~48s)
  defaultPageSize = 20,
  enableStats = false,
  enableExport = false,
  enableVisualization = false,
}: LncRNAChIPSeqOverlapTableProps) {
  const { t } = useTranslation('overlap')
  const { t: tCommon } = useTranslation('common')

  // UI state
  const [showFilters, setShowFilters] = useState(true)
  const [showStats, setShowStats] = useState(enableStats)
  const [showVisualization, setShowVisualization] = useState(enableVisualization)
  const [activeTab, setActiveTab] = useState<string>('table')

  // Filter state - Default chromosome to 'chr22' (smaller dataset, loads in ~4s vs chr1's ~48s)
  const [filters, setFilters] = useState<OverlapFilters>(() => ({
    lncrna_gene_id: lncrnaGeneId,
    target_gene_id: targetGeneId,
    mark_type: initialMarkTypes,
    cell_type: initialCellTypes,
    chromosome: initialChromosome,
    page: 1,
    page_size: defaultPageSize,
  }))

  // Data fetching
  const {
    data: overlapData,
    isLoading: dataLoading,
    error: dataError,
    refetch: refetchData,
  } = useLncRNAChIPSeqOverlaps(filters)

  const {
    data: summaryData,
    isLoading: summaryLoading,
  } = useLncRNAChIPSeqOverlapSummary(filters, {
    enabled: showStats && enableStats,
  })

  // Handle filter changes
  const handleFiltersChange = useCallback(
    (newFilters: Partial<OverlapFilters>) => {
      setFilters((prev) => ({
        ...prev,
        ...newFilters,
      }))
    },
    []
  )

  // Reset all filters - Keep chromosome default to prevent timeout
  const handleResetFilters = useCallback(() => {
    setFilters({
      lncrna_gene_id: lncrnaGeneId,
      target_gene_id: targetGeneId,
      mark_type: initialMarkTypes,
      cell_type: initialCellTypes,
      chromosome: initialChromosome,
      page: 1,
      page_size: defaultPageSize,
    })
    message.success(tCommon('message.filtersReset', 'Filters reset'))
  }, [lncrnaGeneId, targetGeneId, initialMarkTypes, initialCellTypes, initialChromosome, defaultPageSize, tCommon])

  // Export data (Phase 2)
  const handleExport = useCallback(
    (format: 'bed' | 'csv') => {
      message.info(t('message.exportStarting', `Exporting to ${format.toUpperCase()}...`))
      // Export logic will be implemented in Phase 2
      // For now, just show a message
      message.warning(t('message.exportNotImplemented', 'Export functionality coming in Phase 2'))
    },
    [t]
  )

  // Loading state - only show full page loading on initial load
  if (dataLoading && !overlapData && !dataError) {
    return <LoadingState />
  }

  // Determine if we should show the table or empty state
  const hasData = overlapData && overlapData.total > 0
  const showEmptyState = !dataError && overlapData && overlapData.total === 0

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Error Alert - Show at top but allow filter panel to remain visible */}
      {dataError && (
        <Alert
          type="error"
          message={t('error.title', 'Loading Failed')}
          description={
            <Space direction="vertical" size="small">
              <span>{dataError.message || t('error.unknown', 'An unknown error occurred')}</span>
              <span style={{ fontSize: 12, color: '#999' }}>
                {t('error.tryAdjustFilters', 'Try adjusting filters or retry the request')}
              </span>
            </Space>
          }
          action={
            <Button size="small" onClick={() => refetchData()} loading={dataLoading}>
              {tCommon('action.retry', 'Retry')}
            </Button>
          }
          showIcon
          closable
          style={{ marginBottom: 0 }}
        />
      )}

      {/* Header with controls */}
      <Card size="small">
        <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <Space wrap>
            <Button
              icon={<FilterOutlined />}
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? t('action.hideFilters', 'Hide Filters') : t('action.showFilters', 'Show Filters')}
            </Button>

            {enableStats && (
              <Space>
                <BarChartOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showStats', 'Show Statistics')}:
                </span>
                <Switch
                  checked={showStats}
                  onChange={setShowStats}
                  size="small"
                />
              </Space>
            )}

            {enableVisualization && (
              <Space>
                <PieChartOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showVisualization', 'Show Visualization')}:
                </span>
                <Switch
                  checked={showVisualization}
                  onChange={setShowVisualization}
                  size="small"
                />
              </Space>
            )}

            <Button
              icon={<ReloadOutlined />}
              onClick={() => refetchData()}
              loading={dataLoading}
            >
              {tCommon('action.refresh', 'Refresh')}
            </Button>
          </Space>

          {enableExport && overlapData && overlapData.total > 0 && (
            <Space>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleExport('bed')}
              >
                {t('action.exportBED', 'Export BED')}
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleExport('csv')}
              >
                {t('action.exportCSV', 'Export CSV')}
              </Button>
            </Space>
          )}
        </Space>
      </Card>

      {/* Phase 2 Notice */}
      {enableStats && !showStats && (
        <Alert
          type="info"
          message={t('notice.statsPhase2Title', 'Statistics Feature')}
          description={t(
            'notice.statsPhase2Desc',
            'Enable statistics to see aggregate metrics and distributions (Phase 2 feature)'
          )}
          showIcon
          closable
        />
      )}

      {/* Statistics Cards (Phase 2) */}
      {showStats && enableStats && (
        <OverlapStatsCards
          summary={summaryData}
          loading={summaryLoading}
        />
      )}

      {/* Visualization Charts (Phase 3.0 Phase 2) */}
      {showVisualization && enableVisualization && summaryData && (
        <Card
          title={
            <Space>
              <BarChartOutlined />
              {t('visualization.title', 'Overlap Visualizations')}
            </Space>
          }
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'charts',
                label: (
                  <Space>
                    <PieChartOutlined />
                    {t('visualization.distributionCharts', 'Distribution Charts')}
                  </Space>
                ),
                children: (
                  <Row gutter={[16, 16]}>
                    {/* Mark Type Distribution Bar Chart */}
                    <Col xs={24} lg={12}>
                      <Card size="small" bordered={false}>
                        <OverlapMarkDistChart
                          data={summaryData.by_mark_type}
                          loading={summaryLoading}
                        />
                      </Card>
                    </Col>
                    {/* Cell Type Distribution Pie Chart */}
                    <Col xs={24} lg={12}>
                      <Card size="small" bordered={false}>
                        <OverlapCellTypeChart
                          data={summaryData.by_cell_type}
                          loading={summaryLoading}
                        />
                      </Card>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'heatmap',
                label: (
                  <Space>
                    <HeatMapOutlined />
                    {t('visualization.heatmap', 'Heatmap Matrix')}
                  </Space>
                ),
                children: (
                  <OverlapHeatmapMatrix
                    initialXAxis="mark_type"
                    initialYAxis="lncrna"
                    initialMetric="count"
                    filters={filters}
                    showControls
                  />
                ),
              },
              {
                key: 'table',
                label: t('visualization.tableView', 'Table View'),
                children: null, // Table is shown outside tabs
              },
            ]}
          />
        </Card>
      )}

      {/* Filter Panel */}
      {showFilters && (
        <OverlapFilterPanel
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onReset={handleResetFilters}
        />
      )}

      {/* Data Table */}
      <Card
        title={
          <Space>
            {t('table.title', 'lncRNA-ChIP-seq Overlaps')}
            {hasData && (
              <span style={{ fontWeight: 'normal', color: '#999' }}>
                ({overlapData.total.toLocaleString()})
              </span>
            )}
          </Space>
        }
      >
        {/* Show table when we have data */}
        {hasData && (
          <OverlapTable
            items={overlapData.items}
            total={overlapData.total}
            page={overlapData.page}
            pageSize={overlapData.page_size}
            loading={dataLoading}
            filters={filters}
            onFiltersChange={handleFiltersChange}
          />
        )}

        {/* Empty state - no data found with current filters */}
        {showEmptyState && (
          <Empty
            description={
              <Space direction="vertical">
                <span>{t('empty.noOverlaps', 'No overlaps found')}</span>
                <span style={{ fontSize: 12, color: '#999' }}>
                  {t('empty.tryAdjustFilters', 'Try adjusting your filters')}
                </span>
              </Space>
            }
          >
            <Button onClick={handleResetFilters} icon={<ReloadOutlined />}>
              {tCommon('action.resetFilters', 'Reset Filters')}
            </Button>
          </Empty>
        )}

        {/* Error state - show message with suggestion to adjust filters */}
        {dataError && !hasData && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical">
                <span>{t('error.noDataDueToError', 'Unable to load data')}</span>
                <span style={{ fontSize: 12, color: '#999' }}>
                  {t('error.adjustFiltersAbove', 'Adjust filters above and retry')}
                </span>
              </Space>
            }
          />
        )}
      </Card>

      {/* Context Info */}
      {(lncrnaGeneId || targetGeneId) && (
        <Alert
          type="info"
          message={t('info.filteredView', 'Filtered View')}
          description={
            <Space direction="vertical" size={0}>
              {lncrnaGeneId && (
                <span>
                  {t('info.filteredByLncRNA', 'Filtered by lncRNA')}:{' '}
                  <strong>Gene ID {lncrnaGeneId}</strong>
                </span>
              )}
              {targetGeneId && (
                <span>
                  {t('info.filteredByTarget', 'Filtered by target gene')}:{' '}
                  <strong>Gene ID {targetGeneId}</strong>
                </span>
              )}
            </Space>
          }
          showIcon
        />
      )}
    </Space>
  )
}

export default LncRNAChIPSeqOverlapTable
