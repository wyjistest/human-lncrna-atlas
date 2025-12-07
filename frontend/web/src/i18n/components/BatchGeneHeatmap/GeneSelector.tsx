/**
 * GeneSelector Component
 * Multi-select component for selecting multiple genes for batch heatmap visualization
 * Phase 2.10 - Batch Gene Heatmap Feature
 */

import { useMemo, useCallback } from 'react'
import { Select, Button, Space, Input, Tag, Empty, Spin } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { DefaultOptionType } from 'antd/es/select'

interface GeneInfo {
  gene_id: number
  gene_name: string
  chromosome?: string
  start?: number
  end?: number
}

interface GeneSelectorProps {
  /** Currently selected genes */
  value?: GeneInfo[]
  /** Change handler */
  onChange?: (genes: GeneInfo[]) => void
  /** Available genes from API */
  availableGenes?: GeneInfo[]
  /** Loading state */
  loading?: boolean
  /** Disabled state */
  disabled?: boolean
  /** Maximum number of genes to select */
  maxCount?: number
  /** Placeholder text */
  placeholder?: string
  /** Allow clear selection */
  allowClear?: boolean
  /** Custom style */
  style?: React.CSSProperties
  /** Show quick add input */
  showQuickAdd?: boolean
}

/**
 * Custom tag render for multi-select mode
 */
function tagRender(props: {
  label: React.ReactNode
  value: number
  closable: boolean
  onClose: () => void
  data?: GeneInfo
}) {
  const { label, closable, onClose } = props

  return (
    <Tag
      color="blue"
      closable={closable}
      onClose={onClose}
      style={{ marginRight: 3, marginBottom: 3 }}
    >
      {label}
    </Tag>
  )
}

/**
 * GeneSelector Component
 *
 * A multi-select component for choosing multiple genes for batch analysis.
 * Features search, filtering, and quick add functionality.
 *
 * @example
 * ```tsx
 * const [selectedGenes, setSelectedGenes] = useState<GeneInfo[]>([])
 *
 * <GeneSelector
 *   value={selectedGenes}
 *   onChange={setSelectedGenes}
 *   availableGenes={genesList}
 *   maxCount={10}
 * />
 * ```
 */
export function GeneSelector({
  value = [],
  onChange,
  availableGenes = [],
  loading = false,
  disabled = false,
  maxCount = 10,
  placeholder,
  allowClear = true,
  style,
  showQuickAdd = true,
}: GeneSelectorProps) {
  const { t } = useTranslation('genes')

  // Build options from available genes
  const options = useMemo<DefaultOptionType[]>(() => {
    return availableGenes.map((gene) => ({
      value: gene.gene_id,
      label: (
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <span>{gene.gene_name}</span>
          {gene.chromosome && (
            <span style={{ color: '#999', fontSize: 12 }}>
              {gene.chromosome}:{gene.start?.toLocaleString()}-{gene.end?.toLocaleString()}
            </span>
          )}
        </div>
      ),
      data: gene,
      // Store searchable values
      searchValue: `${gene.gene_name} ${gene.chromosome || ''} ${gene.gene_id}`,
    }))
  }, [availableGenes])

  // Handle change
  const handleChange = useCallback(
    (selectedIds: number[]) => {
      const selectedGenes = selectedIds
        .map((id) => availableGenes.find((g) => g.gene_id === id))
        .filter((g): g is GeneInfo => g !== undefined)

      onChange?.(selectedGenes)
    },
    [onChange, availableGenes]
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

  const selectedIds = value.map((g) => g.gene_id)

  const defaultPlaceholder = placeholder || t('batchGeneHeatmap.selectGenes', 'Select genes to analyze')

  return (
    <Space direction="vertical" style={{ width: '100%', ...style }} size="middle">
      {/* Selection info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#666' }}>
          {value.length}/{maxCount} genes selected
        </span>
        {value.length > 0 && (
          <Button
            type="text"
            size="small"
            danger
            onClick={() => onChange?.([])}
          >
            Clear All
          </Button>
        )}
      </div>

      {/* Select dropdown */}
      <Select
        mode="multiple"
        value={selectedIds}
        onChange={handleChange}
        options={options}
        placeholder={defaultPlaceholder}
        disabled={disabled || loading}
        allowClear={allowClear && value.length > 0}
        style={{ width: '100%' }}
        size="middle"
        showSearch
        filterOption={filterOption}
        tagRender={tagRender}
        maxCount={maxCount}
        optionFilterProp="searchValue"
        popupMatchSelectWidth={false}
        dropdownStyle={{ minWidth: 400 }}
        listHeight={320}
        notFoundContent={
          loading ? (
            <Spin size="small" />
          ) : availableGenes.length === 0 ? (
            <Empty
              description={t('batchGeneHeatmap.noGenesAvailable', 'No genes available')}
              style={{ marginTop: 16, marginBottom: 16 }}
            />
          ) : undefined
        }
      />

      {/* Quick add input (optional) */}
      {showQuickAdd && (
        <div>
          <span style={{ fontSize: 12, color: '#666', marginBottom: 8, display: 'block' }}>
            Or search and add by gene name:
          </span>
          <Input.Search
            placeholder={t('batchGeneHeatmap.searchByName', 'Search gene name')}
            disabled={disabled || loading}
            onSearch={(searchTerm) => {
              if (searchTerm.trim()) {
                const matchedGene = availableGenes.find(
                  (g) => g.gene_name.toLowerCase() === searchTerm.toLowerCase()
                )
                if (matchedGene && !selectedIds.includes(matchedGene.gene_id)) {
                  if (value.length < maxCount) {
                    onChange?.([...value, matchedGene])
                  }
                }
              }
            }}
            allowClear
            size="small"
          />
        </div>
      )}

      {/* Selected genes display */}
      {value.length > 0 && (
        <div style={{ maxHeight: 120, overflowY: 'auto', paddingRight: 8 }}>
          <Space wrap size="small">
            {value.map((gene) => (
              <Tag
                key={gene.gene_id}
                closable
                onClose={() => {
                  onChange?.(value.filter((g) => g.gene_id !== gene.gene_id))
                }}
                color="blue"
                icon={<PlusOutlined style={{ marginRight: 4 }} />}
              >
                <span style={{ fontWeight: 500 }}>{gene.gene_name}</span>
                {gene.chromosome && (
                  <span style={{ marginLeft: 8, fontSize: 11, color: '#666' }}>
                    {gene.chromosome}
                  </span>
                )}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* Warning when at max capacity */}
      {value.length === maxCount && (
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: '#fff7e6',
            border: '1px solid #ffd591',
            borderRadius: 4,
            fontSize: 12,
            color: '#ad6800',
          }}
        >
          Maximum {maxCount} genes selected. Remove one to add another.
        </div>
      )}
    </Space>
  )
}

export default GeneSelector
