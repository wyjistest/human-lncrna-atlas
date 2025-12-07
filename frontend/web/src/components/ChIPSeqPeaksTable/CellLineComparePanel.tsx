/**
 * CellLineComparePanel Component
 * Phase 2.6 - Cell line comparison selection panel
 *
 * Allows selection of multiple cell lines to compare for the same histone mark.
 * Displays cell types grouped by category (cancer, normal, stem) with visual indicators.
 */

import { useState, useCallback } from 'react'
import { Card, Checkbox, Button, Space, Alert, Tag, Row, Col, Typography } from 'antd'
import { SwapOutlined, ExperimentOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  CELL_TYPE_CONFIGS,
  CELL_CATEGORY_CONFIGS,
  getCellTypeColor,
  getCellTypesByCategory,
  type CellTypeCategory,
} from '@/config/cellTypeConfigs'
import { getMarkConfig } from '@/config/markConfigs'
import type { MarkType } from '@/types/chipseq'

const { Text } = Typography

interface CellLineComparePanelProps {
  /** Gene ID for context */
  geneId: number
  /** Current mark type to compare across cell lines */
  currentMarkType: MarkType
  /** Callback when compare button is clicked */
  onCompare: (cellTypes: string[]) => void
  /** Optional initially selected cell types */
  initialSelectedCellTypes?: string[]
  /** Loading state */
  loading?: boolean
}

/**
 * CellLineComparePanel Component
 *
 * A panel that allows users to select multiple cell lines for comparing
 * the same histone modification mark across different cell types.
 *
 * @example
 * ```tsx
 * <CellLineComparePanel
 *   geneId={123}
 *   currentMarkType="H3K27me3"
 *   onCompare={(cellTypes) => console.log('Compare:', cellTypes)}
 * />
 * ```
 */
