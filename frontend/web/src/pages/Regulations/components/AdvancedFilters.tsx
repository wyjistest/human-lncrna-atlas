/**
 * Regulations 高级筛选器（AntD 6 Collapse items API）
 *
 * 后端 API 支持的全部参数：
 * - min_ba / max_ba: BA 范围筛选
 * - species_id / species_ids: 物种筛选（支持多选）
 * - chromosome / chromosomes: 染色体筛选（支持多选）
 * - lncrna_gene_id / target_gene_id: 基因 ID 精确筛选（选择器主路径）
 * - lncrna_gene_name / target_gene_name: 基因名模糊搜索（兼容历史 URL；UI 不再提供编辑入口）
 */

import { useMemo, useState } from 'react'
import { Form, Select, InputNumber, Collapse, Button, Space, Row, Col } from 'antd'
import { FilterOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useBARange } from '@/hooks/useDetailedStats'
import { useRegulationLncRNAOptions, useRegulationTargetOptions } from '@/hooks/useRegulations'
import { SPECIES_OPTIONS, CHROMOSOME_OPTIONS, BA_CONFIG } from '@/config/constants'

// 内部筛选器状态类型（支持数组）
export interface FilterState {
  min_ba?: number
  max_ba?: number
  species_ids?: number[]
  chromosomes?: string[]
  lncrna_gene_id?: number
  target_gene_id?: number
  lncrna_gene_name?: string
  target_gene_name?: string
}

interface AdvancedFiltersProps {
  filters: FilterState
  onFilterChange: (key: keyof FilterState, value: unknown) => void
  onReset: () => void
}

