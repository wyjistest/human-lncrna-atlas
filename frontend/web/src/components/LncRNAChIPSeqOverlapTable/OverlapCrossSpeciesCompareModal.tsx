import { Alert, Checkbox, Modal, Select, Space, Spin, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import type { OverlapCrossSpeciesComparisonResponse } from '@/types/lncRNAChIPSeqOverlap'

const { Text } = Typography

interface SpeciesRow {
  species_id: number
  species_name: string
  lncrna_gene_id: number | null
  target_gene_id: number | null
  statistics: OverlapCrossSpeciesComparisonResponse['species_stats'][number]['statistics']
}

interface OverlapCrossSpeciesCompareModalProps {
  open: boolean
  onClose: () => void
  data?: OverlapCrossSpeciesComparisonResponse
  loading: boolean
  error?: Error | null
  topN: number
  onTopNChange: (next: number) => void
  speciesIds: number[]
  onSpeciesIdsChange: (next: number[]) => void
}

function formatTopMarks(row: SpeciesRow, limit: number) {
  const items = row.statistics.by_mark_type?.slice(0, limit) || []
  if (items.length === 0) return '-'
  return items.map((x) => `${x.mark_type} (${x.count.toLocaleString()})`).join(', ')
}

function formatTopCells(row: SpeciesRow, limit: number) {
  const items = row.statistics.by_cell_type?.slice(0, limit) || []
  if (items.length === 0) return '-'
  return items.map((x) => `${x.cell_type} (${x.count.toLocaleString()})`).join(', ')
}

export function OverlapCrossSpeciesCompareModal(props: OverlapCrossSpeciesCompareModalProps) {
  const { t } = useTranslation('overlap')

  const speciesOptions = useMemo(
    () => [
      { label: props.data?.species_names?.['1'] ?? 'Human', value: 1 },
      { label: props.data?.species_names?.['2'] ?? 'Chimpanzee', value: 2 },
      { label: props.data?.species_names?.['3'] ?? 'Rhesus Macaque', value: 3 },
      { label: props.data?.species_names?.['4'] ?? 'Marmoset', value: 4 },
    ],
    [props.data?.species_names]
  )

  const rows = useMemo(() => {
    const stats = props.data?.species_stats
    if (!stats) return []
    return Object.values(stats)
      .map((s) => ({
        species_id: s.species_id,
        species_name: s.species_name,
        lncrna_gene_id: s.lncrna_gene_id ?? null,
        target_gene_id: s.target_gene_id ?? null,
        statistics: s.statistics,
      }))
      .sort((a, b) => a.species_id - b.species_id)
  }, [props.data?.species_stats])

  const columns: ColumnsType<SpeciesRow> = useMemo(
    () => [
      {
        title: t('compare.columns.species', 'Species'),
        dataIndex: 'species_name',
        key: 'species',
        render: (_value, row) => (
          <Space size={6}>
            <Text>{row.species_name}</Text>
            <Text type="secondary">({row.species_id})</Text>
          </Space>
        ),
      },
      {
        title: t('compare.columns.overlaps', 'Overlaps'),
        key: 'total_overlaps',
        align: 'right',
        render: (_value, row) => row.statistics.total_overlaps.toLocaleString(),
      },
      {
        title: t('compare.columns.uniqueTargets', 'Unique Targets'),
        key: 'unique_target_genes',
        align: 'right',
        render: (_value, row) => row.statistics.unique_target_genes.toLocaleString(),
      },
      {
        title: t('compare.columns.uniqueMarks', 'Unique Marks'),
        key: 'unique_marks',
        align: 'right',
        render: (_value, row) => row.statistics.unique_marks.toLocaleString(),
      },
      {
        title: t('compare.columns.topMarks', 'Top Marks'),
        key: 'top_marks',
        render: (_value, row) => formatTopMarks(row, 3),
      },
      {
        title: t('compare.columns.topCells', 'Top Cell Types'),
        key: 'top_cells',
        render: (_value, row) => formatTopCells(row, 3),
      },
    ],
    [t]
  )

  return (
    <Modal
      open={props.open}
      onCancel={props.onClose}
      footer={null}
      width={980}
      title={t('compare.title', 'Cross-species Overlap Comparison')}
      destroyOnHidden
    >
      <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
        <Space wrap>
          <Text>{t('compare.topN', 'Top N')}:</Text>
          <Select
            value={props.topN}
            style={{ width: 120 }}
            onChange={(value) => props.onTopNChange(value)}
            options={[5, 10, 20, 50].map((value) => ({ value, label: String(value) }))}
          />
          <Text type="secondary">{t('compare.topNHint', 'Used for breakdown queries per species')}</Text>
        </Space>

        <Space wrap>
          <Text>{t('compare.columns.species', 'Species')}:</Text>
          <Checkbox.Group
            options={speciesOptions}
            value={props.speciesIds}
            onChange={(values) => {
              const next = values as number[]
              if (next.length === 0) return
              props.onSpeciesIdsChange(next)
            }}
          />
        </Space>

        {props.error && (
          <Alert
            type="error"
            showIcon
            message={t('compare.error', 'Failed to load cross-species comparison')}
            description={props.error.message}
          />
        )}

        {props.loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0' }}>
            <Spin />
          </div>
        )}

        {!props.loading && !props.error && props.data && (
          <Table
            data-testid="overlap-compare-species-table"
            rowKey={(row) => String(row.species_id)}
            size="small"
            pagination={false}
            columns={columns}
            dataSource={rows}
          />
        )}
      </Space>
    </Modal>
  )
}
