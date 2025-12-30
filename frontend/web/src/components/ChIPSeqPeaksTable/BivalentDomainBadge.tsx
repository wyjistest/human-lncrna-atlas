/**
 * BivalentDomainBadge Component
 * Phase 2.5 - Visual indicator for bivalent chromatin domains
 *
 * Displays a badge when H3K4me3 (active) and H3K27me3 (repressive) marks
 * co-occur, indicating a bivalent chromatin domain which is biologically
 * significant in stem cells and cancer.
 */

import { Alert, Badge, Tooltip, Space, Typography } from 'antd'
import { ExperimentOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { MarkType, ChIPSeqCompareResponse, OverlapRegion } from '@/types/chipseq'

const { Text } = Typography

interface BivalentDomainBadgeProps {
  /** Whether bivalent domain is detected */
  hasBivalentDomain?: boolean
  /** Comparison data containing overlap information */
  compareData?: ChIPSeqCompareResponse
  /** Selected marks for comparison */
  selectedMarks?: MarkType[]
  /** Display mode: 'badge' for inline, 'alert' for full-width alert */
  displayMode?: 'badge' | 'alert'
  /** Show detailed overlap statistics */
  showDetails?: boolean
}

/**
 * Check if selected marks include the bivalent pair (H3K4me3 + H3K27me3)
 */
function hasBivalentMarks(marks: MarkType[]): boolean {
  return marks.includes('H3K4me3') && marks.includes('H3K27me3')
}

/**
 * Get bivalent overlap statistics from comparison data
 */
function getBivalentOverlap(
  overlapRegions?: OverlapRegion[]
): OverlapRegion | undefined {
  if (!overlapRegions) return undefined

  return overlapRegions.find(
    (r) =>
      (r.mark1 === 'H3K4me3' && r.mark2 === 'H3K27me3') ||
      (r.mark1 === 'H3K27me3' && r.mark2 === 'H3K4me3')
  )
}

/**
 * BivalentDomainBadge Component
 *
 * Displays visual indicator when bivalent chromatin domains are detected.
 * Bivalent domains contain both H3K4me3 (activating) and H3K27me3 (repressive)
 * marks, which is characteristic of poised genes in stem cells and is often
 * observed in cancer-related genes.
 *
 * @example Badge mode (inline)
 * ```tsx
 * <BivalentDomainBadge
 *   hasBivalentDomain={true}
 *   displayMode="badge"
 * />
 * ```
 *
 * @example Alert mode with details
 * ```tsx
 * <BivalentDomainBadge
 *   compareData={comparisonData}
 *   selectedMarks={['H3K4me3', 'H3K27me3']}
 *   displayMode="alert"
 *   showDetails
 * />
 * ```
 */
export function BivalentDomainBadge({
  hasBivalentDomain,
  compareData,
  selectedMarks = [],
  displayMode = 'badge',
  showDetails = false,
}: BivalentDomainBadgeProps) {
  const { t } = useTranslation('genes')

  // Determine if we should show the badge
  const showBadge =
    hasBivalentDomain ||
    compareData?.has_bivalent_domain ||
    (hasBivalentMarks(selectedMarks) && compareData?.overlap_regions)

  // Get overlap statistics
  const bivalentOverlap = getBivalentOverlap(compareData?.overlap_regions)

  // Don't render if no bivalent domain
  if (!showBadge) {
    return null
  }

  // Tooltip content explaining bivalent domains
  const tooltipContent = (
    <div style={{ maxWidth: 300 }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8 }}>
        {t('detail.chipseq.bivalent.title', 'Bivalent Chromatin Domain')}
      </div>
      <div style={{ marginBottom: 8 }}>
        {t(
          'detail.chipseq.bivalent.description',
          'This gene region contains both H3K4me3 (activating) and H3K27me3 (repressive) histone marks simultaneously.'
        )}
      </div>
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary">
          {t(
            'detail.chipseq.bivalent.significance',
            'Bivalent domains are characteristic of poised genes in stem cells and are frequently observed in developmental and cancer-related genes.'
          )}
        </Text>
      </div>
      {bivalentOverlap && (
        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
          <Text strong>
            {t('detail.chipseq.bivalent.overlapStats', 'Overlap Statistics')}:
          </Text>
          <br />
          <Text>
            {t('detail.chipseq.bivalent.regionCount', 'Regions')}: {bivalentOverlap.region_count}
          </Text>
          <br />
          <Text>
            {t('detail.chipseq.bivalent.totalBp', 'Total Coverage')}: {bivalentOverlap.total_bp.toLocaleString()} bp
          </Text>
        </div>
      )}
    </div>
  )

  // Badge display mode
  if (displayMode === 'badge') {
    return (
      <Tooltip title={tooltipContent} placement="bottom">
        <Badge
          count={
            <Space size={4} style={{ cursor: 'help' }}>
              <ExperimentOutlined style={{ color: '#722ed1', fontSize: 14 }} />
              <span style={{ color: '#722ed1', fontWeight: 500 }}>
                {t('detail.chipseq.bivalent.badge', 'Bivalent')}
              </span>
              <QuestionCircleOutlined style={{ color: '#8c8c8c', fontSize: 12 }} />
            </Space>
          }
          style={{
            backgroundColor: '#f9f0ff',
            border: '1px solid #d3adf7',
            borderRadius: 4,
            padding: '4px 8px',
            height: 'auto',
            lineHeight: '1.5',
          }}
        />
      </Tooltip>
    )
  }

  // Alert display mode
  return (
    <Alert
      type="info"
      icon={<ExperimentOutlined />}
      showIcon
      title={
        <Space>
          <span style={{ fontWeight: 500 }}>
            {t('detail.chipseq.bivalent.detected', 'Bivalent Domain Detected')}
          </span>
          <Tooltip title={tooltipContent}>
            <QuestionCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
          </Tooltip>
        </Space>
      }
      description={
        showDetails ? (
          <div>
            <div style={{ marginBottom: 8 }}>
              {t(
                'detail.chipseq.bivalent.alertDescription',
                'H3K4me3 and H3K27me3 marks co-occur in this gene region, indicating a bivalent chromatin state.'
              )}
            </div>
            {bivalentOverlap && (
              <Space size="large">
                <Text type="secondary">
                  {t('detail.chipseq.bivalent.regionCount', 'Regions')}: <Text strong>{bivalentOverlap.region_count}</Text>
                </Text>
                <Text type="secondary">
                  {t('detail.chipseq.bivalent.totalBp', 'Total Coverage')}: <Text strong>{bivalentOverlap.total_bp.toLocaleString()} bp</Text>
                </Text>
              </Space>
            )}
          </div>
        ) : undefined
      }
      style={{
        backgroundColor: '#f9f0ff',
        borderColor: '#d3adf7',
      }}
    />
  )
}

export default BivalentDomainBadge
