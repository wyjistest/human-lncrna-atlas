/**
 * Epigenetic Mark Association Analysis Tab
 *
 * Displays ChIP-seq overlap analysis with:
 * - Statistics cards (total overlaps, by mark type)
 * - Mark distribution bar chart
 * - Data table with pagination
 */

import { useCallback, useMemo, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Space, Button, Select, Tag, message } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ReactECharts from 'echarts-for-react'
import { analysisApi } from '@/api/analysis'
import { useEpigeneticData, useAnalysisSummary } from '@/hooks/useAnalysis'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import echarts from '@/utils/echarts'
import { getChartToolbox } from '@/utils/chart-export'
import { escapeHtml } from '@/utils/escapeHtml'
import type { ECOption } from '@/utils/echarts'
import type { ChIPSeqOverlapRecord } from '@/api/analysis'
import { useSearchParams } from 'react-router-dom'

const HISTONE_MARKS = [
  { value: 'H3K4me1', label: 'H3K4me1', color: '#1890ff', type: 'active' },
  { value: 'H3K4me3', label: 'H3K4me3', color: '#52c41a', type: 'active' },
  { value: 'H3K27ac', label: 'H3K27ac', color: '#faad14', type: 'active' },
  { value: 'H3K36me3', label: 'H3K36me3', color: '#13c2c2', type: 'active' },
  { value: 'H3K9me3', label: 'H3K9me3', color: '#f5222d', type: 'repressive' },
  { value: 'H3K27me3', label: 'H3K27me3', color: '#722ed1', type: 'repressive' },
]

const ALL_HISTONE_MARK_VALUES = HISTONE_MARKS.map((mark) => mark.value)
const ALLOWED_MARK_VALUES = new Set(ALL_HISTONE_MARK_VALUES)

const DEFAULT_PAGE = 1
const MAX_PAGE = 1_000_000

function parseIntParam(value: string | null, min: number, max: number): number | undefined {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return undefined
  if (parsed < min || parsed > max) return undefined
  return parsed
}

