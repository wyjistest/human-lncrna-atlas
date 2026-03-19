/**
 * GlobalCompareSection Component
 *
 * The public /chipseq-compare page previously rendered mock charts backed by
 * non-existent endpoints. Until a real backend contract exists, this component
 * exposes an honest unavailable state instead of synthetic data.
 */

import { Alert, Card, Space, Tag, Typography } from 'antd'
import { ClockCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { GlobalCompareFilters, GlobalCompareViewMode } from '@/types/globalCompare'

const { Paragraph, Text, Title } = Typography

interface GlobalCompareSectionProps {
  /** 预留给未来真实 compare 流程的初始筛选参数。 */
  initialFilters?: Partial<GlobalCompareFilters>
  /** 预留给未来真实 compare 流程的默认 tab。 */
  defaultTab?: GlobalCompareViewMode
  /** Show title */
  showTitle?: boolean
}

const GENE_SCOPED_API_HINT = '/api/v1/features/chipseq/genes/{gene_id}/...'

export function GlobalCompareSection({
  showTitle = true,
}: GlobalCompareSectionProps) {
  const { t } = useTranslation('globalCompare')

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {showTitle && (
        <Space align="center" size="middle" wrap>
          <Title level={3} style={{ marginBottom: 0 }}>
            {t('title', 'ChIP-seq Global Comparison')}
          </Title>
          <Tag color="gold" icon={<ClockCircleOutlined />} data-testid="chipseq-compare-status-tag">
            {t('status.comingSoon', 'Coming soon')}
          </Tag>
        </Space>
      )}

      <div data-testid="chipseq-compare-unavailable">
        <Card>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Alert
              type="warning"
              showIcon
              message={t('unavailable.title', 'Global compare is not available yet')}
              description={t(
                'unavailable.description',
                'This page no longer shows mock data. A public backend contract for cross-gene global comparison has not been implemented yet.'
              )}
            />

            <Paragraph style={{ marginBottom: 0 }}>
              {t(
                'unavailable.guidance',
                'For real ChIP-seq analysis, use the gene-specific compare, summary, and heatmap tools from a gene detail page.'
              )}
            </Paragraph>

            <Card
              size="small"
              type="inner"
              title={t('unavailable.currentScope', 'Currently supported scope')}
            >
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Text>
                  {t(
                    'unavailable.scopeDetail',
                    'The backend currently supports gene-scoped ChIP-seq endpoints rather than a global mark-comparison dataset.'
                  )}
                </Text>
                <Text code>{GENE_SCOPED_API_HINT}</Text>
                <Space size="small" wrap>
                  <Tag color="blue">Gene compare</Tag>
                  <Tag color="blue">Cell-line compare</Tag>
                  <Tag color="blue">Heatmap matrix</Tag>
                  <Tag color="blue">Export</Tag>
                </Space>
              </Space>
            </Card>

            <Alert
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
              message={t('unavailable.devNoteTitle', 'Developer note')}
              description={t(
                'unavailable.devNote',
                'Legacy /api/v1/chipseq/* global-compare endpoints are intentionally not exposed. Frontend code should treat this page as unavailable until a real backend contract is added.'
              )}
            />
          </Space>
        </Card>
      </div>
    </Space>
  )
}

export default GlobalCompareSection
