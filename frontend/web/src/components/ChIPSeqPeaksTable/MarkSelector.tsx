/**
 * MarkSelector Component
 * Phase 2.2 - Dropdown selector for histone modification marks
 *
 * Features:
 * - Single or multi-select mode
 * - Grouped by category (repressive, activating, etc.)
 * - Search filtering
 * - Color-coded options
 * - Show/hide based on available marks from API
 */

import { useMemo, useCallback } from 'react'
import { Select, Tag, Space, Tooltip, Badge } from 'antd'
import {
  StopOutlined,
  CheckCircleOutlined,
  StarOutlined,
  ArrowRightOutlined,
  TagOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  MARK_CONFIGS,
  CATEGORY_CONFIGS,
  getMarksGroupedByCategory,
  getCommonMarks,
} from '@/config/markConfigs'
import type { MarkType, MarkCategory } from '@/types/chipseq'

import type { DefaultOptionType } from 'antd/es/select'

interface MarkSelectorProps {
  /** Currently selected mark(s) */
  value?: MarkType | MarkType[]
  /** Change handler */
  onChange?: (value: MarkType | MarkType[]) => void
  /** Allow multiple selection */
  multiple?: boolean
  /** Available marks from API (optional - if not provided, shows all) */
  availableMarks?: MarkType[]
  /** Show only common marks initially */
  showOnlyCommon?: boolean
  /** Placeholder text */
  placeholder?: string
  /** Disable the selector */
  disabled?: boolean
  /** Allow clear selection */
  allowClear?: boolean
  /** Custom style */
  style?: React.CSSProperties
  /** Size of the select */
  size?: 'small' | 'middle' | 'large'
  /** Maximum number of selections (for multi-select) */
  maxCount?: number
  /** Show peak counts from API data */
  markCounts?: Record<MarkType, number>
  /** Callback when user hovers over an option (for prefetch) */
  onOptionHover?: (markType: MarkType) => void
}

/**
 * Get icon component for a category
 */
function getCategoryIcon(category: MarkCategory) {
  const iconMap: Record<MarkCategory, React.ReactNode> = {
    repressive: <StopOutlined />,
    activating: <CheckCircleOutlined />,
    enhancer: <StarOutlined />,
    elongation: <ArrowRightOutlined />,
    other: <TagOutlined />,
  }
  return iconMap[category]
}

/**
 * Custom tag render for multi-select mode
 */
function tagRender(props: {
  label: React.ReactNode
  value: MarkType
  closable: boolean
  onClose: () => void
}) {
  const { label, value, closable, onClose } = props
  const config = MARK_CONFIGS[value]

  return (
    <Tag
      color={config?.color}
      closable={closable}
      onClose={onClose}
      style={{ marginRight: 3 }}
    >
      {config?.shortName || label}
    </Tag>
  )
}

/**
 * MarkSelector Component
 *
 * A dropdown selector for ChIP-seq histone modification marks.
 * Supports single and multi-select modes with category grouping.
 *
 * @example Single select
 * ```tsx
 * <MarkSelector
 *   value={selectedMark}
 *   onChange={setSelectedMark}
 * />
 * ```
 *
 * @example Multi-select
 * ```tsx
 * <MarkSelector
 *   value={selectedMarks}
 *   onChange={setSelectedMarks}
 *   multiple
 *   maxCount={5}
 * />
 * ```
 */
