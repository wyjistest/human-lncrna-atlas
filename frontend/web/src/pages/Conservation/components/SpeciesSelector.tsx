/**
 * SpeciesSelector Component
 * Multi-select component for choosing 2-4 species for conservation comparison
 */

import { Checkbox, Card, Space, Typography, Tag, Alert } from 'antd'
import { useTranslation } from 'react-i18next'
import { CONSERVATION_SPECIES } from '@/types/conservationPage'

const { Text } = Typography

interface SpeciesSelectorProps {
  /** Currently selected species IDs */
  selectedSpecies: number[]
  /** Callback when selection changes */
  onSelectionChange: (speciesIds: number[]) => void
  /** Whether the selector is disabled */
  disabled?: boolean
  /** Minimum required selections */
  minSelection?: number
  /** Maximum allowed selections */
  maxSelection?: number
}

/**
 * Species color mapping for visual distinction
 */
const SPECIES_COLORS: Record<number, string> = {
  1: '#1890ff', // Human - Blue
  2: '#52c41a', // Chimpanzee - Green
  3: '#faad14', // Macaque - Yellow/Orange
  4: '#eb2f96'  // Marmoset - Pink
}

/**
 * Species selector component for conservation analysis
 */
export function SpeciesSelector({
  selectedSpecies,
  onSelectionChange,
  disabled = false,
  minSelection = 2,
  maxSelection = 4
}: SpeciesSelectorProps) {
  const { t } = useTranslation('conservation')

  const handleChange = (speciesId: number, checked: boolean) => {
    let newSelection: number[]

    if (checked) {
      // Add species if under max limit
      if (selectedSpecies.length < maxSelection) {
        newSelection = [...selectedSpecies, speciesId].sort((a, b) => a - b)
      } else {
        return // Don't add if at max
      }
    } else {
      // Remove species if above min limit
      if (selectedSpecies.length > minSelection) {
        newSelection = selectedSpecies.filter(id => id !== speciesId)
      } else {
        return // Don't remove if at min
      }
    }

    onSelectionChange(newSelection)
  }

  const isValid = selectedSpecies.length >= minSelection && selectedSpecies.length <= maxSelection
  const canAddMore = selectedSpecies.length < maxSelection
  const canRemoveMore = selectedSpecies.length > minSelection

  return (
    <Card
      title={t('speciesSelector.title', 'Select Species for Comparison')}
      size="small"
      style={{ marginBottom: 16 }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* Selection hint */}
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t('speciesSelector.hint', 'Select 2-4 species to analyze conservation patterns')}
        </Text>

        {/* Species checkboxes */}
        <Space wrap>
          {CONSERVATION_SPECIES.map(species => {
            const isChecked = selectedSpecies.includes(species.id)
            const isDisabledCheck = disabled || (!isChecked && !canAddMore)
            const isDisabledUncheck = disabled || (isChecked && !canRemoveMore)

            return (
              <Checkbox
                key={species.id}
                checked={isChecked}
                disabled={isChecked ? isDisabledUncheck : isDisabledCheck}
                onChange={(e) => handleChange(species.id, e.target.checked)}
                style={{ marginRight: 16 }}
              >
                <Tag
                  color={isChecked ? SPECIES_COLORS[species.id] : 'default'}
                  style={{ cursor: 'pointer' }}
                >
                  {t(`species.${species.name.toLowerCase()}`, species.name)}
                </Tag>
              </Checkbox>
            )
          })}
        </Space>

        {/* Selected species tags */}
        {selectedSpecies.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 12, marginRight: 8 }}>
              {t('speciesSelector.selected', 'Selected')}:
            </Text>
            {selectedSpecies.map(id => {
              const species = CONSERVATION_SPECIES.find(s => s.id === id)
              return species ? (
                <Tag key={id} color={SPECIES_COLORS[id]} style={{ marginRight: 4 }}>
                  {t(`species.${species.name.toLowerCase()}`, species.name)}
                </Tag>
              ) : null
            })}
          </div>
        )}

        {/* Validation message */}
        {!isValid && (
          <Alert
            type="warning"
            message={t(
              'speciesSelector.validationError',
              `Please select between ${minSelection} and ${maxSelection} species`
            )}
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
      </Space>
    </Card>
  )
}

export default SpeciesSelector
