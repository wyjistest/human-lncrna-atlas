/**
 * PeaksTable Component
 * Phase 2.2 - Data table for ChIP-seq peaks with sorting and pagination
 *
 * Features:
 * - Sortable columns
 * - Server-side pagination
 * - Color-coded values based on significance
 * - Responsive design
 * - Export functionality
 */

import { useMemo, useCallback } from 'react'
import { Table, Tag, Tooltip, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue, SorterResult } from 'antd/es/table/interface'
import { getMarkConfig } from '@/config/markConfigs'
import type { MarkType, ChIPSeqPeak, ChIPSeqFilters } from '@/types/chipseq'

const { Text } = Typography

interface PeaksTableProps {
  /** Mark type for styling */
  markType: MarkType
  /** Peak data items */
  items: ChIPSeqPeak[]
  /** Total count for pagination */
  total: number
  /** Current page */
  page: number
  /** Page size */
  pageSize: number
  /** Loading state */
  loading?: boolean
  /** Current filters (for sort indicators) */
  filters: ChIPSeqFilters
  /** Filter change handler */
  onFiltersChange: (filters: ChIPSeqFilters) => void
  /** Show mark column (for merged view) */
  showMarkColumn?: boolean
}

/**
 * Format scientific notation for p-values/q-values
 */
function formatScientific(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A'
  if (value === 0) return '0'
  if (value < 0.001) {
    return value.toExponential(2)
  }
  return value.toFixed(4)
}

/**
 * Get color based on q-value significance
 */
function getQValueColor(qvalue: number | null | undefined): string {
  if (qvalue === null || qvalue === undefined) return '#888888' // Unknown
  if (qvalue <= 0.001) return '#52c41a' // Highly significant
  if (qvalue <= 0.01) return '#73d13d'
  if (qvalue <= 0.05) return '#faad14' // Significant
  return '#f5222d' // Not significant
}

/**
 * Get color based on fold enrichment
 */
function getFoldEnrichmentColor(fe: number | null | undefined): string {
  if (fe === null || fe === undefined) return '#888888' // Unknown
  if (fe >= 10) return '#1890ff'
  if (fe >= 5) return '#52c41a'
  if (fe >= 2) return '#faad14'
  return '#ff7a45'
}

/**
 * Position tag with color coding
 */
function PositionTag({ position }: { position: string | undefined }) {
  if (!position) return <span>-</span>

  const colorMap: Record<string, string> = {
    promoter: 'green',
    upstream: 'blue',
    downstream: 'purple',
    exon: 'orange',
    intron: 'cyan',
    gene_body: 'magenta',
    intergenic: 'default',
  }

  return (
    <Tag color={colorMap[position.toLowerCase()] || 'default'}>
      {position}
    </Tag>
  )
}

/**
 * PeaksTable Component
 *
 * Displays ChIP-seq peak data in a sortable, paginated table.
 *
 * @example
 * ```tsx
 * <PeaksTable
 *   markType="H3K27me3"
 *   items={peaksData.items}
 *   total={peaksData.total}
 *   page={currentPage}
 *   pageSize={20}
 *   filters={filters}
 *   onFiltersChange={handleFiltersChange}
 * />
 * ```
 */
