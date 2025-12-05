/**
 * RepeatMaskerLegend Component
 * Floating legend showing repeat class colors for RepeatMasker track
 * Matches UCSC Genome Browser color scheme for repeat elements
 *
 * Color scheme (UCSC compatible):
 * - SINE: Red (#FF0000)
 * - LINE: Blue (#0000CC)
 * - LTR: Green (#00CC00)
 * - DNA: Purple (#CC00CC)
 * - Simple_repeat: Black (#000000)
 * - Low_complexity: Gray (#666666)
 * - Satellite: Orange (#CC6600)
 * - Other: Dark gray (#888888)
 */
import { useState } from 'react'
import { Button } from 'antd'
import { DownOutlined, UpOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { REPEAT_CLASS_COLORS, REPEAT_CLASS_ORDER } from './constants'

interface RepeatMaskerLegendProps {
  /** Position of the legend box */
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'
  /** Compact mode with smaller text and spacing */
  compact?: boolean
  /** Initial collapsed state */
  defaultCollapsed?: boolean
  /** Custom style overrides */
  style?: React.CSSProperties
}

/**
 * Get position styles based on position prop
 */
function getPositionStyles(position: RepeatMaskerLegendProps['position']): React.CSSProperties {
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

export const RepeatMaskerLegend: React.FC<RepeatMaskerLegendProps> = ({
  position = 'top-right',
  compact = false,
  defaultCollapsed = false,
  style
}) => {
  const { t } = useTranslation('genomeBrowser')
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  const containerStyle: React.CSSProperties = {
    ...getPositionStyles(position),
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderRadius: 6,
    padding: compact ? '6px 10px' : '10px 14px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
    fontSize: compact ? 11 : 12,
    minWidth: compact ? 100 : 140,
    ...style
  }

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    fontWeight: 600,
    marginBottom: collapsed ? 0 : (compact ? 4 : 8),
    color: '#333',
    fontSize: compact ? 11 : 13,
    cursor: 'pointer',
    userSelect: 'none'
  }

  const itemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: compact ? 6 : 8,
    marginBottom: compact ? 2 : 4
  }

  const colorBoxStyle = (color: string): React.CSSProperties => ({
    width: compact ? 14 : 18,
    height: compact ? 10 : 12,
    backgroundColor: color,
    borderRadius: 2,
    flexShrink: 0,
    border: color === '#000000' ? 'none' : '1px solid rgba(0,0,0,0.1)'
  })

  const labelStyle: React.CSSProperties = {
    color: '#666',
    lineHeight: 1.4
  }

  const toggleCollapse = () => {
    setCollapsed(!collapsed)
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle} onClick={toggleCollapse}>
        <span>{t('repeatMaskerLegend.title')}</span>
        <Button
          type="text"
          size="small"
          icon={collapsed ? <DownOutlined /> : <UpOutlined />}
          style={{ padding: '0 4px', height: 'auto', marginLeft: 8 }}
        />
      </div>
      {!collapsed && (
        <div style={{ marginTop: 4 }}>
          {REPEAT_CLASS_ORDER.map((repeatClass) => (
            <div key={repeatClass} style={itemStyle}>
              <div style={colorBoxStyle(REPEAT_CLASS_COLORS[repeatClass])} />
              <span style={labelStyle}>
                {t(`repeatMaskerLegend.classes.${repeatClass}`)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default RepeatMaskerLegend
