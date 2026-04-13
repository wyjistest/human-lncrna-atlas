import { Button, Card, Space, Tag, Typography, message } from 'antd'
import { useTranslation } from 'react-i18next'
import { copyText } from '@/utils/copyText'
import type { AnalysisTabKey } from '../evidenceRegistry'
import { getAnalysisTabDescriptor } from '../evidenceRegistry'

const { Text } = Typography

interface AnalysisWorkspacePanelProps {
  activeTab: AnalysisTabKey
}

export default function AnalysisWorkspacePanel({ activeTab }: AnalysisWorkspacePanelProps) {
  const { t } = useTranslation('analysis')
  const descriptor = getAnalysisTabDescriptor(activeTab)
  const [messageApi, contextHolder] = message.useMessage()
  const [primaryEvidence, ...supportingEvidence] = descriptor.evidence

  const handleCopyLink = async () => {
    try {
      const copied = await copyText(window.location.href)
      if (!copied) {
        messageApi.error(t('workspace.copyLinkError'))
        return
      }
      messageApi.success(t('workspace.copyLinkSuccess'))
    } catch (error) {
      console.error('Copy share link failed:', error)
      messageApi.error(t('workspace.copyLinkError'))
    }
  }

  return (
    <>
      {contextHolder}
      <Card size="small" style={{ marginBottom: 16 }} data-testid="analysis-workspace-panel">
        <Space orientation="vertical" size={8} style={{ width: '100%' }}>
          <Text type="secondary">{t(descriptor.summaryKey)}</Text>

          <Space wrap>
            <Button type="primary" onClick={() => { void handleCopyLink() }}>
              {t('workspace.copyLink')}
            </Button>
            <Tag color={descriptor.downstreamReady ? 'blue' : 'gold'}>
              {t('workspace.downstream')}: {descriptor.downstreamReady && descriptor.downstreamActionKey
                ? t(descriptor.downstreamActionKey)
                : t('workspace.comingSoon')}
            </Tag>
          </Space>

          {primaryEvidence ? (
            <Space wrap>
              <Text strong>{t('workspace.evidence')}:</Text>
              <a
                data-testid="analysis-workspace-evidence-primary"
                href={primaryEvidence.href}
                target="_blank"
                rel="noreferrer"
              >
                {primaryEvidence.label}
              </a>
            </Space>
          ) : null}

          {supportingEvidence.length > 0 ? (
            <Space wrap>
              <Text type="secondary">{t('workspace.moreEvidence')}:</Text>
              {supportingEvidence.map((item) => (
                <a
                  key={item.id}
                  data-testid={`analysis-workspace-evidence-${item.id}`}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  {item.label}
                </a>
              ))}
            </Space>
          ) : null}
        </Space>
      </Card>
    </>
  )
}
