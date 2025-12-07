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
  Collapse,
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
import { ErrorState } from '@/components/ErrorState'

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

  // Filter state
  const [filters, setFilters] = useState<OverlapFilters>(() => ({
    lncrna_gene_id: lncrnaGeneId,
    target_gene_id: targetGeneId,
    mark_type: initialMarkTypes,
    cell_type: initialCellTypes,
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

  // Reset all filters
  const handleResetFilters = useCallback(() => {
    setFilters({
      lncrna_gene_id: lncrnaGeneId,
      target_gene_id: targetGeneId,
      mark_type: initialMarkTypes,
      cell_type: initialCellTypes,
      page: 1,
      page_size: defaultPageSize,
    })
    message.success(tCommon('message.filtersReset', 'Filters reset'))
  }, [lncrnaGeneId, targetGeneId, initialMarkTypes, initialCellTypes, defaultPageSize, tCommon])

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

  // Loading state
  if (dataLoading && !overlapData) {
    return <LoadingState />
  }

  // Error state
  if (dataError) {
    return (
      <ErrorState
        error={dataError}
        onRetry={refetchData}
      />
    )
  }

  // No data state
  if (overlapData && overlapData.total === 0) {
    return (
      <Card>
        <Empty
          description={
            <Space direction="vertical">
              <span>{t('empty.noOverlaps', 'No overlaps found')}</span>
              <span style={{ fontSize: 12, color: '#999' }}>
                {t('empty.tryAdjustFilters', 'Try adjusting your filters')}
              </span>
            </Space>
          }
        />
        {Object.keys(filters).length > 2 && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Button onClick={handleResetFilters} icon={<ReloadOutlined />}>
              {tCommon('action.resetFilters', 'Reset Filters')}
            </Button>
          </div>
        )}
      </Card>
    )
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
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
            {overlapData && (
              <span style={{ fontWeight: 'normal', color: '#999' }}>
                ({overlapData.total.toLocaleString()})
              </span>
            )}
          </Space>
        }
      >
        {overlapData && (
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
