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
 * - IGV Genome Browser integration (Phase 3.4)
 *   - Split layout (table top, IGV bottom)
 *   - Click table row to navigate IGV
 *   - Dynamic overlap track loading
 * - Export functionality (BED, CSV) (Phase 2)
 * - Responsive design
 *
 * Backend Integration:
 * - GET /api/v1/lncrna-chipseq-overlap (paginated query)
 * - GET /api/v1/lncrna-chipseq-overlap/summary (Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/heatmap (Phase 3.0 Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/export (Phase 2)
 */

import { useState, useCallback, useMemo, useRef } from 'react'
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
  Dropdown,
  Modal,
  Tooltip,
} from 'antd'
import {
  DownloadOutlined,
  ReloadOutlined,
  FilterOutlined,
  BarChartOutlined,
  HeatMapOutlined,
  PieChartOutlined,
  FileTextOutlined,
  FileExcelOutlined,
  DownOutlined,
  InfoCircleOutlined,
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
import GenomeBrowser, { type GenomeBrowserHandle } from '@/components/GenomeBrowser'

// Hooks
import {
  useLncRNAChIPSeqOverlaps,
  useLncRNAChIPSeqOverlapSummary,
} from '@/hooks/useLncRNAChIPSeqOverlap'

// Types
import type { OverlapFilters, OverlapResult } from '@/types/lncRNAChIPSeqOverlap'

interface LncRNAChIPSeqOverlapTableProps {
  /** Optional: Pre-filter by lncRNA gene ID */
  lncrnaGeneId?: number
  /** Optional: Pre-filter by target gene ID */
  targetGeneId?: number
  /** Optional: Initial mark types (comma-separated) */
  initialMarkTypes?: string
  /** Optional: Initial cell types (comma-separated) */
  initialCellTypes?: string
  /** Optional: Initial chromosome filter (undefined = all chromosomes, requires materialized view optimization) */
  initialChromosome?: string
  /** Default page size */
  defaultPageSize?: number
  /** Enable statistics cards (Phase 2 feature) */
  enableStats?: boolean
  /** Enable export functionality (Phase 2 feature) */
  enableExport?: boolean
  /** Enable visualization charts (Phase 3.0 Phase 2 feature) */
  enableVisualization?: boolean
  /** Enable IGV genome browser integration (Phase 3.4 feature) */
  enableIGV?: boolean
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
  initialChromosome,  // No default - allows querying all chromosomes (requires backend materialized view)
  defaultPageSize = 20,
  enableStats = false,
  enableExport = false,
  enableVisualization = false,
  enableIGV = false,
}: LncRNAChIPSeqOverlapTableProps) {
  const { t } = useTranslation('overlap')
  const { t: tCommon } = useTranslation('common')

  // UI state
  const [showFilters, setShowFilters] = useState(true)
  const [showStats, setShowStats] = useState(enableStats)
  const [showVisualization, setShowVisualization] = useState(enableVisualization)
  const [showIGV, setShowIGV] = useState(enableIGV)
  const [activeTab, setActiveTab] = useState<string>('table')

  // IGV browser handle reference
  const browserHandleRef = useRef<GenomeBrowserHandle | null>(null)

  // Filter state - No default chromosome (backend uses materialized view for all-chromosome queries)
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

  // Reset all filters - No chromosome default (backend handles via materialized view)
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

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.mark_type) count++
    if (filters.cell_type) count++
    if (filters.chromosome) count++
    if (filters.min_overlap_length) count++
    if (filters.min_binding_affinity) count++
    return count
  }, [filters])

  // Handle table row click to navigate IGV
  const handleRowClick = useCallback((record: OverlapResult) => {
    if (!browserHandleRef.current) {
      message.warning(t('igv.browserNotReady', 'IGV browser is not ready'))
      return
    }

    // Calculate locus with padding (50kb on each side)
    const padding = 50000
    const start = Math.max(0, record.overlap_start - padding)
    const end = record.overlap_end + padding
    const locus = `${record.chromosome}:${start}-${end}`

    // Navigate IGV
    browserHandleRef.current.navigateToLocus(locus)
      .then(() => {
        message.success(
          t('igv.navigateSuccess', {
            lncrna: record.lncrna_name || `Gene ${record.lncrna_gene_id}`,
            defaultValue: `Navigated to ${record.lncrna_name}`
          })
        )
      })
      .catch((error) => {
        console.error('IGV navigation failed:', error)
        message.error(t('igv.navigateError', 'Failed to navigate IGV'))
      })
  }, [t])

  // Perform export - internal function
  // Note: exportOverlaps opens a new window for download, which has limited error handling
  const performExport = useCallback(
    (format: 'bed' | 'csv') => {
      message.loading({
        content: t('export.starting', `Starting ${format.toUpperCase()} export...`),
        key: 'export',
        duration: 0 // Keep loading until we update it
      })

      try {
        // Build the export URL for validation
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
        const params = new URLSearchParams()

        // Validate filters and build URL parameters
        if (filters.lncrna_gene_id) params.append('lncrna_gene_id', String(filters.lncrna_gene_id))
        if (filters.target_gene_id) params.append('target_gene_id', String(filters.target_gene_id))
        if (filters.mark_type) params.append('mark_type', filters.mark_type)
        if (filters.cell_type) params.append('cell_type', filters.cell_type)
        if (filters.chromosome) params.append('chromosome', filters.chromosome)
        if (filters.min_overlap_length !== undefined) params.append('min_overlap_length', String(filters.min_overlap_length))
        if (filters.min_binding_affinity !== undefined) params.append('min_binding_affinity', String(filters.min_binding_affinity))
        params.append('format', format)

        const exportUrl = `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export?${params.toString()}`

        // Open in new window
        const newWindow = window.open(exportUrl, '_blank')

        // Check if popup was blocked
        if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
          message.warning({
            content: t('export.popupBlocked', 'Please allow popups to download the file, or try right-clicking and "Save As"'),
            key: 'export',
            duration: 5
          })
        } else {
          // Successful window open - show success message after delay
          setTimeout(() => {
            message.success({
              content: t('export.success', `${format.toUpperCase()} export started - check your downloads`),
              key: 'export',
              duration: 3
            })
          }, 1000)
        }
      } catch (error) {
        console.error('Export failed:', error)
        message.error({
          content: t('export.error.failed', `Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`),
          key: 'export',
          duration: 5
        })
      }
    },
    [filters, t]
  )

  // Export data handler with large data warning
  const handleExport = useCallback(
    (format: 'bed' | 'csv') => {
      // Check for large export warning (no chromosome filter)
      if (!filters.chromosome && overlapData && overlapData.total > 50000) {
        Modal.confirm({
          title: t('export.largeDataWarning.title'),
          content: t('export.largeDataWarning.noChromosomeWarning'),
          okText: t('export.largeDataWarning.proceed'),
          cancelText: t('export.largeDataWarning.cancel'),
          onOk: () => performExport(format),
        })
        return
      }

      performExport(format)
    },
    [filters, overlapData, t, performExport]
  )

  // Check if querying all chromosomes (potentially large query)
  const isAllChromosomeQuery = !filters.chromosome

  // Loading state - show enhanced loading for all-chromosome queries
  if (dataLoading && !overlapData && !dataError) {
    return (
      <LoadingState
        message={isAllChromosomeQuery
          ? t('loading.allChromosomes', 'Loading data from all chromosomes...')
          : t('loading.data', 'Loading data...')
        }
        tip={isAllChromosomeQuery
          ? t('loading.allChromosomesTip', 'This query covers all chromosomes and may take longer. Consider filtering by chromosome for faster results.')
          : undefined
        }
        showProgress={isAllChromosomeQuery}
        estimatedTime={isAllChromosomeQuery ? 15 : undefined}
      />
    )
  }

  // Determine if we should show the table or empty state
  const hasData = overlapData && overlapData.total > 0
  const showEmptyState = !dataError && overlapData && overlapData.total === 0

  // Main layout container style
  const containerStyle: React.CSSProperties = enableIGV && showIGV
    ? { display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', overflow: 'hidden' }
    : {}

  return (
    <div style={containerStyle}>
      {/* Top Section: Table and Filters (when IGV enabled and shown) */}
      <div style={enableIGV && showIGV ? { flex: '0 0 50%', overflow: 'auto', borderBottom: '2px solid #e8e8e8', padding: '16px' } : {}}>
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

            {enableIGV && (
              <Space>
                <HeatMapOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showIGV', 'Show IGV Browser')}:
                </span>
                <Switch
                  checked={showIGV}
                  onChange={setShowIGV}
                  size="small"
                />
              </Space>
            )}

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
            <Tooltip
              title={
                activeFilterCount > 0
                  ? t('export.tooltipWithFilters', { count: activeFilterCount })
                  : t('export.tooltip')
              }
            >
              <Dropdown.Button
                icon={<DownOutlined />}
                menu={{
                  items: [
                    {
                      key: 'bed',
                      label: t('export.bed'),
                      icon: <FileTextOutlined />,
                    },
                    {
                      key: 'csv',
                      label: t('export.csv'),
                      icon: <FileExcelOutlined />,
                    },
                  ],
                  onClick: ({ key }) => handleExport(key as 'bed' | 'csv'),
                }}
                onClick={() => handleExport('bed')}
              >
                <DownloadOutlined />
                {t('export.button')}
              </Dropdown.Button>
            </Tooltip>
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

      {/* All Chromosomes Info Alert */}
      {isAllChromosomeQuery && !dataLoading && hasData && (
        <Alert
          type="info"
          icon={<InfoCircleOutlined />}
          message={t('info.allChromosomesQuery', 'Querying All Chromosomes')}
          description={t(
            'info.allChromosomesDesc',
            'You are viewing data from all chromosomes. For faster queries and exports, consider selecting a specific chromosome from the filter panel.'
          )}
          showIcon
          closable
          style={{ marginBottom: 0 }}
        />
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
            onRowClick={enableIGV && showIGV ? handleRowClick : undefined}
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
      </div>

      {/* Bottom Section: IGV Genome Browser (when enabled and shown) */}
      {enableIGV && showIGV && (
        <div style={{ flex: '1 1 50%', padding: '16px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Card
            title={
              <Space>
                <HeatMapOutlined />
                {t('igv.title', 'Genome Browser')}
                <span style={{ fontWeight: 'normal', color: '#999', fontSize: 13 }}>
                  ({t('igv.clickHint', 'Click table row to navigate')})
                </span>
              </Space>
            }
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '8px' }}
          >
            <GenomeBrowser
              speciesId={1}
              onBrowserReady={(handle) => {
                browserHandleRef.current = handle
              }}
              height="100%"
            />
          </Card>
        </div>
      )}
    </div>
  )
}

export default LncRNAChIPSeqOverlapTable
