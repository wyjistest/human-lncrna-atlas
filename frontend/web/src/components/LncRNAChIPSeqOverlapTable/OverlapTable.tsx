/**
 * OverlapTable Component
 * Phase 3.0 - Task 1.6
 *
 * Data table for lncRNA-ChIP-seq overlaps with sorting and pagination.
 *
 * Features:
 * - Sortable columns
 * - Server-side pagination
 * - Color-coded values (binding affinity, peak strength, Q-value)
 * - Genomic coordinate display
 * - Mark type badges
 * - Cell type tags
 * - Responsive design
 */

import { useMemo, useCallback } from 'react'
import { Table, Tag, Tooltip, Typography, Space } from 'antd'
import { useTranslation } from 'react-i18next'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue, SorterResult } from 'antd/es/table/interface'
import { getMarkConfig } from '@/config/markConfigs'
import { getCellTypeColor } from '@/config/cellTypeConfigs'
import type { OverlapResult, OverlapFilters } from '@/types/lncRNAChIPSeqOverlap'
import type { MarkType } from '@/types/chipseq'

const { Text, Link } = Typography

interface OverlapTableProps {
  /** Overlap data items */
  items: OverlapResult[]
  /** Total count for pagination */
  total: number
  /** Current page */
  page: number
  /** Page size */
  pageSize: number
  /** Whether to show built-in pagination controls */
  paginationEnabled?: boolean
  /** Loading state */
  loading?: boolean
  /** Current filters (for sort indicators) */
  filters: OverlapFilters
  /** Filter change handler */
  onFiltersChange: (filters: Partial<OverlapFilters>) => void
  /** Optional: Row click handler (for IGV integration) */
  onRowClick?: (record: OverlapResult) => void
}

/**
 * Format genomic coordinates
 */
function formatCoordinates(chr: string, start: number, end: number): string {
  return `${chr}:${start.toLocaleString()}-${end.toLocaleString()}`
}

/**
 * Get color based on binding affinity score
 */
function getBindingAffinityColor(score: number): string {
  if (score >= 80) return '#52c41a' // High affinity (green)
  if (score >= 60) return '#1890ff' // Good affinity (blue)
  if (score >= 40) return '#faad14' // Moderate (orange)
  return '#ff4d4f' // Low (red)
}

/**
 * Get color based on peak fold enrichment
 */
function getPeakStrengthColor(fe: number): string {
  if (fe >= 10) return '#1890ff' // Very strong
  if (fe >= 5) return '#52c41a' // Strong
  if (fe >= 2) return '#faad14' // Moderate
  return '#ff7a45' // Weak
}

/**
 * Get color based on Q-value significance
 */
function getQValueColor(qvalue: number | null): string {
  if (qvalue === null) return '#888888' // Unknown
  if (qvalue <= 0.001) return '#52c41a' // Highly significant
  if (qvalue <= 0.01) return '#73d13d'
  if (qvalue <= 0.05) return '#faad14' // Significant
  return '#f5222d' // Not significant
}

/**
 * Format scientific notation for Q-values
 */
function formatQValue(value: number | null): string {
  if (value === null) return 'N/A'
  if (value === 0) return '0'
  if (value < 0.001) return value.toExponential(2)
  return value.toFixed(4)
}

/**
 * OverlapTable Component
 *
 * Displays lncRNA-ChIP-seq overlap data in a sortable, paginated table.
 *
 * @example
 * ```tsx
 * <OverlapTable
 *   items={overlapData.items}
 *   total={overlapData.total}
 *   page={currentPage}
 *   pageSize={20}
 *   filters={filters}
 *   onFiltersChange={handleFiltersChange}
 * />
 * ```
 */
