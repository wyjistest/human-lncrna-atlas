/**
 * FilterPanel Component
 * Phase 2.2 - Advanced filter panel for ChIP-seq data
 *
 * Provides filtering options for:
 * - Fold enrichment range
 * - Q-value (FDR) threshold
 * - Signal value minimum
 * - Relative position filter
 * - Flanking region size
 */

import { useState, useCallback } from 'react'
import {
  Card,
  Space,
  Select,
  Slider,
  InputNumber,
  Button,
  Row,
  Col,
  Tooltip,
} from 'antd'
import {
  FilterOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getMarkConfig } from '@/config/markConfigs'
import { RELATIVE_POSITIONS } from '@/types/chipseq'
import type { MarkType, ChIPSeqFilters } from '@/types/chipseq'

interface FilterPanelProps {
  /** Current mark type (for default values) */
  markType: MarkType
  /** Current filter values */
  filters: ChIPSeqFilters
  /** Filter change handler */
  onFiltersChange: (filters: ChIPSeqFilters) => void
  /** Reset filters handler */
  onReset: () => void
  /** Collapsed state (for responsive design) */
  collapsed?: boolean
}

/**
 * FilterPanel Component
 *
 * Advanced filtering panel for ChIP-seq peak data.
 * Uses mark-specific default values from configuration.
 *
 * @example
 * ```tsx
 * <FilterPanel
 *   markType="H3K27me3"
 *   filters={currentFilters}
 *   onFiltersChange={handleFiltersChange}
 *   onReset={handleReset}
 * />
 * ```
 */
export function FilterPanel({
  markType,
  filters,
  onFiltersChange,
  onReset,
  collapsed = false,
}: FilterPanelProps) {
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')
  const markConfig = getMarkConfig(markType)

  // Local state for slider values (for smooth dragging)
  const [foldEnrichmentRange, setFoldEnrichmentRange] = useState<[number, number]>([
    filters.min_fold_enrichment ?? 0,
    filters.max_fold_enrichment ?? 100,
  ])

  // Apply fold enrichment filter
  const applyFoldEnrichmentFilter = useCallback(() => {
    onFiltersChange({
      ...filters,
      min_fold_enrichment: foldEnrichmentRange[0] || undefined,
      max_fold_enrichment: foldEnrichmentRange[1] < 100 ? foldEnrichmentRange[1] : undefined,
      page: 1, // Reset to first page
    })
  }, [filters, foldEnrichmentRange, onFiltersChange])

  // Handle q-value change
  const handleQValueChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        ...filters,
        max_qvalue: value || undefined,
        page: 1,
      })
    },
    [filters, onFiltersChange]
  )

  // Handle signal value change
  const handleSignalChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        ...filters,
        min_signal: value || undefined,
        page: 1,
      })
    },
    [filters, onFiltersChange]
  )

  // Handle position filter change
  const handlePositionChange = useCallback(
    (value: string | undefined) => {
      onFiltersChange({
        ...filters,
        relative_position: value,
        page: 1,
      })
    },
    [filters, onFiltersChange]
  )

  // Handle flanking region change
  const handleFlankingChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        ...filters,
        flanking: value || undefined,
        page: 1,
      })
    },
    [filters, onFiltersChange]
  )

  // Handle cell type change
  const handleCellTypeChange = useCallback(
    (value: string | undefined) => {
      onFiltersChange({
        ...filters,
        cell_type: value,
        page: 1,
      })
    },
    [filters, onFiltersChange]
  )

  if (collapsed) {
    return null
  }

  return (
    <Card
      title={
        <Space>
          <FilterOutlined />
          <span>{t('detail.chipseq.filters', 'Filters')}</span>
        </Space>
      }
      size="small"
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={onReset}>
          {tCommon('action.reset', 'Reset')}
        </Button>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Row gutter={[16, 16]} align="middle">
          {/* Q-Value Filter */}
          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.maxQValue', 'Max Q-Value (FDR)')}:
                <Tooltip title={t('detail.chipseq.qvalueTooltip', 'False Discovery Rate threshold')}>
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
                </Tooltip>
              </span>
              <InputNumber
                style={{ width: '100%' }}
                value={filters.max_qvalue}
                onChange={handleQValueChange}
                min={0}
                max={1}
                step={0.01}
                placeholder={String(markConfig.defaultFilters.max_qvalue ?? 0.05)}
              />
            </Space>
          </Col>

          {/* Min Signal Filter */}
          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.minSignal', 'Min Signal Value')}:
              </span>
              <InputNumber
                style={{ width: '100%' }}
                value={filters.min_signal}
                onChange={handleSignalChange}
                min={0}
                step={1}
                placeholder="0"
              />
            </Space>
          </Col>

          {/* Position Filter */}
          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.position', 'Relative Position')}:
              </span>
              <Select
                style={{ width: '100%' }}
                placeholder={tCommon('placeholder.select', 'Select')}
                allowClear
                value={filters.relative_position}
                onChange={handlePositionChange}
                options={RELATIVE_POSITIONS.map((pos) => ({
                  value: pos.value,
                  label: t(`detail.chipseq.positions.${pos.value}`, pos.label),
                }))}
              />
            </Space>
          </Col>

          {/* Flanking Region */}
          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.flanking', 'Flanking Region')}:
                <Tooltip
                  title={t(
                    'detail.chipseq.flankingTooltip',
                    'Distance from gene boundaries to search for peaks'
                  )}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
                </Tooltip>
              </span>
              <Select
                style={{ width: '100%' }}
                value={filters.flanking}
                onChange={handleFlankingChange}
                options={[
                  { value: 5000, label: '5 kb' },
                  { value: 10000, label: '10 kb' },
                  { value: 25000, label: '25 kb' },
                  { value: 50000, label: '50 kb' },
                  { value: 100000, label: '100 kb' },
                ]}
              />
            </Space>
          </Col>
        </Row>

        {/* Second Row: Cell Type Filter */}
        <Row gutter={[16, 16]} align="middle">
          {/* Cell Type Filter */}
          <Col xs={24} sm={12} md={8}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.cellType', 'Cell Type')}:
              </span>
              <Select
                style={{ width: '100%' }}
                placeholder={t('detail.chipseq.allCellTypes', 'All Cell Types')}
                allowClear
                value={filters.cell_type}
                onChange={handleCellTypeChange}
                options={[
                  { value: 'K562', label: 'K562 (白血病细胞)' },
                  { value: 'B-lymphocyte', label: 'GM12878 (B淋巴细胞)' },
                ]}
              />
            </Space>
          </Col>
        </Row>

        {/* Fold Enrichment Slider */}
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={16}>
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('detail.chipseq.foldEnrichment', 'Fold Enrichment')}:{' '}
                {foldEnrichmentRange[0]} - {foldEnrichmentRange[1]}x
                <Tooltip
                  title={t(
                    'detail.chipseq.foldEnrichmentTooltip',
                    'Signal enrichment over background'
                  )}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
                </Tooltip>
              </span>
              <Space style={{ width: '100%' }}>
                <Slider
                  range
                  style={{ width: 300 }}
                  min={0}
                  max={100}
                  step={1}
                  value={foldEnrichmentRange}
                  onChange={(val) => setFoldEnrichmentRange(val as [number, number])}
                  tooltip={{ formatter: (val) => `${val}x` }}
                />
                <Button size="small" type="primary" onClick={applyFoldEnrichmentFilter}>
                  {tCommon('action.apply', 'Apply')}
                </Button>
              </Space>
            </Space>
          </Col>
        </Row>
      </Space>
    </Card>
  )
}

export default FilterPanel
