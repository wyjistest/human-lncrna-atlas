/**
 * OverlapFilterPanel Component
 * Phase 3.0 - Task 1.5
 *
 * Advanced filter panel for lncRNA-ChIP-seq overlap analysis.
 * Provides filtering options for:
 * - Mark type selection (with category grouping)
 * - Cell type selection (multiple)
 * - Chromosome selection
 * - Overlap length threshold
 * - Binding affinity threshold
 * - Peak strength threshold
 * - Q-value (FDR) threshold
 */

import { useState, useCallback, type CSSProperties } from 'react'
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
import type { OverlapFilters } from '@/types/lncRNAChIPSeqOverlap'
import type { MarkType } from '@/types/chipseq'
import { CELL_TYPE_OPTIONS, CHROMOSOME_OPTIONS } from '@/types/lncRNAChIPSeqOverlap'
import { MarkSelector } from '../ChIPSeqPeaksTable/MarkSelector'

interface OverlapFilterPanelProps {
  /** Current filter values */
  filters: OverlapFilters
  /** Filter change handler */
  onFiltersChange: (filters: Partial<OverlapFilters>) => void
  /** Reset filters handler */
  onReset: () => void
  /** Collapsed state (for responsive design) */
  collapsed?: boolean
  /** Highlight specific filter controls (for actionable error guidance) */
  highlightKeys?: string[]
}

/**
 * OverlapFilterPanel Component
 *
 * Advanced filtering panel for lncRNA-ChIP-seq overlap data.
 * Uses mark-specific configurations and supports multiple filters.
 *
 * @example
 * ```tsx
 * <OverlapFilterPanel
 *   filters={currentFilters}
 *   onFiltersChange={handleFiltersChange}
 *   onReset={handleReset}
 * />
 * ```
 */
