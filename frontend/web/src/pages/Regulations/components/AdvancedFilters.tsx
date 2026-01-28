/**
 * Regulations 高级筛选器（AntD 6 Collapse items API）
 *
 * 后端 API 支持的全部参数：
 * - min_ba / max_ba: BA 范围筛选
 * - species_id / species_ids: 物种筛选（支持多选）
 * - chromosome / chromosomes: 染色体筛选（支持多选）
 * - lncrna_gene_name: lncRNA 基因名模糊搜索
 * - target_gene_name: 靶基因名模糊搜索
 */

import { useState, useEffect, useRef } from 'react'
import { Form, Select, InputNumber, Collapse, Button, Space, Input, Row, Col } from 'antd'
import { FilterOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useBARange } from '@/hooks/useDetailedStats'
import { SPECIES_OPTIONS, CHROMOSOME_OPTIONS, BA_CONFIG } from '@/config/constants'

// 防抖延迟（毫秒）
const DEBOUNCE_DELAY = 500

// 内部筛选器状态类型（支持数组）
export interface FilterState {
  min_ba?: number
  max_ba?: number
  species_ids?: number[]
  chromosomes?: string[]
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

  // 物种选项本地化
  const localizedSpeciesOptions = SPECIES_OPTIONS.map(opt => ({
    ...opt,
    label: i18n.language?.startsWith('en')
      ? ['Human', 'Chimpanzee', 'Macaque', 'Marmoset'][opt.value - 1]
      : opt.label
  }))

  // 本地输入状态（用于防抖）
  const [lncrnaInput, setLncrnaInput] = useState(filters.lncrna_gene_name || '')
  const [targetInput, setTargetInput] = useState(filters.target_gene_name || '')
  const lncrnaTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const targetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 同步外部 filters 到本地状态（重置时）
  useEffect(() => {
    setLncrnaInput(filters.lncrna_gene_name || '')
    setTargetInput(filters.target_gene_name || '')
  }, [filters.lncrna_gene_name, filters.target_gene_name])

  // lncRNA 基因名防抖处理
  const handleLncrnaChange = (value: string) => {
    setLncrnaInput(value)
    if (lncrnaTimerRef.current) {
      clearTimeout(lncrnaTimerRef.current)
    }
    lncrnaTimerRef.current = setTimeout(() => {
      onFilterChange('lncrna_gene_name', value || undefined)
    }, DEBOUNCE_DELAY)
  }

  // 靶基因名防抖处理
  const handleTargetChange = (value: string) => {
    setTargetInput(value)
    if (targetTimerRef.current) {
      clearTimeout(targetTimerRef.current)
    }
    targetTimerRef.current = setTimeout(() => {
      onFilterChange('target_gene_name', value || undefined)
    }, DEBOUNCE_DELAY)
  }

  // 清理定时器
  useEffect(() => {
    return () => {
      if (lncrnaTimerRef.current) clearTimeout(lncrnaTimerRef.current)
      if (targetTimerRef.current) clearTimeout(targetTimerRef.current)
    }
  }, [])

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

                {/* lncRNA 基因名搜索（500ms 防抖） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.lncrnaName')} style={{ marginBottom: 12 }}>
                    <Input
                      aria-label={t('filters.lncrnaName')}
                      placeholder={i18n.language?.startsWith('en') ? 'e.g. CATG' : '模糊搜索，如: CATG'}
                      prefix={<SearchOutlined style={{ color: '#999' }} />}
                      value={lncrnaInput}
                      onChange={(e) => handleLncrnaChange(e.target.value)}
                      allowClear
                      onClear={() => handleLncrnaChange('')}
                    />
                  </Form.Item>
                </Col>

                {/* 靶基因名搜索（500ms 防抖） */}
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label={t('filters.targetName')} style={{ marginBottom: 12 }}>
                    <Input
                      aria-label={t('filters.targetName')}
                      placeholder={i18n.language?.startsWith('en') ? 'e.g. BRCA' : '模糊搜索，如: BRCA'}
                      prefix={<SearchOutlined style={{ color: '#999' }} />}
                      value={targetInput}
                      onChange={(e) => handleTargetChange(e.target.value)}
                      allowClear
                      onClear={() => handleTargetChange('')}
                    />
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
