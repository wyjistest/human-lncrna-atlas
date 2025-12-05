/**
 * ConservationLegend Component
 * Floating legend showing conservation tiers with colored indicators
 * Phase 2.2.1 - Conservation Visualization MVP
 */
import { useTranslation } from 'react-i18next'
import {
  CONSERVATION_COLORS,
  type ConservationCategory
} from '@/types/conservation'

interface ConservationLegendProps {
  /** Position of the legend box */
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'
  /** Compact mode with smaller text and spacing */
  compact?: boolean
  /** Custom style overrides */
  style?: React.CSSProperties
}

/**
 * Legend items configuration
 */
interface LegendItem {
  category: ConservationCategory
  labelKey: string
  description: string
}

const LEGEND_ITEMS: LegendItem[] = [
  { category: 'high', labelKey: 'conservation.high', description: '4 species' },
  { category: 'medium', labelKey: 'conservation.medium', description: '2-3 species' },
  { category: 'low', labelKey: 'conservation.low', description: '1 species' },
  { category: 'unknown', labelKey: 'conservation.unknown', description: '0 species' }
]

/**
 * Get position styles based on position prop
 */
function getPositionStyles(position: ConservationLegendProps['position']): React.CSSProperties {
  const base: React.CSSProperties = {
    position: 'absolute',
    zIndex: 10
  }

  switch (position) {
    case 'top-left':
      return { ...base, top: 10, left: 10 }
    case 'bottom-right':
      return { ...base, bottom: 10, right: 10 }
    case 'bottom-left':
      return { ...base, bottom: 10, left: 10 }
    case 'top-right':
    default:
      return { ...base, top: 10, right: 10 }
  }
}

export const ConservationLegend: React.FC<ConservationLegendProps> = ({
  position = 'top-right',
  compact = false,
  style
}) => {
  const { t } = useTranslation('genes')

  const containerStyle: React.CSSProperties = {
    ...getPositionStyles(position),
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderRadius: 6,
    padding: compact ? '6px 10px' : '10px 14px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
    fontSize: compact ? 11 : 12,
    minWidth: compact ? 100 : 120,
    ...style
  }

  const titleStyle: React.CSSProperties = {
    fontWeight: 600,
    marginBottom: compact ? 4 : 8,
    color: '#333',
    fontSize: compact ? 11 : 13
  }

  const itemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: compact ? 6 : 8,
    marginBottom: compact ? 2 : 4
  }

  const circleStyle = (color: string): React.CSSProperties => ({
    width: compact ? 10 : 12,
    height: compact ? 10 : 12,
    borderRadius: '50%',
    backgroundColor: color,
    flexShrink: 0
  })

  const labelStyle: React.CSSProperties = {
    color: '#666',
    lineHeight: 1.4
  }

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>
        {t('conservation.legend.title')}
      </div>
      {LEGEND_ITEMS.map((item) => (
        <div key={item.category} style={itemStyle}>
          <div style={circleStyle(CONSERVATION_COLORS[item.category])} />
          <span style={labelStyle}>
            {t(item.labelKey)}
            {!compact && (
              <span style={{ color: '#999', marginLeft: 4 }}>
                ({item.description})
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  )
}

export default ConservationLegend