export function OverlapFilterPanel({
  filters,
  onFiltersChange,
  onReset,
  collapsed = false,
  highlightKeys,
}: OverlapFilterPanelProps) {
  const { t } = useTranslation('overlap')
  const { t: tCommon } = useTranslation('common')

  const highlightSet = new Set(highlightKeys || [])
  const highlightStyle: CSSProperties = {
    boxShadow: '0 0 0 2px #faad14',
    borderRadius: 6,
  }

  // Local state for slider (smooth dragging experience)
  const [overlapLengthRange, setOverlapLengthRange] = useState<number>(
    filters.min_overlap_length ?? 0
  )

  // Apply overlap length filter when user finishes dragging
  const applyOverlapLengthFilter = useCallback(() => {
    onFiltersChange({
      min_overlap_length: overlapLengthRange > 0 ? overlapLengthRange : undefined,
      page: 1, // Reset to first page
    })
  }, [overlapLengthRange, onFiltersChange])

  // Handle mark type change (supports multiple selection)
  const handleMarkTypeChange = useCallback(
    (markType: MarkType | MarkType[]) => {
      // MarkSelector returns MarkType | MarkType[], we convert to comma-separated string
      const markTypeStr = Array.isArray(markType) ? markType.join(',') : markType
      onFiltersChange({
        mark_type: markTypeStr || undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  // Handle cell type change (supports multiple selection)
  const handleCellTypeChange = useCallback(
    (cellTypes: string[]) => {
      onFiltersChange({
        cell_type: cellTypes.length > 0 ? cellTypes.join(',') : undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  // Handle chromosome selection
  const handleChromosomeChange = useCallback(
    (chr: string) => {
      onFiltersChange({
        chromosome: chr || undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  // Handle binding affinity threshold
  const handleBAChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        min_binding_affinity: value || undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  // Handle peak strength threshold
  const handlePeakStrengthChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        min_peak_strength: value || undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  // Handle Q-value threshold
  const handleQValueChange = useCallback(
    (value: number | null) => {
      onFiltersChange({
        max_qvalue: value || undefined,
        page: 1,
      })
    },
    [onFiltersChange]
  )

  if (collapsed) {
    return null
  }

  return (
    <Card
      title={
        <Space>
          <FilterOutlined />
          <span>{t('filters.title', 'Advanced Filters')}</span>
        </Space>
      }
      size="small"
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={onReset}>
          {tCommon('action.reset', 'Reset')}
        </Button>
      }
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        {/* First Row: Mark Type, Cell Type, Chromosome */}
        <Row gutter={[16, 16]} align="middle">
          {/* Mark Type Selector */}
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('filters.markType', 'Mark Type')}:
              </span>
              <div
                data-testid="overlap-filter-mark-type"
                style={{ width: '100%', ...(highlightSet.has('mark_type') ? highlightStyle : {}) }}
              >
                <MarkSelector
                  value={filters.mark_type?.split(',') as MarkType[]}
                  onChange={handleMarkTypeChange}
                  multiple
                  placeholder={t('filters.selectMarks', 'Select histone marks')}
                  allowClear
                />
              </div>
            </Space>
          </Col>

          {/* Cell Type Selector */}
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('filters.cellType', 'Cell Type')}:
              </span>
              <div
                data-testid="overlap-filter-cell-type"
                style={{ width: '100%', ...(highlightSet.has('cell_type') ? highlightStyle : {}) }}
              >
                <Select
                  aria-label={t('filters.cellType', 'Cell Type')}
                  mode="multiple"
                  virtual={false}
                  style={{ width: '100%' }}
                  value={filters.cell_type?.split(',') || []}
                  onChange={handleCellTypeChange}
                  options={Array.from(CELL_TYPE_OPTIONS).map((ct) => ({
                    label: ct,
                    value: ct,
                  }))}
                  placeholder={t('filters.selectCellTypes', 'Select cell types')}
                  allowClear
                  maxTagCount="responsive"
                />
              </div>
            </Space>
          </Col>

          {/* Chromosome Selector */}
          <Col xs={24} sm={12} md={8}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <span style={{ fontWeight: 500 }}>
                {t('filters.chromosome', 'Chromosome')}:
              </span>
              <div
                data-testid="overlap-filter-chromosome"
                style={{ width: '100%', ...(highlightSet.has('chromosome') ? highlightStyle : {}) }}
              >
                <Select
                  aria-label={t('filters.chromosome', 'Chromosome')}
                  virtual={false}
                  style={{ width: '100%' }}
                  value={filters.chromosome}
                  onChange={handleChromosomeChange}
                  options={Array.from(CHROMOSOME_OPTIONS).map((chr) => ({
                    label: chr,
                    value: chr,
                  }))}
                  placeholder={t('filters.selectChromosome', 'All chromosomes')}
                  allowClear
                  showSearch
                />
              </div>
            </Space>
          </Col>
        </Row>

        {/* Second Row: Numeric Filters */}
        <Row gutter={[16, 16]} align="middle">
	          {/* Min Binding Affinity */}
	          <Col xs={24} sm={12} md={6}>
	            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
	              <span style={{ fontWeight: 500 }}>
	                {t('filters.minBindingAffinity', 'Min Binding Affinity')}:
                <Tooltip
                  title={t(
                    'filters.bindingAffinityTooltip',
                    'Minimum lncRNA-target binding affinity score'
                  )}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
	                </Tooltip>
	              </span>
	              <div
	                data-testid="overlap-filter-min-binding-affinity"
	                style={{ width: '100%', ...(highlightSet.has('min_binding_affinity') ? highlightStyle : {}) }}
	              >
	                <InputNumber
	                  aria-label={t('filters.minBindingAffinity', 'Min Binding Affinity')}
	                  style={{ width: '100%' }}
	                  value={filters.min_binding_affinity}
	                  onChange={handleBAChange}
	                  min={0}
	                  max={100}
	                  step={5}
	                  placeholder="0"
	                />
	              </div>
	            </Space>
	          </Col>

	          {/* Min Peak Strength */}
	          <Col xs={24} sm={12} md={6}>
	            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
	              <span style={{ fontWeight: 500 }}>
	                {t('filters.minPeakStrength', 'Min Peak Strength')}:
                <Tooltip
                  title={t(
                    'filters.peakStrengthTooltip',
                    'Minimum ChIP-seq peak fold enrichment'
                  )}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
	                </Tooltip>
	              </span>
	              <div
	                data-testid="overlap-filter-min-peak-strength"
	                style={{ width: '100%', ...(highlightSet.has('min_peak_strength') ? highlightStyle : {}) }}
	              >
	                <InputNumber
	                  aria-label={t('filters.minPeakStrength', 'Min Peak Strength')}
	                  style={{ width: '100%' }}
	                  value={filters.min_peak_strength}
	                  onChange={handlePeakStrengthChange}
	                  min={0}
	                  max={100}
	                  step={1}
	                  placeholder="0"
	                />
	              </div>
	            </Space>
	          </Col>

	          {/* Max Q-value */}
	          <Col xs={24} sm={12} md={6}>
	            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
	              <span style={{ fontWeight: 500 }}>
	                {t('filters.maxQValue', 'Max Q-value (FDR)')}:
                <Tooltip
                  title={t('filters.qvalueTooltip', 'Maximum False Discovery Rate for peaks')}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
	                </Tooltip>
	              </span>
	              <div
	                data-testid="overlap-filter-max-qvalue"
	                style={{ width: '100%', ...(highlightSet.has('max_qvalue') ? highlightStyle : {}) }}
	              >
	                <InputNumber
	                  aria-label={t('filters.maxQValue', 'Max Q-value (FDR)')}
	                  style={{ width: '100%' }}
	                  value={filters.max_qvalue}
	                  onChange={handleQValueChange}
	                  min={0}
	                  max={1}
	                  step={0.01}
	                  placeholder="0.05"
	                />
	              </div>
	            </Space>
	          </Col>
        </Row>

        {/* Third Row: Overlap Length Slider */}
        <Row gutter={[16, 16]} align="middle">
	          <Col xs={24} md={16}>
	            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
	              <span style={{ fontWeight: 500 }}>
	                {t('filters.minOverlapLength', 'Min Overlap Length')}: {overlapLengthRange} bp
                <Tooltip
                  title={t(
                    'filters.overlapLengthTooltip',
                    'Minimum overlap between binding site and peak in base pairs'
                  )}
                >
                  <InfoCircleOutlined style={{ marginLeft: 4 }} />
	                </Tooltip>
	              </span>
	              <div
	                data-testid="overlap-filter-min-overlap-length"
	                style={{ width: '100%', ...(highlightSet.has('min_overlap_length') ? highlightStyle : {}) }}
	              >
	                <Space style={{ width: '100%' }} align="center">
	                  <Slider
	                    style={{ width: 300 }}
	                    ariaLabelForHandle={t('filters.minOverlapLength', 'Min Overlap Length')}
	                    min={0}
	                    max={10000}
	                    step={100}
	                    value={overlapLengthRange}
	                    onChange={setOverlapLengthRange}
	                    onChangeComplete={applyOverlapLengthFilter}
	                    tooltip={{ formatter: (val) => `${val} bp` }}
	                  />
	                  <InputNumber
	                    aria-label={t('filters.minOverlapLength', 'Min Overlap Length')}
	                    style={{ width: 100 }}
	                    value={overlapLengthRange}
	                    onChange={(v) => v !== null && setOverlapLengthRange(v)}
	                    onPressEnter={applyOverlapLengthFilter}
	                    min={0}
	                    max={10000}
	                    step={100}
	                    suffix="bp"
	                  />
	                  <Button size="small" type="primary" onClick={applyOverlapLengthFilter}>
	                    {tCommon('action.apply', 'Apply')}
	                  </Button>
	                </Space>
	              </div>
	            </Space>
	          </Col>
	        </Row>
      </Space>
    </Card>
  )
}

export default OverlapFilterPanel
