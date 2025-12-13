import { useState, useMemo, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Dropdown, Space, message, Modal, Progress } from 'antd'
import { DownloadOutlined, ExperimentOutlined } from '@ant-design/icons'
import type { TableProps, MenuProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useRegulations, usePrefetchRegulations } from '@/hooks/useRegulations'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { AdvancedFilters, type FilterState } from './components/AdvancedFilters'
import { SelectionToolbar } from './components/SelectionToolbar'
import { BatchVisualizationModal } from './components/BatchVisualizationModal'
import { exportRegulations, exportSelectedRegulations, shouldShowExportWarning, isExportLimitExceeded } from '@/utils/export'
import { EXPORT_LIMITS } from '@/config/constants'
import type { components } from '@/types'

type RegulationListItem = components['schemas']['RegulationListItem']

export default function Regulations() {
  const navigate = useNavigate()
  const { t } = useTranslation('regulations')
  const { t: tc } = useTranslation('common')
  const { t: tGB } = useTranslation('genomeBrowser')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [filters, setFilters] = useState<FilterState>({})
  const [exporting, setExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState(0)

  // 行选择状态
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [selectedRows, setSelectedRows] = useState<RegulationListItem[]>([])

  // 可视化弹窗状态
  const [visualizeOpen, setVisualizeOpen] = useState(false)

  // 转换筛选器状态为 API 参数
  // 注意：BA 范围在 AdvancedFilters 中已自动交换，始终保证 min <= max
  // 使用 useMemo 包裹以避免每次渲染创建新对象，防止 useEffect 无效触发
  const apiParams = useMemo(() => ({
    page,
    page_size: pageSize,
    min_ba: filters.min_ba,
    max_ba: filters.max_ba,
    // 数组转逗号分隔字符串
    species_ids: filters.species_ids?.join(','),
    chromosomes: filters.chromosomes?.join(','),
    lncrna_gene_name: filters.lncrna_gene_name,
    target_gene_name: filters.target_gene_name,
  }), [
    page,
    pageSize,
    filters.min_ba,
    filters.max_ba,
    filters.species_ids,
    filters.chromosomes,
    filters.lncrna_gene_name,
    filters.target_gene_name,
  ])

  const { data, isLoading, error } = useRegulations(apiParams)

  // 预加载相邻页
  const prefetchRegulations = usePrefetchRegulations()

  // 当前页加载完成后，预加载下一页和上一页
  useEffect(() => {
    if (data) {
      const totalPages = Math.ceil((data.total || 0) / pageSize)

      // 预加载下一页
      if (page < totalPages) {
        prefetchRegulations({ ...apiParams, page: page + 1 })
      }

      // 预加载上一页（用户可能回退）
      if (page > 1) {
        prefetchRegulations({ ...apiParams, page: page - 1 })
      }
    }
  }, [data, page, pageSize, apiParams, prefetchRegulations])

  // 更新单个筛选器
  const updateFilter = (key: keyof FilterState, value: unknown) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1)
  }

  // 重置筛选器
  const resetFilters = () => {
    setFilters({})
    setPage(1)
  }

  // 导出功能（使用 useCallback 避免 stale closure）
  const handleExport = useCallback(async (format: 'csv' | 'xlsx') => {
    const total = data?.total || 0

    if (total === 0) {
      message.warning(t('export.noData'))
      return
    }

    // 检查是否超过限制
    if (isExportLimitExceeded(total)) {
      Modal.warning({
        title: t('export.tooLarge.title'),
        content: t('export.tooLarge.content', { total, limit: EXPORT_LIMITS.MAX_FRONTEND }),
        okText: tc('action.confirm')
      })
      return
    }

    // 大数据量警告
    if (shouldShowExportWarning(total)) {
      const confirmed = await new Promise<boolean>(resolve => {
        Modal.confirm({
          title: t('export.warning.title'),
          content: t('export.warning.content', { total }),
          okText: t('export.warning.continue'),
          cancelText: tc('action.cancel'),
          onOk: () => resolve(true),
          onCancel: () => resolve(false)
        })
      })
      if (!confirmed) return
    }

    setExporting(true)
    setExportProgress(0)

    // 使用与查询相同的筛选参数（不包含分页）
    const exportFilters = {
      min_ba: filters.min_ba,
      max_ba: filters.max_ba,
      species_ids: filters.species_ids?.join(','),
      chromosomes: filters.chromosomes?.join(','),
      lncrna_gene_name: filters.lncrna_gene_name,
      target_gene_name: filters.target_gene_name,
    }

    const result = await exportRegulations(
      exportFilters,
      format,
      total,
      (current, total) => {
        setExportProgress(Math.round((current / total) * 100))
      }
    )

    setExporting(false)
    setExportProgress(0)

    if (!result.success) {
      message.error(result.message || t('export.failed'))
    } else {
      message.success(t('export.success'))
    }
  }, [data?.total, filters, t, tc])

  // 批量导出选中行
  const handleBatchExport = async (format: 'csv' | 'xlsx') => {
    if (selectedRows.length === 0) {
      message.warning(t('selection.selectFirst'))
      return
    }

    // 双重校验：UI 已禁用按钮，此处再次防护
    if (selectedRows.length > EXPORT_LIMITS.MAX_FRONTEND) {
      message.error(t('selection.tooMany', { count: selectedRows.length, limit: EXPORT_LIMITS.MAX_FRONTEND }))
      return
    }

    setExporting(true)
    const result = await exportSelectedRegulations(selectedRows, format)
    setExporting(false)

    if (result.success) {
      message.success(t('selection.exportSuccess', { count: selectedRows.length }))
    } else {
      message.error(result.message || t('export.failed'))
    }
  }

  // 清空选择
  const handleClearSelection = () => {
    setSelectedRowKeys([])
    setSelectedRows([])
  }

  // 行选择配置
  const rowSelection: TableProps<RegulationListItem>['rowSelection'] = {
    type: 'checkbox',
    selectedRowKeys,
    onChange: (keys, rows) => {
      setSelectedRowKeys(keys)
      setSelectedRows(rows)
    },
    preserveSelectedRowKeys: true,
    columnWidth: 48,
    selections: [
      Table.SELECTION_ALL,
      Table.SELECTION_INVERT,
      Table.SELECTION_NONE
    ]
  }

  const exportMenuItems: MenuProps['items'] = useMemo(() => [
    {
      key: 'csv',
      label: t('export.csv'),
      onClick: () => handleExport('csv')
    },
    {
      key: 'xlsx',
      label: t('export.xlsx'),
      onClick: () => handleExport('xlsx')
    }
  ], [t, handleExport])

  // Navigate to IGV genome browser with gene name
  // Use gene mode to load regulation/interaction tracks for the lncRNA
  const handleViewInIGV = useCallback((record: RegulationListItem) => {
    const { lncrna_gene_name, species_id } = record

    if (lncrna_gene_name) {
      // Use gene parameter to load gene-specific IGV config with regulation/interaction tracks
      navigate(`/genome-browser?gene=${encodeURIComponent(lncrna_gene_name)}&species=${species_id}`)
    }
  }, [navigate])

  const columns: TableProps<RegulationListItem>['columns'] = useMemo(() => [
    { title: t('columns.id'), dataIndex: 'regulation_id', width: 100 },
    { title: t('columns.lncrna'), dataIndex: 'lncrna_gene_name', width: 150 },
    { title: t('columns.targetGene'), dataIndex: 'target_gene_name', width: 150 },
    { title: t('columns.species'), dataIndex: 'species_name', width: 100 },
    { title: t('columns.chr'), dataIndex: 'target_chromosome', width: 80 },
    { title: t('columns.start'), dataIndex: 'target_start', width: 120 },
    { title: t('columns.end'), dataIndex: 'target_end', width: 120 },
    { title: t('columns.ba'), dataIndex: 'binding_affinity', width: 100 },
    { title: t('columns.peaks'), dataIndex: 'num_peaks', width: 80 },
    {
      title: t('columns.action'),
      key: 'action',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, record: RegulationListItem) => (
        <Button
          type="link"
          size="small"
          icon={<ExperimentOutlined />}
          onClick={() => handleViewInIGV(record)}
          title={tGB('viewInIGV')}
        >
          IGV
        </Button>
      ),
    },
  ], [t, handleViewInIGV, tGB])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{t('title')}</h1>
        <Dropdown menu={{ items: exportMenuItems }} disabled={exporting}>
          <Button icon={<DownloadOutlined />} loading={exporting}>
            {exporting ? t('export.exporting', { percent: exportProgress }) : t('export.button')}
          </Button>
        </Dropdown>
      </Space>

      <AdvancedFilters
        filters={filters}
        onFilterChange={updateFilter}
        onReset={resetFilters}
      />

      {/* 选择工具栏 */}
      <SelectionToolbar
        selectedCount={selectedRowKeys.length}
        selectedRows={selectedRows}
        onClear={handleClearSelection}
        onExport={handleBatchExport}
        onVisualize={() => setVisualizeOpen(true)}
        loading={exporting}
      />

      {/* 导出进度条 */}
      {exporting && (
        <Progress
          percent={exportProgress}
          status="active"
          style={{ marginBottom: 16 }}
        />
      )}

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={data?.items}
        rowKey="regulation_id"
        pagination={{
          current: page,
          pageSize,
          total: data?.total,
          showSizeChanger: true,
          showTotal: (total) => t('pagination.total', { count: total }),
          onChange: (p, ps) => {
            // 当 pageSize 改变时，重置到第一页避免竞态条件
            if (ps !== pageSize) {
              setPage(1)
              setPageSize(ps)
            } else {
              setPage(p)
            }
          },
        }}
      />

      {/* 批量可视化弹窗 */}
      <BatchVisualizationModal
        open={visualizeOpen}
        onClose={() => setVisualizeOpen(false)}
        data={selectedRows}
      />
    </div>
  )
}
