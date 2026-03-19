/**
 * ChIPSeqComparePage
 * Phase 2.5 - Global ChIP-seq Mark Comparison Page
 *
 * This route is intentionally kept as an honest status page.
 * The previous implementation rendered mock charts for a backend contract that
 * does not exist yet.
 */

import { useTranslation } from 'react-i18next'
import { Typography, Breadcrumb } from 'antd'
import { HomeOutlined, ExperimentOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import GlobalCompareSection from '@/components/GlobalCompare'

const { Paragraph } = Typography

/**
 * ChIPSeqComparePage Component
 *
 * Main page component for global ChIP-seq mark comparison.
 */
export default function ChIPSeqComparePage() {
  const { t } = useTranslation('globalCompare')

  return (
    <div data-testid="chipseq-compare-page" style={{ padding: '0 0 24px 0' }}>
      {/* Breadcrumb */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/">
                <HomeOutlined />
              </Link>
            ),
          },
          {
            title: (
              <>
                <ExperimentOutlined style={{ marginRight: 4 }} />
                {t('title', 'ChIP-seq Global Comparison')}
              </>
            ),
          },
        ]}
      />

      {/* Page Description */}
      <Paragraph type="secondary" style={{ marginBottom: 24 }}>
        {t(
          'subtitle',
          'Global ChIP-seq comparison is not publicly available yet. Use the guided gene-scoped entry points below for real data.'
        )}
      </Paragraph>

      {/* Main Content */}
      <GlobalCompareSection
        defaultTab="radar"
        showTitle={false}
      />
    </div>
  )
}
