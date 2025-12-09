/**
 * ChIPSeqComparePage
 * Phase 2.5 - Global ChIP-seq Mark Comparison Page
 *
 * This page provides a comprehensive view for comparing histone modification
 * marks across all genes and cell types in the database.
 *
 * Features:
 * - Multi-mark comparison with various visualizations
 * - Cell type filtering
 * - Export capabilities
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
    <div style={{ padding: '0 0 24px 0' }}>
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
          'Compare histone modifications across all genes and cell types to understand global epigenetic patterns.'
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
