/**
 * ConservationBadge Component
 * Displays conservation tier with color-coded Ant Design Tag
 * Phase 2.2.1 - Conservation Visualization MVP
 */
import { Tag, Tooltip } from 'antd'
import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  parseConservationLabel,
  CONSERVATION_COLORS,
  type ConservationCategory
} from '@/types/conservation'

interface ConservationBadgeProps {
  /** Conservation label (4-char binary string, e.g., "1100") */
  conservationLabel?: string | null
  /** Pre-computed conservation count (optional) */
  conservationCount?: number
  /** Show detailed species breakdown in tooltip */
  showDetails?: boolean
  /** Badge size */
  size?: 'small' | 'default'
}

/**
 * Species info for tooltip display
 */
interface SpeciesInfo {
  key: 'human' | 'chimpanzee' | 'macaque' | 'marmoset'
  nameKey: string
}

const SPECIES_LIST: SpeciesInfo[] = [
  { key: 'human', nameKey: 'conservation.species.human' },
  { key: 'chimpanzee', nameKey: 'conservation.species.chimpanzee' },
  { key: 'macaque', nameKey: 'conservation.species.macaque' },
  { key: 'marmoset', nameKey: 'conservation.species.marmoset' }
]

/**
 * Get tag color based on conservation category
 * Maps to Ant Design color presets or custom hex
 */
function getTagColor(category: ConservationCategory): string {
  // Using hex colors directly for consistency with Tol Bright palette
  return CONSERVATION_COLORS[category]
}

export const ConservationBadge: React.FC<ConservationBadgeProps> = ({
  conservationLabel,
  conservationCount,
  showDetails = true,
  size = 'default'
}) => {
  const { t } = useTranslation('genes')

  // Parse conservation data
  const conservation = parseConservationLabel(conservationLabel, conservationCount)

  // Get localized category text
  const getCategoryText = () => {
    switch (conservation.category) {
      case 'high':
        return t('conservation.high')
      case 'medium':
        return t('conservation.medium')
      case 'low':
        return t('conservation.low')
      default:
        return t('conservation.unknown')
    }
  }

  // Build display text
  const displayText = conservation.category === 'unknown'
    ? getCategoryText()
    : `${getCategoryText()} (${conservation.count}/4)`

  // Build tooltip content
  const tooltipContent = showDetails ? (
    <div style={{ minWidth: 140 }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8 }}>
        {t('conservation.legend.title')}
      </div>
      {SPECIES_LIST.map((species) => (
        <div
          key={species.key}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4
          }}
        >
          {conservation.species[species.key] ? (
            <CheckCircleFilled style={{ color: '#52c41a' }} />
          ) : (
            <CloseCircleFilled style={{ color: '#d9d9d9' }} />
          )}
          <span>{t(species.nameKey)}</span>
        </div>
      ))}
    </div>
  ) : undefined

  // Style adjustments based on size
  const tagStyle: React.CSSProperties = {
    fontSize: size === 'small' ? 11 : 13,
    padding: size === 'small' ? '0 4px' : '2px 8px',
    fontWeight: 500,
    cursor: showDetails ? 'help' : 'default'
  }

  const badge = (
    <Tag color={getTagColor(conservation.category)} style={tagStyle}>
      {displayText}
    </Tag>
  )

  if (showDetails && tooltipContent) {
    return (
      <Tooltip title={tooltipContent} placement="bottom">
        {badge}
      </Tooltip>
    )
  }

  return badge
}

export default ConservationBadge
