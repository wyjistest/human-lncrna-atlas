/**
 * OverlapStatsCards Component
 * Phase 3.0 - Task 1.7
 *
 * Statistics display cards for lncRNA-ChIP-seq overlap analysis.
 *
 * Displays key metrics:
 * - Total overlaps
 * - Unique lncRNAs involved
 * - Unique target genes
 * - Average overlap length
 * - Average binding affinity
 * - Average peak strength
 * - Distribution by mark type
 * - Distribution by cell type
 */

import { Card, Statistic, Row, Col, Space, Tag, Tooltip } from 'antd'
import {
  BarChartOutlined,
  ExperimentOutlined,
  AimOutlined,
  RiseOutlined,
  FireOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getMarkColor } from '@/config/markConfigs'
import { getCellTypeColor } from '@/config/cellTypeConfigs'
import type { OverlapSummary } from '@/types/lncRNAChIPSeqOverlap'
import type { MarkType } from '@/types/chipseq'

interface OverlapStatsCardsProps {
  /** Summary statistics data */
  summary: OverlapSummary | undefined
  /** Loading state */
  loading?: boolean
}

/**
 * Mark type tag with count
 */
function MarkTypeTag({
  markType,
  count,
  avgStrength,
}: {
  markType: string
  count: number
  avgStrength: number
}) {
  const color = getMarkColor(markType as MarkType)

  return (
    <Tooltip
      title={
        <span>
          {count.toLocaleString()} overlaps<br />
          Avg strength: {avgStrength.toFixed(2)}x
        </span>
      }
    >
      <Tag color={color} style={{ margin: 2, minWidth: 80, textAlign: 'center' }}>
        {markType}: {count}
      </Tag>
    </Tooltip>
  )
}

/**
 * Cell type tag with count
 */
function CellTypeTag({ cellType, count }: { cellType: string; count: number }) {
  const color = getCellTypeColor(cellType)

  return (
    <Tooltip title={`${count.toLocaleString()} overlaps in ${cellType}`}>
      <Tag color={color} style={{ margin: 2, minWidth: 70, textAlign: 'center' }}>
        {cellType}: {count}
      </Tag>
    </Tooltip>
  )
}

/**
 * OverlapStatsCards Component
 *
 * Displays summary statistics for lncRNA-ChIP-seq overlap data in card format.
 * Note: This component requires Phase 2 backend implementation for summary endpoint.
 *
 * @example
 * ```tsx
 * <OverlapStatsCards
 *   summary={summaryData}
 *   loading={isLoading}
 * />
 * ```
 */
export function OverlapStatsCards({ summary, loading = false }: OverlapStatsCardsProps) {
  const { t } = useTranslation('overlap')

  // Return null if no summary data and not loading (Phase 2 feature)
  if (!summary && !loading) {
    return null
  }

  return (
    <Row gutter={[16, 16]}>
      {/* Total Overlaps */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <LinkOutlined />
                {t('stats.totalOverlaps', 'Total Overlaps')}
              </Space>
            }
            value={summary?.total_overlaps ?? 0}
            styles={{ content: { color: '#1890ff' } }}
          />
        </Card>
      </Col>

      {/* Unique lncRNAs */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <ExperimentOutlined />
                {t('stats.uniqueLncRNAs', 'Unique lncRNAs')}
              </Space>
            }
            value={summary?.unique_lncrnas ?? 0}
            styles={{ content: { color: '#52c41a' } }}
          />
        </Card>
      </Col>

      {/* Unique Target Genes */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <AimOutlined />
                {t('stats.uniqueTargets', 'Unique Targets')}
              </Space>
            }
            value={summary?.unique_target_genes ?? 0}
            styles={{ content: { color: '#722ed1' } }}
          />
        </Card>
      </Col>

      {/* Unique Marks */}
      <Col xs={24} sm={12} md={6}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <BarChartOutlined />
                {t('stats.uniqueMarks', 'Unique Marks')}
              </Space>
            }
            value={summary?.unique_marks ?? 0}
            styles={{ content: { color: '#fa8c16' } }}
          />
        </Card>
      </Col>

      {/* Average Overlap Length */}
      <Col xs={24} sm={12} md={8}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <AimOutlined />
                {t('stats.avgOverlapLength', 'Avg Overlap Length')}
              </Space>
            }
            value={summary?.avg_overlap_length ?? 0}
            precision={0}
            suffix="bp"
            styles={{ content: { color: '#1890ff' } }}
          />
        </Card>
      </Col>

      {/* Average Binding Affinity */}
      <Col xs={24} sm={12} md={8}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <FireOutlined />
                {t('stats.avgBindingAffinity', 'Avg Binding Affinity')}
              </Space>
            }
            value={summary?.avg_binding_affinity ?? 0}
            precision={2}
            styles={{ content: { color: '#52c41a' } }}
          />
        </Card>
      </Col>

      {/* Average Peak Strength */}
      <Col xs={24} sm={12} md={8}>
        <Card size="small" hoverable loading={loading}>
          <Statistic
            title={
              <Space>
                <RiseOutlined />
                {t('stats.avgPeakStrength', 'Avg Peak Strength')}
              </Space>
            }
            value={summary?.avg_peak_strength ?? 0}
            precision={2}
            suffix="x"
            styles={{ content: { color: '#fa8c16' } }}
          />
        </Card>
      </Col>

      {/* Distribution by Mark Type */}
      {summary?.by_mark_type && summary.by_mark_type.length > 0 && (
        <Col xs={24} md={12}>
          <Card
            size="small"
            title={
              <Space>
                <BarChartOutlined />
                <span style={{ fontSize: 14 }}>
                  {t('stats.distributionByMark', 'Distribution by Mark Type')}
                </span>
              </Space>
            }
            loading={loading}
          >
            <Space wrap size={[4, 4]}>
              {summary.by_mark_type
                .sort((a, b) => b.count - a.count)
                .map((item) => (
                  <MarkTypeTag
                    key={item.mark_type}
                    markType={item.mark_type}
                    count={item.count}
                    avgStrength={item.avg_strength}
                  />
                ))}
            </Space>
          </Card>
        </Col>
      )}

      {/* Distribution by Cell Type */}
      {summary?.by_cell_type && summary.by_cell_type.length > 0 && (
        <Col xs={24} md={12}>
          <Card
            size="small"
            title={
              <Space>
                <ExperimentOutlined />
                <span style={{ fontSize: 14 }}>
                  {t('stats.distributionByCellType', 'Distribution by Cell Type')}
                </span>
              </Space>
            }
            loading={loading}
          >
            <Space wrap size={[4, 4]}>
              {summary.by_cell_type
                .sort((a, b) => b.count - a.count)
                .map((item) => (
                  <CellTypeTag
                    key={item.cell_type}
                    cellType={item.cell_type}
                    count={item.count}
                  />
                ))}
            </Space>
          </Card>
        </Col>
      )}
    </Row>
  )
}

export default OverlapStatsCards
