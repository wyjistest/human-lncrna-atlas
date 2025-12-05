/**
 * RepeatMaskerTable Component
 * Displays RepeatMasker annotations for a gene with filtering and statistics
 */
import { useState, useMemo } from 'react'
import {
  Table,
  Select,
  Slider,
  Space,
  Card,
  Statistic,
  Row,
  Col,
  Button,
  message,
  Tag,
  Empty,
  Tooltip
} from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  DownloadOutlined,
  FilterOutlined,
  InfoCircleOutlined
} from '@ant-design/icons'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import type { FilterValue } from 'antd/es/table/interface'
import type { RepeatMaskerFeature, RepeatMaskerFilters } from '@/types/features'
import { featuresApi } from '@/api/features'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { REPEAT_CLASSES, REPEAT_CLASS_COLORS } from '@/types/features'

interface RepeatMaskerTableProps {
  geneId: number
}

const RepeatMaskerTable: React.FC<RepeatMaskerTableProps> = ({ geneId }) => {
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // Filter state
  const [filters, setFilters] = useState<RepeatMaskerFilters>({
    page: 1,
    page_size: 20
  })

  // Divergence range for slider
  const [divergenceRange, setDivergenceRange] = useState<[number, number]>([0, 50])

  // Query RepeatMasker data
  const {
    data: repeatsData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['gene-repeats', geneId, filters],
    queryFn: async () => {
      const response = await featuresApi.getGeneRepeats(geneId, filters)
      return response.data
    },
    staleTime: 30 * 60 * 1000, // 30 minutes
    enabled: geneId > 0
  })

  // Query statistics
  const { data: statsData } = useQuery({
    queryKey: ['gene-repeat-stats', geneId],
    queryFn: async () => {
      const response = await featuresApi.getGeneRepeatStats(geneId)
      return response.data
    },
    staleTime: 30 * 60 * 1000,
    enabled: geneId > 0
  })

  // Get color for repeat class
  const getRepeatClassColor = (repeatClass: string): string => {
    return REPEAT_CLASS_COLORS[repeatClass] || REPEAT_CLASS_COLORS.Unknown
  }

  // Table columns definition
  const columns: ColumnsType<RepeatMaskerFeature> = useMemo(() => [
    {
      title: t('detail.repeats.repeatName'),
      dataIndex: 'repeat_name',
      key: 'repeat_name',
      width: 150,
      ellipsis: true,
      render: (name: string) => (
        <Tooltip title={name}>
          <span style={{ fontFamily: 'monospace' }}>{name}</span>
        </Tooltip>
      )
    },
    {
      title: t('detail.repeats.class'),
      dataIndex: 'repeat_class',
      key: 'repeat_class',
      width: 120,
      render: (cls: string) => (
        <Tag color={getRepeatClassColor(cls)} style={{ minWidth: 60, textAlign: 'center' }}>
          {cls}
        </Tag>
      ),
      filters: REPEAT_CLASSES.map(rc => ({
        text: rc.label,
        value: rc.value
      })),
      onFilter: (value, record) => record.repeat_class === value
    },
    {
      title: t('detail.repeats.family'),
      dataIndex: 'repeat_family',
      key: 'repeat_family',
      width: 120,
      ellipsis: true,
      render: (family: string) => (
        <Tooltip title={family}>
          <span>{family}</span>
        </Tooltip>
      )
    },
    {
      title: t('detail.repeats.chromosome'),
      dataIndex: 'chromosome',
      key: 'chromosome',
      width: 100,
      render: (chr: string) => (
        <span style={{ fontFamily: 'monospace' }}>{chr}</span>
      )
    },
    {
      title: t('detail.repeats.start'),
      dataIndex: 'start',
      key: 'start',
      width: 120,
      align: 'right',
      render: (val: number) => (
        <span style={{ fontFamily: 'monospace' }}>
          {val?.toLocaleString() ?? '-'}
        </span>
      ),
      sorter: (a, b) => a.start - b.start
    },
    {
      title: t('detail.repeats.end'),
      dataIndex: 'end',
      key: 'end',
      width: 120,
      align: 'right',
      render: (val: number) => (
        <span style={{ fontFamily: 'monospace' }}>
          {val?.toLocaleString() ?? '-'}
        </span>
      ),
      sorter: (a, b) => a.end - b.end
    },
    {
      title: (
        <Tooltip title={t('detail.repeats.divergenceTooltip')}>
          <span>
            {t('detail.repeats.divergence')} <InfoCircleOutlined />
          </span>
        </Tooltip>
      ),
      dataIndex: 'divergence',
      key: 'divergence',
      width: 100,
      align: 'right',
      render: (val: number) => {
        const color = val < 10 ? '#52c41a' : val < 25 ? '#faad14' : '#f5222d'
        return (
          <span style={{ color, fontWeight: 500 }}>
            {val?.toFixed(1) ?? '-'}%
          </span>
        )
      },
      sorter: (a, b) => a.divergence - b.divergence
    },
    {
      title: t('detail.repeats.strand'),
      dataIndex: 'strand',
      key: 'strand',
      width: 80,
      align: 'center',
      render: (strand: string) => (
        <Tag color={strand === '+' ? 'blue' : strand === '-' ? 'red' : 'default'}>
          {strand || '.'}
        </Tag>
      )
    }
  ], [t])

  // Handle pagination change
  const handleTableChange = (
    pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>
  ) => {
    setFilters(prev => ({
      ...prev,
      page: pagination.current || 1,
      page_size: pagination.pageSize || 20
    }))
  }

  // Handle divergence slider change
  const handleDivergenceChange = (value: number[]) => {
    setDivergenceRange(value as [number, number])
  }

  // Apply divergence filter
  const applyDivergenceFilter = () => {
    setFilters(prev => ({
      ...prev,
      min_divergence: divergenceRange[0],
      max_divergence: divergenceRange[1],
      page: 1
    }))
  }

  // Handle repeat class filter
  const handleClassChange = (value: string | undefined) => {
    setFilters(prev => ({
      ...prev,
      repeat_class: value,
      page: 1
    }))
  }

  // Handle export
  const handleExport = () => {
    featuresApi.exportRepeatsToBED(geneId, filters)
    message.success(t('detail.repeats.exportSuccess'))
  }

  // Reset filters
  const resetFilters = () => {
    setFilters({
      page: 1,
      page_size: 20
    })
    setDivergenceRange([0, 50])
  }

  // Loading state
  if (isLoading) {
    return <LoadingState />
  }

  // Error state
  if (error) {
    return <ErrorState error={error} onRetry={() => refetch()} />
  }

  // No data state
  if (!repeatsData || repeatsData.total === 0) {
    return (
      <Empty
        description={t('detail.repeats.noRepeats')}
        style={{ padding: 48 }}
      />
    )
  }

  const { items, total, page, page_size } = repeatsData

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Statistics Cards */}
      {statsData && (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Card size="small" hoverable>
              <Statistic
                title={t('detail.repeats.totalCount')}
                value={statsData.total_count}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small" hoverable>
              <Statistic
                title={t('detail.repeats.avgDivergence')}
                value={statsData.avg_divergence}
                suffix="%"
                precision={1}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card
              size="small"
              title={
                <span style={{ fontSize: 14 }}>
                  {t('detail.repeats.classDistribution')}
                </span>
              }
            >
              <Space wrap size={[8, 8]}>
                {statsData?.class_distribution &&
                  Object.entries(statsData.class_distribution)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cls, count]) => (
                      <Tag
                      key={cls}
                      color={getRepeatClassColor(cls)}
                      style={{ margin: 0 }}
                    >
                      {cls}: {count}
                    </Tag>
                  ))}
              </Space>
            </Card>
          </Col>
        </Row>
      )}

      {/* Filters Card */}
      <Card
        title={
          <Space>
            <FilterOutlined />
            <span>{t('detail.repeats.filters')}</span>
          </Space>
        }
        size="small"
        extra={
          <Button size="small" onClick={resetFilters}>
            {tCommon('action.reset')}
          </Button>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} sm={12} md={8}>
              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                <span style={{ fontWeight: 500 }}>{t('detail.repeats.repeatClass')}:</span>
                <Select
                  style={{ width: '100%' }}
                  placeholder={tCommon('placeholder.select')}
                  allowClear
                  value={filters.repeat_class}
                  onChange={handleClassChange}
                  options={REPEAT_CLASSES}
                />
              </Space>
            </Col>
            <Col xs={24} sm={12} md={12}>
              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                <span style={{ fontWeight: 500 }}>
                  {t('detail.repeats.divergence')}: {divergenceRange[0]}% - {divergenceRange[1]}%
                </span>
                <Space style={{ width: '100%' }}>
                  <Slider
                    range
                    style={{ width: 200 }}
                    min={0}
                    max={50}
                    step={1}
                    value={divergenceRange}
                    onChange={handleDivergenceChange}
                    tooltip={{ formatter: (val) => `${val}%` }}
                  />
                  <Button size="small" type="primary" onClick={applyDivergenceFilter}>
                    {tCommon('action.apply')}
                  </Button>
                </Space>
              </Space>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* Data Table */}
      <Card
        title={
          <span>
            {t('detail.repeats.title')} ({total.toLocaleString()})
          </span>
        }
        extra={
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
            disabled={total === 0}
          >
            {t('detail.repeats.exportBED')}
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={items}
          rowKey="feature_id"
          pagination={{
            current: page,
            pageSize: page_size,
            total: total,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            showTotal: (total, range) =>
              `${range[0]}-${range[1]} / ${total.toLocaleString()} ${tCommon('unit.records')}`,
            showQuickJumper: total > 100
          }}
          onChange={handleTableChange}
          scroll={{ x: 1000 }}
          size="middle"
        />
      </Card>
    </Space>
  )
}

export default RepeatMaskerTable
export { RepeatMaskerTable }
