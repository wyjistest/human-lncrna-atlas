/**
 * StatsCards Component
 * Phase 2.2 - Statistics display cards for ChIP-seq data
 *
 * Displays key metrics for the selected mark type:
 * - Total peaks count
 * - Average signal value
 * - Average fold enrichment
 * - Position distribution
 */

import { Card, Statistic, Row, Col, Space, Tag, Tooltip } from 'antd'
import {
  BarChartOutlined,
  RiseOutlined,
  AimOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getMarkColor } from '@/config/markConfigs'
import type { MarkType, ChIPSeqSummary } from '@/types/chipseq'

interface StatsCardsProps {
  /** Mark type for styling */
  markType: MarkType
  /** Summary statistics data */
  summary: ChIPSeqSummary | undefined
  /** Loading state */
  loading?: boolean
}

/**
 * Position distribution tag with color coding
 */
function PositionTag({
  position,
  count,
  total,
}: {
  position: string
  count: number
  total: number
}) {
  const percentage = total > 0 ? ((count / total) * 100).toFixed(1) : '0'

  // Color mapping for different positions
  const colorMap: Record<string, string> = {
    promoter: '#52c41a',
    upstream: '#1890ff',
    downstream: '#722ed1',
    exon: '#fa8c16',
    intron: '#13c2c2',
    gene_body: '#eb2f96',
  }

  return (
    <Tooltip title={`${count.toLocaleString()} peaks (${percentage}%)`}>
      <Tag color={colorMap[position] || 'default'} style={{ margin: 2 }}>
        {position}: {count}
      </Tag>
    </Tooltip>
  )
}

/**
 * StatsCards Component
 *
 * Displays summary statistics for ChIP-seq data in card format.
 *
 * @example
 * ```tsx
 * <StatsCards
 *   markType="H3K27me3"
 *   summary={summaryData}
 *   loading={isLoading}
 * />
 * ```
 */
export function StatsCards({ markType, summary, loading = false }: StatsCardsProps) {
  const { t } = useTranslation('genes')
  const markColor = getMarkColor(markType)

  if (!summary && !loading) {
    return null
  }

  return (
    <Row gutter={[16, 16]} data-testid="stats-cards-container">
      {/* Total Peaks */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <BarChartOutlined />
                {t('detail.chipseq.totalPeaks', 'Total Peaks')}
              </Space>
            }
            value={summary?.total_peaks ?? 0}
            styles={{ content: { color: markColor } }}
          />
        </Card>
      </Col>

      {/* Average Signal */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <RiseOutlined />
                {t('detail.chipseq.avgSignal', 'Avg Signal')}
              </Space>
            }
            value={summary?.avg_signal ?? 0}
            precision={2}
            styles={{ content: { color: '#1890ff' } }}
          />
        </Card>
      </Col>

      {/* Average Fold Enrichment */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <AimOutlined />
                {t('detail.chipseq.avgFoldEnrichment', 'Avg Fold Enrichment')}
              </Space>
            }
            value={summary?.avg_fold_enrichment ?? 0}
            precision={2}
            suffix="x"
            styles={{ content: { color: '#52c41a' } }}
          />
        </Card>
      </Col>

      {/* Max Signal */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <RiseOutlined />
                {t('detail.chipseq.maxSignal', 'Max Signal')}
              </Space>
            }
            value={summary?.max_signal ?? 0}
            precision={2}
            styles={{ content: { color: '#722ed1' } }}
          />
        </Card>
      </Col>

      {/* Position Distribution */}
      {summary?.position_distribution && Object.keys(summary.position_distribution).length > 0 && (
        <Col xs={24}>
          <Card
            size="small"
            title={
              <Space>
                <EnvironmentOutlined />
                <span style={{ fontSize: 14 }}>
                  {t('detail.chipseq.positionDistribution', 'Position Distribution')}
                </span>
              </Space>
            }
          >
            <Space wrap size={[4, 4]}>
              {Object.entries(summary.position_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([position, count]) => (
                  <PositionTag
                    key={position}
                    position={position}
                    count={count}
                    total={summary.total_peaks}
                  />
                ))}
            </Space>
          </Card>
        </Col>
      )}
    </Row>
  )
}

export default StatsCards
