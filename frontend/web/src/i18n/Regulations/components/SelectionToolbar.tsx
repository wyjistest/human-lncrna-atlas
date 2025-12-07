import { useMemo } from 'react'
import { Alert, Button, Dropdown, Space, Tooltip } from 'antd'
import { DownOutlined, InfoCircleOutlined, DeleteOutlined, ApartmentOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { BATCH_LIMITS, EXPORT_LIMITS } from '@/config/constants'
import type { components } from '@/types/api'

type RegulationListItem = components['schemas']['RegulationListItem']

interface SelectionToolbarProps {
  selectedCount: number
  selectedRows: RegulationListItem[]
  onClear: () => void
  onExport: (format: 'csv' | 'xlsx') => void
  onVisualize?: () => void
  loading?: boolean
}

export function SelectionToolbar({
  selectedCount,
  selectedRows: _selectedRows,  // 添加下划线前缀，表示未使用
  onClear,
  onExport,
  onVisualize,
  loading = false
}: SelectionToolbarProps) {
  const { t, i18n } = useTranslation('regulations')

  const isExportDisabled = selectedCount > BATCH_LIMITS.MAX_EXPORT
  const isVisualizeDisabled = selectedCount > BATCH_LIMITS.MAX_VISUALIZATION
  const showWarning = selectedCount > EXPORT_LIMITS.WARN && selectedCount <= BATCH_LIMITS.MAX_EXPORT

  // useMemo 必须在 early return 之前调用（添加 onExport 依赖避免 stale closure）
  const exportMenuItems: MenuProps['items'] = useMemo(() => [
    {
      key: 'csv',
      label: t('export.csv'),
      disabled: isExportDisabled,
      onClick: () => onExport('csv')
    },
    {
      key: 'xlsx',
      label: t('export.xlsx'),
      disabled: isExportDisabled,
      onClick: () => onExport('xlsx')
    }
  ], [t, isExportDisabled, onExport])

  // Early return 必须在所有 hooks 之后
  if (selectedCount === 0) return null

  return (
    <Alert
      type={showWarning ? 'warning' : 'info'}
      showIcon
      message={
        <Space wrap>
          <span>
            {t('selection.selected', { count: selectedCount })}
          </span>

          <Button
            size="small"
            icon={<DeleteOutlined />}
            onClick={onClear}
          >
            {t('selection.clear')}
          </Button>

          <Dropdown menu={{ items: exportMenuItems }} disabled={isExportDisabled}>
            <Button size="small" loading={loading} disabled={isExportDisabled}>
              {t('selection.exportSelected')} <DownOutlined />
            </Button>
          </Dropdown>

          {onVisualize && (
            <Tooltip
              title={isVisualizeDisabled
                ? (i18n.language?.startsWith('en') ? `Max ${BATCH_LIMITS.MAX_VISUALIZATION} for visualization` : `可视化上限为 ${BATCH_LIMITS.MAX_VISUALIZATION} 条`)
                : t('visualization.title')}
            >
              <Button
                size="small"
                type="primary"
                icon={<ApartmentOutlined />}
                onClick={onVisualize}
                disabled={isVisualizeDisabled}
              >
                {t('selection.visualize')}
              </Button>
            </Tooltip>
          )}

          {isExportDisabled && (
            <Tooltip title={i18n.language?.startsWith('en') ? `Export limit: ${BATCH_LIMITS.MAX_EXPORT.toLocaleString()}` : `批量导出上限为 ${BATCH_LIMITS.MAX_EXPORT.toLocaleString()} 条`}>
              <span style={{ color: '#ff4d4f', fontSize: 12 }}>
                <InfoCircleOutlined /> {i18n.language?.startsWith('en') ? 'Exceeds limit' : '超出导出上限'}
              </span>
            </Tooltip>
          )}

          {showWarning && (
            <span style={{ color: '#faad14', fontSize: 12 }}>
              <InfoCircleOutlined /> {i18n.language?.startsWith('en') ? 'Large data set, export may take time' : '数据量较大，导出可能需要一些时间'}
            </span>
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
    />
  )
}