export function AdvancedFilters({ filters, onFilterChange, onReset }: AdvancedFiltersProps) {
  const { t, i18n } = useTranslation('regulations')
  const { data: baRange, isLoading: baRangeLoading } = useBARange()
  const [filtersOpen, setFiltersOpen] = useState(false)

  // 物种选项本地化
  const localizedSpeciesOptions = SPECIES_OPTIONS.map(opt => ({
    ...opt,
    label: i18n.language?.startsWith('en')
      ? ['Human', 'Chimpanzee', 'Macaque', 'Marmoset'][opt.value - 1]
      : opt.label
  }))

  // 选择器 options：默认仅在展开筛选面板时加载，避免首屏额外请求。
  // 若仅选择了单个物种，则按 species_id 过滤 options，降低响应体积。
  const selectedSpeciesId = filters.species_ids?.length === 1 ? filters.species_ids[0] : undefined
  const optionsParams = useMemo(
    () => (selectedSpeciesId ? { species_id: selectedSpeciesId } : undefined),
    [selectedSpeciesId]
  )

  const { data: lncrnaOptions, isLoading: lncrnaOptionsLoading } = useRegulationLncRNAOptions(
    optionsParams,
    { enabled: filtersOpen }
  )
  const { data: targetOptions, isLoading: targetOptionsLoading } = useRegulationTargetOptions(
    optionsParams,
    { enabled: filtersOpen }
  )

  const lncrnaSelectOptions = useMemo(() => (
    (lncrnaOptions?.lncrnas ?? []).map((lnc) => ({
      value: lnc.gene_id,
      label: `${lnc.gene_name || lnc.gene_ensembl_id} · ${lnc.species_name} · ${lnc.regulation_count} targets`,
    }))
  ), [lncrnaOptions])

  const targetSelectOptions = useMemo(() => (
    (targetOptions?.targets ?? []).map((gene) => ({
      value: gene.gene_id,
      label: `${gene.gene_name || gene.gene_ensembl_id} · ${gene.species_name} · ${gene.lncrna_count} lncRNAs`,
    }))
  ), [targetOptions])

  const setLncrnaGeneId = (value: number | null) => {
    // 避免与 legacy name 参数同时存在导致 AND 过滤为空
    onFilterChange('lncrna_gene_name', undefined)
    onFilterChange('lncrna_gene_id', value ?? undefined)
  }

  const setTargetGeneId = (value: number | null) => {
    onFilterChange('target_gene_name', undefined)
    onFilterChange('target_gene_id', value ?? undefined)
  }

  // BA 范围变更处理：自动交换确保 min <= max
  const handleMinBAChange = (val: number | null) => {
    const newMin = val ?? undefined
    // 如果新 min > 当前 max，自动交换
    if (newMin !== undefined && filters.max_ba !== undefined && newMin > filters.max_ba) {
      onFilterChange('min_ba', filters.max_ba)
      onFilterChange('max_ba', newMin)
    } else {
      onFilterChange('min_ba', newMin)
    }
  }

  const handleMaxBAChange = (val: number | null) => {
    const newMax = val ?? undefined
    // 如果新 max < 当前 min，自动交换
    if (newMax !== undefined && filters.min_ba !== undefined && newMax < filters.min_ba) {
      onFilterChange('max_ba', filters.min_ba)
      onFilterChange('min_ba', newMax)
    } else {
      onFilterChange('max_ba', newMax)
    }
  }

  return (
    <Collapse
      size="small"
      style={{ marginBottom: 16 }}
      onChange={(activeKey) => {
        const keys = Array.isArray(activeKey) ? activeKey : [activeKey]
        setFiltersOpen(keys.includes('filters'))
      }}
      items={[
        {
          key: 'filters',
          label: (
            <Space>
              <FilterOutlined />
              <span>{i18n.language?.startsWith('en') ? 'Advanced Filters' : '高级筛选'}</span>
            </Space>
          ),
          children: (
            <Form layout="vertical">
              <Row gutter={16}>
                {/* 物种筛选（多选） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.species')} style={{ marginBottom: 12 }}>
                    <Select
                      aria-label={t('filters.species')}
                      mode="multiple"
                      placeholder={i18n.language?.startsWith('en') ? 'Select species' : '选择物种（可多选）'}
                      value={filters.species_ids}
                      onChange={(val) => onFilterChange('species_ids', val.length ? val : undefined)}
                      options={localizedSpeciesOptions}
                      style={{ width: '100%' }}
                      allowClear
                    />
                  </Form.Item>
                </Col>

                {/* 染色体筛选（多选） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.chromosome')} style={{ marginBottom: 12 }}>
                    <Select
                      aria-label={t('filters.chromosome')}
                      mode="multiple"
                      placeholder={i18n.language?.startsWith('en') ? 'Select chromosomes' : '选择染色体（可多选）'}
                      value={filters.chromosomes}
                      onChange={(val) => onFilterChange('chromosomes', val.length ? val : undefined)}
                      options={CHROMOSOME_OPTIONS}
                      style={{ width: '100%' }}
                      allowClear
                      maxTagCount={3}
                    />
                  </Form.Item>
                </Col>

                {/* BA 范围（自动交换确保 min <= max） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item
                    label={`${t('filters.baRange')}${baRange ? ` (${baRange.min_ba.toFixed(0)} - ${baRange.max_ba.toFixed(0)})` : ''}`}
                    style={{ marginBottom: 12 }}
                  >
                    <Space.Compact style={{ width: '100%' }}>
                      <InputNumber
                        aria-label={i18n.language?.startsWith('en') ? 'Min BA' : '最小BA'}
                        placeholder={baRangeLoading ? '...' : `最小: ${baRange?.min_ba?.toFixed(0) || BA_CONFIG.MIN}`}
                        min={baRange?.min_ba ?? BA_CONFIG.MIN}
                        max={baRange?.max_ba ?? BA_CONFIG.MAX}
                        step={BA_CONFIG.STEP}
                        value={filters.min_ba}
                        onChange={handleMinBAChange}
                        style={{ width: '50%' }}
                      />
                      <InputNumber
                        aria-label={i18n.language?.startsWith('en') ? 'Max BA' : '最大BA'}
                        placeholder={baRangeLoading ? '...' : `最大: ${baRange?.max_ba?.toFixed(0) || BA_CONFIG.MAX}`}
                        min={baRange?.min_ba ?? BA_CONFIG.MIN}
                        max={baRange?.max_ba ?? BA_CONFIG.MAX}
                        step={BA_CONFIG.STEP}
                        value={filters.max_ba}
                        onChange={handleMaxBAChange}
                        style={{ width: '50%' }}
                      />
                    </Space.Compact>
                  </Form.Item>
                </Col>

                {/* lncRNA 选择器（gene_id 主路径；仅在展开时加载 options） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.lncrnaName')} style={{ marginBottom: 12 }}>
                    <div data-testid="regulations-lncrna-selector">
                      <Select
                        aria-label={t('filters.lncrnaName')}
                        placeholder={t('filters.lncrnaPlaceholder')}
                        value={filters.lncrna_gene_id ?? null}
                        onChange={(val) => setLncrnaGeneId(val ?? null)}
                        options={lncrnaSelectOptions}
                        loading={lncrnaOptionsLoading}
                        style={{ width: '100%' }}
                        showSearch
                        allowClear
                        virtual
                        optionFilterProp="label"
                        suffixIcon={<SearchOutlined />}
                      />
                    </div>
                  </Form.Item>
                </Col>

                {/* 靶基因选择器（gene_id 主路径；仅在展开时加载 options） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.targetName')} style={{ marginBottom: 12 }}>
                    <div data-testid="regulations-target-selector">
                      <Select
                        aria-label={t('filters.targetName')}
                        placeholder={t('filters.targetPlaceholder')}
                        value={filters.target_gene_id ?? null}
                        onChange={(val) => setTargetGeneId(val ?? null)}
                        options={targetSelectOptions}
                        loading={targetOptionsLoading}
                        style={{ width: '100%' }}
                        showSearch
                        allowClear
                        virtual
                        optionFilterProp="label"
                        suffixIcon={<SearchOutlined />}
                      />
                    </div>
                  </Form.Item>
                </Col>

                {/* 操作按钮 */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label=" " style={{ marginBottom: 12 }}>
                    <Button icon={<ReloadOutlined />} onClick={onReset}>
                      {t('filters.reset')}
                    </Button>
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          )
        }
      ]}
    />
  )
}
