import { Collapse, Space, Slider, Radio, Select, Button, Tag } from 'antd'
import { FilterOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

interface AdvancedFiltersProps {
  minBA: number
  setMinBA: (value: number) => void
  nodeTypeFilter: string
  setNodeTypeFilter: (value: string) => void
  minDegree: number
  setMinDegree: (value: number) => void
  currentLayout: string
  onLayoutChange: (layout: string) => void
}

/**
 * Advanced filters component for network visualization
 * Includes BA threshold, node type filter, degree filter, and layout selector
 */
export const AdvancedFilters = ({
  minBA,
  setMinBA,
  nodeTypeFilter,
  setNodeTypeFilter,
  minDegree,
  setMinDegree,
  currentLayout,
  onLayoutChange
}: AdvancedFiltersProps) => {
  const { t } = useTranslation('network')

  const handleReset = () => {
    setMinBA(0)
    setNodeTypeFilter('all')
    setMinDegree(0)
    onLayoutChange('concentric')
  }

  const hasActiveFilters = minBA > 0 || nodeTypeFilter !== 'all' || minDegree > 0

  return (
    <Collapse
      size="small"
      style={{ marginBottom: 8 }}
      items={[
        {
          key: 'filters',
          label: (
            <span style={{ fontSize: 12 }}>
              <FilterOutlined /> {t('filters.title')}
              {hasActiveFilters && (
                <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>{t('filters.enabled')}</Tag>
              )}
            </span>
          ),
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  {t('filters.baThreshold')}: {minBA}
                </div>
                <Slider
                  min={0}
                  max={100}
                  value={minBA}
                  onChange={setMinBA}
                  marks={{ 0: '0', 50: '50', 100: '100' }}
                  tooltip={{ formatter: (value) => t('filters.baTooltip', { value }) }}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>{t('filters.nodeType')}:</div>
                <Radio.Group
                  value={nodeTypeFilter}
                  onChange={(e) => setNodeTypeFilter(e.target.value)}
                  size="small"
                >
                  <Radio.Button value="all">{t('filters.all')}</Radio.Button>
                  <Radio.Button value="lncRNA">lncRNA</Radio.Button>
                  <Radio.Button value="protein_coding">{t('filters.targetGene')}</Radio.Button>
                </Radio.Group>
              </div>
              <div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  {t('filters.minDegree')}: {minDegree}
                </div>
                <Slider
                  min={0}
                  max={10}
                  value={minDegree}
                  onChange={setMinDegree}
                  marks={{ 0: '0', 5: '5', 10: '10' }}
                  tooltip={{ formatter: (value) => t('filters.degreeTooltip', { value }) }}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>{t('filters.layout')}:</div>
                <Select
                  value={currentLayout}
                  onChange={onLayoutChange}
                  size="small"
                  style={{ width: '100%' }}
                  options={[
                    { label: t('layouts.concentric'), value: 'concentric' },
                    { label: t('layouts.cose'), value: 'cose' },
                    { label: t('layouts.circle'), value: 'circle' },
                    { label: t('layouts.grid'), value: 'grid' },
                    { label: t('layouts.breadthfirst'), value: 'breadthfirst' },
                    { label: t('layouts.random'), value: 'random' }
                  ]}
                />
              </div>
              <Button
                size="small"
                onClick={handleReset}
              >
                {t('filters.resetAll')}
              </Button>
            </Space>
          )
        }
      ]}
    />
  )
}