export default function EpigeneticTab() {
  const { t } = useTranslation('analysis')

  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseIntParam(searchParams.get('page'), 1, MAX_PAGE) ?? DEFAULT_PAGE
  const [isExporting, setIsExporting] = useState(false)

  const selectedMarks = useMemo(() => {
    const raw = searchParams
      .getAll('mark_names')
      .map(v => v.trim())
      .filter(Boolean)
      .filter(v => ALLOWED_MARK_VALUES.has(v))
    return Array.from(new Set(raw))
  }, [searchParams])

  const pageSize = 20
  const effectiveMarks = selectedMarks.length > 0 ? selectedMarks : ALL_HISTONE_MARK_VALUES

  const updateParams = useCallback((apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }, [setSearchParams])

  // Fetch summary and data
  const { data: summary } = useAnalysisSummary()
  const { data, isLoading, error, refetch } = useEpigeneticData({
    mark_names: effectiveMarks,
    limit: 500,
  })

  // Mark distribution chart
  const markDistributionOption: ECOption = useMemo(() => {
    const byMark = summary?.epigenetic.by_mark
    if (!byMark) return {}

    const marks = effectiveMarks
    const counts = marks.map((mark) => byMark[mark] || 0)

    return {
      title: {
        text: t('epigenetic.charts.markDistribution'),
        left: 'center',
        textStyle: { fontSize: 16, fontWeight: 'bold' },
      },
	      toolbox: getChartToolbox('mark-distribution', t('common.export')),
	      tooltip: {
	        trigger: 'axis',
	        axisPointer: { type: 'shadow' },
	        // SECURITY: ECharts tooltip 默认使用 HTML 渲染，必须对不可信字段做转义防止 XSS
	        formatter: (params: unknown) => {
	          const arr = Array.isArray(params) ? params : [params]
	          const p = arr[0] as { name?: unknown; value?: unknown } | undefined
	          if (!p) return ''
	          const name = escapeHtml(String(p.name ?? ''))
	          const value = typeof p.value === 'number' ? p.value : Number(p.value)
	          const displayValue = Number.isFinite(value) ? value.toLocaleString() : escapeHtml(String(p.value ?? ''))
	          return `<strong>${name}</strong><br/>Overlap Count: ${displayValue}`
	        },
	      },
      xAxis: {
        type: 'category',
        data: marks,
        axisLabel: { rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: 'Overlap Count',
      },
      series: [
        {
          type: 'bar',
          data: counts,
          itemStyle: {
            color: (params: { dataIndex: number }) => {
              const mark = marks[params.dataIndex]
              const markConfig = HISTONE_MARKS.find((m) => m.value === mark)
              return markConfig?.color || '#1890ff'
            },
          },
        },
      ],
      grid: { bottom: 80, left: 60, right: 40 },
    }
  }, [effectiveMarks, summary, t])

  // Table columns
  const columns = [
    {
      title: t('epigenetic.table.lncrna'),
      dataIndex: 'lncrna_name',
      key: 'lncrna_name',
      width: 150,
    },
    {
      title: 'Target',
      dataIndex: 'target_name',
      key: 'target_name',
      width: 120,
    },
    {
      title: t('epigenetic.table.mark'),
      dataIndex: 'mark_name',
      key: 'mark_name',
      width: 120,
      render: (mark: string) => {
        const markConfig = HISTONE_MARKS.find((m) => m.value === mark)
        return (
          <Tag color={markConfig?.color || 'default'}>
            {mark}
          </Tag>
        )
      },
      filters: HISTONE_MARKS.map((mark) => ({ text: mark.label, value: mark.value })),
      onFilter: (value: boolean | React.Key, record: ChIPSeqOverlapRecord) => record.mark_name === value,
    },
    {
      title: t('epigenetic.table.cellType'),
      dataIndex: 'cell_type',
      key: 'cell_type',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('epigenetic.table.peakScore'),
      dataIndex: 'peak_score',
      key: 'peak_score',
      width: 100,
      render: (score: number) => score?.toFixed(1) || '-',
      sorter: (a: ChIPSeqOverlapRecord, b: ChIPSeqOverlapRecord) =>
        (a.peak_score || 0) - (b.peak_score || 0),
    },
    {
      title: t('epigenetic.table.ba'),
      dataIndex: 'binding_affinity',
      key: 'binding_affinity',
      width: 100,
      render: (ba: number) => ba?.toFixed(2) || '-',
      sorter: (a: ChIPSeqOverlapRecord, b: ChIPSeqOverlapRecord) =>
        a.binding_affinity - b.binding_affinity,
    },
  ]

  const handleExport = async () => {
    if (!data?.data?.length) return

    setIsExporting(true)
    try {
      await analysisApi.exportChipseqOverlapsCsv({
        mark_names: effectiveMarks,
        limit: data.total || data.data.length,
      })
    } catch (error) {
      console.error('Epigenetic export failed:', error)
      message.error(t('common.error'))
    } finally {
      setIsExporting(false)
    }
  }

  if (isLoading) return <LoadingState message={t('common.loading')} />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div>
      <p style={{ color: '#666', marginBottom: 24 }}>{t('epigenetic.description')}</p>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.totalOverlaps')}
              value={summary?.epigenetic.total_overlaps || 0}
              styles={{ content: { color: '#1890ff' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.bivalentDomains')}
              value={summary?.epigenetic.bivalent_domains || 0}
              styles={{ content: { color: '#722ed1' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.activeMarks')}
              value={summary?.epigenetic.active_marks || 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('epigenetic.stats.repressiveMarks')}
              value={summary?.epigenetic.repressive_marks || 0}
              styles={{ content: { color: '#f5222d' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Chart */}
      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={16}>
          <Card>
            <ReactECharts
              echarts={echarts}
              option={markDistributionOption}
              style={{ height: 400 }}
              notMerge
              lazyUpdate
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Histone Marks">
            <Space orientation="vertical" style={{ width: '100%' }}>
              {HISTONE_MARKS.map((mark) => (
                <div key={mark.value} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tag color={mark.color}>{mark.label}</Tag>
                  <span style={{ fontSize: 12, color: '#666' }}>
                    {t(`epigenetic.marks.${mark.value}`)}
                  </span>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Filters and Table */}
      <Card title={t('epigenetic.title')} style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>Filter by Mark:</span>
          <Select
            mode="multiple"
            style={{ minWidth: 250 }}
            value={selectedMarks}
            onChange={(value) => {
              updateParams((params) => {
                params.delete('mark_names')
                for (const mark of value) {
                  if (ALLOWED_MARK_VALUES.has(mark)) params.append('mark_names', mark)
                }
                params.delete('page')
              })
            }}
            placeholder="Select marks"
            maxTagCount={2}
          >
            {HISTONE_MARKS.map((mark) => (
              <Select.Option key={mark.value} value={mark.value}>
                <Tag color={mark.color} style={{ marginRight: 4 }}>
                  {mark.label}
                </Tag>
                {mark.type === 'active' ? 'Active' : 'Repressive'}
              </Select.Option>
            ))}
          </Select>
          <Button type="primary" onClick={() => refetch()}>
            {t('common.refresh')}
          </Button>
          <Button
            icon={<DownloadOutlined />}
            loading={isExporting}
            disabled={!data?.data?.length}
            onClick={() => { void handleExport() }}
          >
            {t('common.exportCsv')}
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data?.data || []}
          rowKey={(record) => `${record.regulation_id}-${record.mark_name}-${record.peak_chr}-${record.peak_start}-${record.peak_end}`}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (p) => {
              updateParams((params) => {
                if (p === DEFAULT_PAGE) params.delete('page')
                else params.set('page', String(p))
              })
            },
            showSizeChanger: false,
            showTotal: (total) => t('common.total', { count: total }),
          }}
          scroll={{ x: 700 }}
          size="small"
        />
      </Card>
    </div>
  )
}
