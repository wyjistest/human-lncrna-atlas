import { useRef, useState, useMemo, useCallback } from 'react'
import { Card, Row, Col, Statistic, Spin, Alert, Button, Dropdown, Space, message } from 'antd'
import { DownloadOutlined, DownOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useStats } from '@/hooks/useStats'
import { useDetailedStats } from '@/hooks/useDetailedStats'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { SpeciesChart } from './components/SpeciesChart'
import { BAChart } from './components/BAChart'
import { TopLncRNAChart } from './components/TopLncRNAChart'
import { exportToPDF } from '@/utils/pdf-export'

export default function Stats() {
  const { data: overviewData, isLoading: overviewLoading, error: overviewError } = useStats()
  const { data: detailedData, isLoading: detailedLoading, error: detailedError } = useDetailedStats()
  const reportRef = useRef<HTMLDivElement>(null)
  const [exporting, setExporting] = useState(false)
  const { t } = useTranslation('stats')

  // 导出 PDF 报告（使用 useCallback 避免 stale closure）
  const handleExportPDF = useCallback(async () => {
    if (!reportRef.current) {
      message.warning(t('export.notReady'))
      return
    }

    setExporting(true)
    const success = await exportToPDF(reportRef.current, {
      title: t('export.pdfTitle'),
      filename: t('export.pdfFilename')
    })
    setExporting(false)

    if (success) {
      message.success(t('export.success'))
    } else {
      message.error(t('export.failed'))
    }
  }, [t])

  const exportMenuItems: MenuProps['items'] = useMemo(() => [
    {
      key: 'pdf',
      label: t('export.pdf'),
      onClick: handleExportPDF
    }
  ], [t, handleExportPDF])

  if (overviewLoading) return <LoadingState />
  if (overviewError) return <ErrorState error={overviewError} />

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{t('title')}</h1>
        <Dropdown menu={{ items: exportMenuItems }} disabled={exporting || detailedLoading}>
          <Button icon={<DownloadOutlined />} loading={exporting}>
            {t('exportReport')} <DownOutlined />
          </Button>
        </Dropdown>
      </Space>

      {/* 报告内容区域 */}
      <div ref={reportRef}>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginTop: 24, marginBottom: 32 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title={t('cards.totalGenes')} value={overviewData?.total_genes} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title={t('cards.lncRNA')} value={overviewData?.total_lncrna} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title={t('cards.regulations')} value={overviewData?.total_regulations} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title={t('cards.diseaseAssociations')} value={overviewData?.total_trait_associations} />
          </Card>
        </Col>
      </Row>

      {/* 图表区域 */}
      {detailedLoading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>{t('loading')}</p>
        </div>
      )}

      {detailedError && (
        <Alert
          type="warning"
          message={t('loadError.title')}
          description={t('loadError.desc')}
          style={{ marginBottom: 24 }}
        />
      )}

      {detailedData && (
        <>
          {/* 数据分布 */}
          <h2 style={{ marginBottom: 16 }}>{t('sections.distribution')}</h2>
          <Row gutter={16} style={{ marginBottom: 32 }}>
            <Col xs={24} lg={12}>
              <Card>
                <SpeciesChart data={detailedData.species_distribution} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card>
                <BAChart data={detailedData.ba_distribution} />
              </Card>
            </Col>
          </Row>

          {/* Top 排行榜 */}
          <h2 style={{ marginBottom: 16 }}>{t('sections.topRankings')}</h2>
          <Row gutter={16}>
            <Col xs={24} xl={16}>
              <Card>
                <TopLncRNAChart data={detailedData.top_lncrnas} />
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card title={t('sections.baRange')} style={{ height: '100%' }}>
                <Statistic
                  title={t('baStats.min')}
                  value={detailedData.ba_range.min_ba}
                  precision={2}
                />
                <Statistic
                  title={t('baStats.max')}
                  value={detailedData.ba_range.max_ba}
                  precision={2}
                  style={{ marginTop: 16 }}
                />
                <Statistic
                  title={t('baStats.avg')}
                  value={detailedData.ba_range.avg_ba}
                  precision={2}
                  style={{ marginTop: 16 }}
                />
                <Statistic
                  title={t('baStats.totalCount')}
                  value={detailedData.ba_range.total_count}
                  style={{ marginTop: 16 }}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
      </div>
    </div>
  )
}
