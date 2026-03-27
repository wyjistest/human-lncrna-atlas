import { Button, Space } from 'antd'
import { useTranslation } from 'react-i18next'
import { DownloadOutlined } from '@ant-design/icons'
import type { AnalysisTabKey } from '../evidenceRegistry'
import { getAnalysisTabDescriptor } from '../evidenceRegistry'

interface AnalysisTabActionBarProps {
  exportLabel: string
  exportDisabled: boolean
  isExporting: boolean
  onExport: () => void
  tabKey: AnalysisTabKey
}

export default function AnalysisTabActionBar({
  exportLabel,
  exportDisabled,
  isExporting,
  onExport,
  tabKey,
}: AnalysisTabActionBarProps) {
  const { t } = useTranslation('analysis')
  const descriptor = getAnalysisTabDescriptor(tabKey)
  const primaryEvidence = descriptor.evidence[0]

  return (
    <Space wrap>
      <Button
        aria-label={exportLabel}
        data-testid={`analysis-${tabKey}-export`}
        icon={<DownloadOutlined />}
        loading={isExporting}
        disabled={exportDisabled}
        onClick={() => { void onExport() }}
      >
        {exportLabel}
      </Button>
      {primaryEvidence ? (
        <Button
          href={primaryEvidence.href}
          target="_blank"
          rel="noreferrer"
          data-testid={`analysis-${tabKey}-evidence-link`}
        >
          {t('workspace.viewEvidence')}
        </Button>
      ) : null}
    </Space>
  )
}