export function MarkSelector({
  value,
  onChange,
  multiple = false,
  availableMarks,
  showOnlyCommon = false,
  placeholder,
  disabled = false,
  allowClear = true,
  style,
  size = 'middle',
  maxCount,
  markCounts,
  onOptionHover,
}: MarkSelectorProps) {
  const { t } = useTranslation('genes')

  // Build options grouped by category
  const options = useMemo(() => {
    const groupedMarks = getMarksGroupedByCategory()
    const commonMarks = showOnlyCommon ? getCommonMarks() : null

    return groupedMarks.map((group) => {
      const categoryConfig = CATEGORY_CONFIGS[group.category]

      // Filter marks based on availability and common setting
      const filteredMarks = group.marks.filter((mark) => {
        // Check if mark is available from API
        if (availableMarks && !availableMarks.includes(mark.value)) {
          return false
        }
        // Check if showing only common marks
        if (commonMarks && !commonMarks.includes(mark.value)) {
          return false
        }
        return true
      })

      // Skip empty categories
      if (filteredMarks.length === 0) {
        return null
      }

      return {
        label: (
          <Space>
            {getCategoryIcon(group.category)}
            <span style={{ fontWeight: 500 }}>{categoryConfig.displayName}</span>
          </Space>
        ),
        options: filteredMarks.map((mark) => {
          const config = MARK_CONFIGS[mark.value]
          const count = markCounts?.[mark.value]

          return {
            value: mark.value,
            label: (
              <Space
                style={{ width: '100%', justifyContent: 'space-between' }}
                onMouseEnter={() => onOptionHover?.(mark.value)}
              >
                <Space>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 12,
                      height: 12,
                      borderRadius: 2,
                      backgroundColor: config.color,
                    }}
                  />
                  <span>{config.displayName}</span>
                </Space>
                {count !== undefined && (
                  <Badge
                    count={count}
                    style={{ backgroundColor: '#f0f0f0', color: '#666' }}
                    overflowCount={9999}
                  />
                )}
              </Space>
            ),
            // Store raw value for search filtering
            searchValue: `${mark.value} ${config.displayName} ${config.description}`,
            config,
          }
        }),
      }
    }).filter(Boolean) as DefaultOptionType[]
  }, [availableMarks, showOnlyCommon, markCounts, onOptionHover])

  // Handle change
  const handleChange = useCallback(
    (selected: MarkType | MarkType[]) => {
      onChange?.(selected)
    },
    [onChange]
  )

  // Filter function for search
  const filterOption = useCallback(
    (input: string, option: DefaultOptionType | undefined) => {
      if (!option) return false
      const searchValue = (option as any).searchValue as string | undefined
      if (!searchValue) return true
      return searchValue.toLowerCase().includes(input.toLowerCase())
    },
    []
  )

  // Default placeholder based on mode
  const defaultPlaceholder = multiple
    ? t('detail.chipseq.selectMarks', 'Select marks to compare')
    : t('detail.chipseq.selectMark', 'Select a histone mark')

  return (
    <Select
      mode={multiple ? 'multiple' : undefined}
      value={value}
      onChange={handleChange}
      options={options}
      placeholder={placeholder || defaultPlaceholder}
      disabled={disabled}
      allowClear={allowClear}
      style={{ minWidth: 200, ...style }}
      size={size}
      showSearch
      filterOption={filterOption}
      tagRender={multiple ? tagRender : undefined}
      maxCount={multiple ? maxCount : undefined}
      optionFilterProp="searchValue"
      popupMatchSelectWidth={false}
      dropdownStyle={{ minWidth: 320 }}
      listHeight={400}
    />
  )
}

/**
 * Compact mark selector for toolbar usage
 * Shows only the mark abbreviation with color
 */
export function CompactMarkSelector({
  value,
  onChange,
  availableMarks,
  disabled,
}: {
  value?: MarkType
  onChange?: (value: MarkType) => void
  availableMarks?: MarkType[]
  disabled?: boolean
}) {
  const options = useMemo(() => {
    const marks = availableMarks || (Object.keys(MARK_CONFIGS) as MarkType[])
    return marks.map((mark) => {
      const config = MARK_CONFIGS[mark]
      return {
        value: mark,
        label: (
          <Tooltip title={config.description}>
            <Tag color={config.color} style={{ margin: 0 }}>
              {config.shortName}
            </Tag>
          </Tooltip>
        ),
      }
    })
  }, [availableMarks])

  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      disabled={disabled}
      size="small"
      style={{ width: 100 }}
      dropdownMatchSelectWidth={false}
    />
  )
}

export default MarkSelector