export function CellLineComparePanel({
  geneId: _geneId, // Keep for future use, suppress unused warning
  currentMarkType,
  onCompare,
  initialSelectedCellTypes = [],
  loading = false,
}: CellLineComparePanelProps) {
  const { t, i18n } = useTranslation('genes')
  const [selectedCellTypes, setSelectedCellTypes] = useState<string[]>(initialSelectedCellTypes)

  const markConfig = getMarkConfig(currentMarkType)
  const isZh = i18n.language === 'zh-CN'

  // Get cell types grouped by category
  const cellTypesByCategory: Array<{
    category: CellTypeCategory
    cellTypes: string[]
  }> = [
    { category: 'cancer', cellTypes: getCellTypesByCategory('cancer') },
    { category: 'normal', cellTypes: getCellTypesByCategory('normal') },
    { category: 'stem', cellTypes: getCellTypesByCategory('stem') },
  ]

  // Handle checkbox change
  const handleCheckboxChange = useCallback((cellType: string, checked: boolean) => {
    setSelectedCellTypes((prev) => {
      if (checked) {
        return [...prev, cellType]
      }
      return prev.filter((ct) => ct !== cellType)
    })
  }, [])

  // Handle select all in a category
  const handleSelectCategory = useCallback((category: CellTypeCategory, checked: boolean) => {
    const categoryTypes = getCellTypesByCategory(category)
    setSelectedCellTypes((prev) => {
      if (checked) {
        // Add all cell types from this category
        const newSet = new Set([...prev, ...categoryTypes])
        return Array.from(newSet)
      }
      // Remove all cell types from this category
      return prev.filter((ct) => !categoryTypes.includes(ct))
    })
  }, [])

  // Handle compare button click
  const handleCompare = useCallback(() => {
    if (selectedCellTypes.length >= 2) {
      onCompare(selectedCellTypes)
    }
  }, [selectedCellTypes, onCompare])

  // Check if a category is fully selected
  const isCategoryFullySelected = useCallback(
    (category: CellTypeCategory) => {
      const categoryTypes = getCellTypesByCategory(category)
      return categoryTypes.every((ct) => selectedCellTypes.includes(ct))
    },
    [selectedCellTypes]
  )

  // Check if a category is partially selected
  const isCategoryPartiallySelected = useCallback(
    (category: CellTypeCategory) => {
      const categoryTypes = getCellTypesByCategory(category)
      const selectedCount = categoryTypes.filter((ct) => selectedCellTypes.includes(ct)).length
      return selectedCount > 0 && selectedCount < categoryTypes.length
    },
    [selectedCellTypes]
  )

  return (
    <Card
      size="small"
      title={
        <Space>
          <SwapOutlined />
          <span>{t('detail.chipseq.compareCellLines', 'Compare Cell Lines')}</span>
        </Space>
      }
      extra={
        <Tag color={markConfig.color} style={{ margin: 0 }}>
          {currentMarkType}
        </Tag>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* Info Alert */}
        <Alert
          message={t(
            'detail.chipseq.compareCellLinesHint',
            'Select 2 or more cell lines to compare the same histone mark across different cell types'
          )}
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
        />

        {/* Current Mark Display */}
        <div style={{ padding: '8px 12px', backgroundColor: '#fafafa', borderRadius: 4 }}>
          <Space>
            <Text strong>{t('detail.chipseq.currentMark', 'Current Mark')}:</Text>
            <Tag
              color={markConfig.color}
              icon={<ExperimentOutlined />}
            >
              {currentMarkType}
            </Tag>
            <Text type="secondary">
              ({t(`detail.chipseq.categories.${markConfig.category}`, markConfig.category)})
            </Text>
          </Space>
        </div>

        {/* Cell Type Selection by Category */}
        {cellTypesByCategory.map(({ category, cellTypes }) => {
          if (cellTypes.length === 0) return null
          const categoryConfig = CELL_CATEGORY_CONFIGS[category]

          return (
            <div key={category}>
              <Row align="middle" style={{ marginBottom: 8 }}>
                <Col flex="auto">
                  <Checkbox
                    checked={isCategoryFullySelected(category)}
                    indeterminate={isCategoryPartiallySelected(category)}
                    onChange={(e) => handleSelectCategory(category, e.target.checked)}
                    style={{ fontWeight: 500 }}
                  >
                    <Tag color={categoryConfig.color} style={{ marginLeft: 4 }}>
                      {isZh ? categoryConfig.displayNameZh : categoryConfig.displayName}
                    </Tag>
                  </Checkbox>
                </Col>
              </Row>

              <Row gutter={[8, 8]} style={{ marginLeft: 24 }}>
                {cellTypes.map((cellType) => {
                  const config = CELL_TYPE_CONFIGS[cellType]
                  if (!config) return null

                  return (
                    <Col key={cellType}>
                      <Checkbox
                        checked={selectedCellTypes.includes(cellType)}
                        onChange={(e) => handleCheckboxChange(cellType, e.target.checked)}
                      >
                        <Space size={4}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              backgroundColor: getCellTypeColor(cellType),
                            }}
                          />
                          <span>{isZh ? config.labelZh : config.label}</span>
                        </Space>
                      </Checkbox>
                    </Col>
                  )
                })}
              </Row>
            </div>
          )
        })}

        {/* Compare Button */}
        <Button
          type="primary"
          icon={<SwapOutlined />}
          onClick={handleCompare}
          disabled={selectedCellTypes.length < 2}
          loading={loading}
          block
        >
          {t('detail.chipseq.compareButton', 'Compare')} ({selectedCellTypes.length}{' '}
          {t('detail.chipseq.selectedCellLines', 'selected')})
        </Button>

        {/* Selection Hint */}
        {selectedCellTypes.length < 2 && selectedCellTypes.length > 0 && (
          <Alert
            message={t(
              'detail.chipseq.selectMoreCellLines',
              'Select at least one more cell line to enable comparison'
            )}
            type="warning"
            showIcon
            banner
          />
        )}
      </Space>
    </Card>
  )
}

export default CellLineComparePanel