export function PeaksTable({
  items,
  total,
  page,
  pageSize,
  loading = false,
  filters,
  onFiltersChange,
  showMarkColumn = false,
}: PeaksTableProps) {
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // Table columns definition
  const columns: ColumnsType<ChIPSeqPeak> = useMemo(() => {
    const baseColumns: ColumnsType<ChIPSeqPeak> = []

    // Optional mark column (for merged view)
    if (showMarkColumn) {
      baseColumns.push({
        title: t('detail.chipseq.mark', 'Mark'),
        dataIndex: 'mark_type',
        key: 'mark_type',
        width: 100,
        fixed: 'left',
        render: (mark: MarkType) => {
          const config = getMarkConfig(mark)
          return (
            <Tag color={config.color} style={{ minWidth: 60, textAlign: 'center' }}>
              {config.shortName}
            </Tag>
          )
        },
      })
    }

    // Standard columns
    baseColumns.push(
      {
        title: t('detail.chipseq.chromosome', 'Chr'),
        dataIndex: 'chromosome',
        key: 'chromosome',
        width: 80,
        render: (chr: string) => (
          <Text style={{ fontFamily: 'monospace' }}>{chr}</Text>
        ),
      },
      {
        title: t('detail.chipseq.peakStart', 'Start'),
        dataIndex: 'peak_start',
        key: 'peak_start',
        width: 120,
        align: 'right',
        sorter: true,
        sortOrder: filters.sort_by === 'peak_start' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (val: number) => (
          <Text style={{ fontFamily: 'monospace' }}>
            {val?.toLocaleString() ?? '-'}
          </Text>
        ),
      },
      {
        title: t('detail.chipseq.peakEnd', 'End'),
        dataIndex: 'peak_end',
        key: 'peak_end',
        width: 120,
        align: 'right',
        render: (val: number) => (
          <Text style={{ fontFamily: 'monospace' }}>
            {val?.toLocaleString() ?? '-'}
          </Text>
        ),
      },
      {
        title: t('detail.chipseq.width', 'Width'),
        dataIndex: 'peak_width',
        key: 'peak_width',
        width: 90,
        align: 'right',
        render: (val: number) => (
          <Text>
            {val?.toLocaleString() ?? '-'} bp
          </Text>
        ),
      },
      {
        title: (
          <Tooltip title={t('detail.chipseq.signalTooltip', 'Signal intensity at peak')}>
            <span>{t('detail.chipseq.signal', 'Signal')}</span>
          </Tooltip>
        ),
        dataIndex: 'signal_value',
        key: 'signal_value',
        width: 100,
        align: 'right',
        sorter: true,
        sortOrder: filters.sort_by === 'signal_value' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (val: number) => (
          <Text style={{ fontWeight: 500 }}>
            {val?.toFixed(2) ?? '-'}
          </Text>
        ),
      },
      {
        title: (
          <Tooltip title={t('detail.chipseq.foldEnrichmentTooltip', 'Signal enrichment over background')}>
            <span>{t('detail.chipseq.foldEnrichmentShort', 'Fold')}</span>
          </Tooltip>
        ),
        dataIndex: 'fold_enrichment',
        key: 'fold_enrichment',
        width: 90,
        align: 'right',
        sorter: true,
        sortOrder: filters.sort_by === 'fold_enrichment' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (val: number) => (
          <Text style={{ color: getFoldEnrichmentColor(val), fontWeight: 500 }}>
            {val?.toFixed(2) ?? '-'}x
          </Text>
        ),
      },
      {
        title: (
          <Tooltip title={t('detail.chipseq.qvalueTooltip', 'False Discovery Rate')}>
            <span>Q-Value</span>
          </Tooltip>
        ),
        dataIndex: 'qvalue',
        key: 'qvalue',
        width: 100,
        align: 'right',
        sorter: true,
        sortOrder: filters.sort_by === 'qvalue' ? (filters.sort_order === 'asc' ? 'ascend' : 'descend') : undefined,
        render: (val: number) => (
          <Text style={{ color: getQValueColor(val) }}>
            {formatScientific(val)}
          </Text>
        ),
      },
      {
        title: t('detail.chipseq.position', 'Position'),
        dataIndex: 'relative_position',
        key: 'relative_position',
        width: 100,
        render: (pos: string) => <PositionTag position={pos} />,
      },
      {
        title: t('detail.chipseq.distanceToTSS', 'TSS Dist'),
        dataIndex: 'distance_to_tss',
        key: 'distance_to_tss',
        width: 100,
        align: 'right',
        render: (val: number | undefined) => {
          if (val === undefined || val === null) return '-'
          const absVal = Math.abs(val)
          const prefix = val >= 0 ? '+' : '-'
          if (absVal >= 1000) {
            return `${prefix}${(absVal / 1000).toFixed(1)}kb`
          }
          return `${prefix}${absVal}bp`
        },
      }
    )

    return baseColumns
  }, [t, filters, showMarkColumn])

  // Handle table change (pagination, sorting)
  const handleTableChange = useCallback(
    (
      pagination: TablePaginationConfig,
      _tableFilters: Record<string, FilterValue | null>,
      sorter: SorterResult<ChIPSeqPeak> | SorterResult<ChIPSeqPeak>[]
    ) => {
      const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter
      const sortField = singleSorter?.field as ChIPSeqFilters['sort_by']
      const sortOrder = singleSorter?.order === 'ascend' ? 'asc' : singleSorter?.order === 'descend' ? 'desc' : undefined

      onFiltersChange({
        ...filters,
        page: pagination.current ?? 1,
        page_size: pagination.pageSize ?? 20,
        sort_by: sortOrder ? sortField : undefined,
        sort_order: sortOrder,
      })
    },
    [filters, onFiltersChange]
  )

  return (
    <Table
      columns={columns}
      dataSource={items}
      rowKey="peak_id"
      loading={loading}
      pagination={{
        current: page,
        pageSize: pageSize,
        total: total,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50', '100'],
        showTotal: (total, range) =>
          `${range[0]}-${range[1]} / ${total.toLocaleString()} ${tCommon('unit.records', 'records')}`,
        showQuickJumper: total > 100,
      }}
      onChange={handleTableChange}
      scroll={{ x: 1000 }}
      size="middle"
      sticky
    />
  )
}

export default PeaksTable