export function OverlapTable({
  items,
  total,
  page,
  pageSize,
  paginationEnabled = true,
  loading = false,
  filters,
  onFiltersChange,
  onRowClick,
}: OverlapTableProps) {
  const { t } = useTranslation('overlap')

  // Table columns definition
  const columns: ColumnsType<OverlapResult> = useMemo(
    () => [
      // lncRNA Information
      {
        title: t('table.lncrna', 'lncRNA'),
        dataIndex: 'lncrna_name',
        key: 'lncrna_name',
        width: 120,
        fixed: 'left',
        render: (name: string | null, record: OverlapResult) => (
          <Tooltip title={`Gene ID: ${record.lncrna_gene_id}`}>
            <Link>{name || `Gene ${record.lncrna_gene_id}`}</Link>
          </Tooltip>
        ),
      },

      // Target Gene Information
      {
        title: t('table.targetGene', 'Target Gene'),
        dataIndex: 'target_gene_name',
        key: 'target_gene_name',
        width: 120,
        render: (name: string | null, record: OverlapResult) => (
          <Tooltip title={`Gene ID: ${record.target_gene_id}`}>
            <Link>{name || `Gene ${record.target_gene_id}`}</Link>
          </Tooltip>
        ),
      },

      // Mark Type
      {
        title: t('table.markType', 'Mark'),
        dataIndex: 'mark_type',
        key: 'mark_type',
        width: 100,
        render: (mark: MarkType) => {
          const config = getMarkConfig(mark)
          return (
            <Tooltip title={config.description}>
              <Tag color={config.color} style={{ minWidth: 80, textAlign: 'center' }}>
                {config.shortName}
              </Tag>
            </Tooltip>
          )
        },
      },

      // Cell Type
      {
        title: t('table.cellType', 'Cell Type'),
        dataIndex: 'cell_type',
        key: 'cell_type',
        width: 100,
        render: (cellType: string) => {
          const color = getCellTypeColor(cellType)
          return (
            <Tag color={color} style={{ minWidth: 70, textAlign: 'center' }}>
              {cellType}
            </Tag>
          )
        },
      },

      // Genomic Location
      {
        title: t('table.location', 'Location'),
        key: 'location',
        width: 180,
        render: (_, record: OverlapResult) => {
          // Handle string/number type mismatch from backend
          const overlapStart = typeof record.overlap_start === 'string' ? parseInt(record.overlap_start, 10) : record.overlap_start
          const overlapEnd = typeof record.overlap_end === 'string' ? parseInt(record.overlap_end, 10) : record.overlap_end
          const overlapLength = typeof record.overlap_length === 'string' ? parseInt(record.overlap_length, 10) : record.overlap_length
          return (
            <Space orientation="vertical" size={0}>
              <Text style={{ fontSize: 12 }}>
                {formatCoordinates(record.chromosome, overlapStart, overlapEnd)}
              </Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {overlapLength.toLocaleString()} bp
              </Text>
            </Space>
          )
        },
      },

      // Binding Affinity
      {
        title: (
          <Tooltip title={t('table.bindingAffinityTooltip', 'lncRNA-target binding strength')}>
            {t('table.bindingAffinity', 'Binding Affinity')}
          </Tooltip>
        ),
        dataIndex: 'binding_affinity',
        key: 'binding_affinity',
        width: 110,
        sorter: true,
        sortOrder:
          filters.sort_by === 'binding_affinity'
            ? filters.sort_order === 'asc'
              ? 'ascend'
              : 'descend'
            : null,
        render: (score: number | string | null) => {
          const numScore = typeof score === 'string' ? parseFloat(score) : (score ?? 0)
          return (
            <Text strong style={{ color: getBindingAffinityColor(numScore) }}>
              {numScore.toFixed(1)}
            </Text>
          )
        },
      },

      // Peak Strength
      {
        title: (
          <Tooltip title={t('table.peakStrengthTooltip', 'ChIP-seq peak fold enrichment')}>
            {t('table.peakStrength', 'Peak Strength')}
          </Tooltip>
        ),
        dataIndex: 'peak_fold_enrichment',
        key: 'peak_fold_enrichment',
        width: 110,
        sorter: true,
        sortOrder:
          filters.sort_by === 'peak_fold_enrichment'
            ? filters.sort_order === 'asc'
              ? 'ascend'
              : 'descend'
            : null,
        render: (fe: number | string | null) => {
          const numFe = typeof fe === 'string' ? parseFloat(fe) : (fe ?? 0)
          return (
            <Text strong style={{ color: getPeakStrengthColor(numFe) }}>
              {numFe.toFixed(2)}x
            </Text>
          )
        },
      },

      // Q-value (FDR)
      {
        title: (
          <Tooltip title={t('table.qvalueTooltip', 'Peak significance (False Discovery Rate)')}>
            {t('table.qvalue', 'Q-value')}
          </Tooltip>
        ),
        dataIndex: 'peak_qvalue',
        key: 'peak_qvalue',
        width: 100,
        sorter: true,
        sortOrder:
          filters.sort_by === 'peak_qvalue'
            ? filters.sort_order === 'asc'
              ? 'ascend'
              : 'descend'
            : null,
        render: (qvalue: number | string | null) => {
          // Handle string/number type mismatch from backend
          const numQvalue = qvalue === null ? null : (typeof qvalue === 'string' ? parseFloat(qvalue) : qvalue)
          return (
            <Text style={{ color: getQValueColor(numQvalue), fontSize: 12 }}>
              {formatQValue(numQvalue)}
            </Text>
          )
        },
      },

      // Overlap Length
      {
        title: t('table.overlapLength', 'Overlap (bp)'),
        dataIndex: 'overlap_length',
        key: 'overlap_length',
        width: 100,
        sorter: true,
        sortOrder:
          filters.sort_by === 'overlap_length'
            ? filters.sort_order === 'asc'
              ? 'ascend'
              : 'descend'
            : null,
        render: (length: number | string) => {
          // Handle string/number type mismatch from backend
          const numLength = typeof length === 'string' ? parseInt(length, 10) : length
          return <Text>{numLength.toLocaleString()}</Text>
        },
      },
    ],
    [t, filters.sort_by, filters.sort_order]
  )

  // Handle table change (pagination, sorting)
  const handleTableChange = useCallback(
    (
      pagination: TablePaginationConfig,
      _filters: Record<string, FilterValue | null>,
      sorter: SorterResult<OverlapResult> | SorterResult<OverlapResult>[]
    ) => {
      const newFilters: Partial<OverlapFilters> = {}

      // Handle pagination
      const nextPage = typeof pagination.current === 'number' ? pagination.current : undefined
      const nextPageSize = typeof pagination.pageSize === 'number' ? pagination.pageSize : undefined

      if (nextPage !== undefined && nextPage !== page) {
        newFilters.page = nextPage
      }
      if (nextPageSize !== undefined && nextPageSize !== pageSize) {
        newFilters.page_size = nextPageSize
        newFilters.page = 1 // Reset to first page when changing page size
      }

      // Handle sorting
      if (!Array.isArray(sorter) && sorter.columnKey) {
        const sortField = sorter.columnKey as string
        const sortOrder = sorter.order === 'ascend' ? 'asc' : sorter.order === 'descend' ? 'desc' : undefined

        if (sortOrder) {
          newFilters.sort_by = sortField as OverlapFilters['sort_by']
          newFilters.sort_order = sortOrder
        } else {
          // Clear sorting
          newFilters.sort_by = undefined
          newFilters.sort_order = undefined
        }
      }

      // Apply changes
      if (Object.keys(newFilters).length > 0) {
        onFiltersChange(newFilters)
      }
    },
    [page, pageSize, onFiltersChange]
  )

  return (
    <Table<OverlapResult>
      columns={columns}
      dataSource={items}
      rowKey="overlap_id"
      loading={loading}
      pagination={
        paginationEnabled
          ? {
              current: page,
              pageSize: pageSize,
              total: total,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => t('table.total', { total, defaultValue: `Total ${total} overlaps` }),
              pageSizeOptions: ['10', '20', '50', '100', '500', '1000'],
              placement: ['bottomCenter'],
            }
          : false
      }
      onChange={handleTableChange}
      onRow={(record) => ({
        onClick: () => onRowClick?.(record),
        style: onRowClick ? { cursor: 'pointer' } : {}
      })}
      virtual
      scroll={{ x: 1200, y: 520 }}
      size="small"
    />
  )
}

export default OverlapTable
