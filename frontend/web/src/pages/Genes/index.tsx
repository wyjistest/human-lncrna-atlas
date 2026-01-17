import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Key } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { DownloadOutlined } from '@ant-design/icons'
import { Alert, Button, Input, InputNumber, Select, Space, Table, Tabs, message } from 'antd'
import type { TableProps } from 'antd'
import { saveAs } from 'file-saver'
import { useTranslation } from 'react-i18next'
import { genesApi, type GeneBatchResolveRequest } from '@/api/genes'
import { useGenes, usePrefetchGenes } from '@/hooks/useGenes'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import type { components } from '@/types'
import { escapeCSV } from '@/utils/csv'
import { createTimestampedFilename } from '@/utils/exportUtils'
import { createSpeciesTranslator } from '@/utils/species'

type GeneListItem = components['schemas']['GeneListItem']

type ActiveTab = 'browse' | 'batch'
type HasRegulationFilter = 'all' | 'with' | 'without'

const BATCH_MAX_IDENTIFIERS = 200

function parseBatchIdentifiers(input: string): string[] {
  return Array.from(
    new Set(
      input
        .split(/[\s,;]+/g)
        .map(v => v.trim())
        .filter(Boolean)
    )
  )
}

export default function Genes() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<ActiveTab>('browse')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)

  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState<string>()
  const [geneType, setGeneType] = useState<string>()
  const [speciesId, setSpeciesId] = useState<number>()
  const [chromosome, setChromosome] = useState<string>()
  const [hasRegulation, setHasRegulation] = useState<HasRegulationFilter>('all')
  const [minRegulationCount, setMinRegulationCount] = useState<number>()

  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([])
  const [selectedRows, setSelectedRows] = useState<GeneListItem[]>([])

  const [batchInput, setBatchInput] = useState('')
  const [batchResults, setBatchResults] = useState<GeneListItem[]>([])
  const [batchMissing, setBatchMissing] = useState<string[]>([])

  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  const translateSpecies = useMemo(() => createSpeciesTranslator(tCommon), [tCommon])

  const speciesOptions = useMemo(() => ([
    { label: tCommon('species.human'), value: 1 },
    { label: tCommon('species.chimpanzee'), value: 2 },
    { label: tCommon('species.macaque'), value: 3 },
    { label: tCommon('species.marmoset'), value: 4 },
  ]), [tCommon])

  const apiParams = useMemo(() => ({
    page,
    page_size: pageSize,
    search,
    gene_type: geneType || undefined,
    species_id: speciesId,
    chromosome: chromosome || undefined,
    has_regulation: hasRegulation === 'all' ? undefined : hasRegulation === 'with',
    min_regulation_count: minRegulationCount,
  }), [
    page,
    pageSize,
    search,
    geneType,
    speciesId,
    chromosome,
    hasRegulation,
    minRegulationCount,
  ])

  const { data, isLoading, error } = useGenes(apiParams, { enabled: activeTab === 'browse' })

  const prefetchGenes = usePrefetchGenes()
  useEffect(() => {
    if (activeTab !== 'browse' || !data) return

    const totalPages = Math.ceil((data.total || 0) / pageSize)
    if (page < totalPages) prefetchGenes({ ...apiParams, page: page + 1 })
    if (page > 1) prefetchGenes({ ...apiParams, page: page - 1 })
  }, [activeTab, apiParams, data, page, pageSize, prefetchGenes])

  const clearSelection = useCallback(() => {
    setSelectedRowKeys([])
    setSelectedRows([])
  }, [])

  useEffect(() => {
    clearSelection()
  }, [activeTab, clearSelection])

  const batchResolve = useMutation({
    mutationFn: (payload: GeneBatchResolveRequest) => genesApi.batchResolve(payload),
    onSuccess: (res) => {
      setBatchResults(res.items)
      setBatchMissing(res.missing)
      clearSelection()
      if (res.missing.length > 0) {
        message.warning(t('batch.missingWarning', { count: res.missing.length }))
      }
    },
    onError: () => {
      message.error(tCommon('error.loadFailed'))
    },
  })

  const handleResetFilters = useCallback(() => {
    setSearchInput('')
    setSearch(undefined)
    setGeneType(undefined)
    setSpeciesId(undefined)
    setChromosome(undefined)
    setHasRegulation('all')
    setMinRegulationCount(undefined)
    setPage(1)
  }, [])

  const handleClearBatch = useCallback(() => {
    setBatchInput('')
    setBatchResults([])
    setBatchMissing([])
    clearSelection()
  }, [clearSelection])

  const handleRunBatch = useCallback(() => {
    const identifiers = parseBatchIdentifiers(batchInput)
    if (identifiers.length === 0) {
      message.warning(t('batch.empty'))
      return
    }
    if (identifiers.length > BATCH_MAX_IDENTIFIERS) {
      message.error(t('batch.tooMany', { max: BATCH_MAX_IDENTIFIERS }))
      return
    }

    batchResolve.mutate({
      identifiers,
      species_id: speciesId,
      gene_type: geneType,
    })
  }, [batchInput, batchResolve, geneType, speciesId, t])

  const exportToCsv = useCallback((rows: GeneListItem[]) => {
    const headers = [
      'gene_id',
      'core_id',
      'gene_name',
      'gene_ensembl_id',
      'gene_type',
      'species_name',
      'chromosome',
      'gene_start',
      'gene_end',
      'regulation_count',
    ]

    const lines = rows.map(r => ([
      escapeCSV(r.gene_id),
      escapeCSV(r.core_id),
      escapeCSV(r.gene_name ?? ''),
      escapeCSV(r.gene_ensembl_id ?? ''),
      escapeCSV(r.gene_type),
      escapeCSV(r.species_name),
      escapeCSV(r.chromosome ?? ''),
      escapeCSV(r.gene_start ?? ''),
      escapeCSV(r.gene_end ?? ''),
      escapeCSV(r.regulation_count ?? 0),
    ]).join(','))

    const csv = [headers.join(','), ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    saveAs(blob, `${createTimestampedFilename('genes')}.csv`)
  }, [])

  const tableData = activeTab === 'batch' ? batchResults : data?.items
  const exportRows = useMemo(
    () => (selectedRows.length > 0 ? selectedRows : (tableData || [])),
    [selectedRows, tableData]
  )

  const handleExportCsv = useCallback(() => {
    if (exportRows.length === 0) {
      message.warning(t('export.noData'))
      return
    }
    exportToCsv(exportRows)
    message.success(t('export.started'))
  }, [exportRows, exportToCsv, t])

  const handleSearch = useCallback((value: string) => {
    const next = value.trim()
    setSearch(next || undefined)
    setPage(1)
  }, [])

  const columns: TableProps<GeneListItem>['columns'] = useMemo(() => [
    {
      title: t('columns.geneName'),
      width: 200,
      render: (_, record) => record.gene_name || record.gene_id
    },
    { title: t('columns.ensemblId'), dataIndex: 'gene_ensembl_id', width: 180 },
    {
      title: t('columns.ensemblLink'),
      width: 150,
      render: (_, record) => {
        if (record.gene_ensembl_id?.startsWith('ENSG')) {
          const cleanId = record.gene_ensembl_id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')
          return (
            <a
              href={`https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${cleanId}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#1890ff' }}
            >
              {t('link.view', { ns: 'common' })}
            </a>
          )
        }
        return <span style={{ color: '#999' }}>{t('link.notAvailable', { ns: 'common' })}</span>
      }
    },
    {
      title: t('columns.fantomLink'),
      width: 170,
      render: (_, record) => {
        if (record.gene_ensembl_id) {
          const cleanId = record.gene_ensembl_id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')
          return (
            <a
              href={`https://fantom.gsc.riken.jp/cat/v1/#/genes/${cleanId}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#1890ff' }}
            >
              {t('link.view', { ns: 'common' })}
            </a>
          )
        }
        return <span style={{ color: '#999' }}>{t('link.notAvailable', { ns: 'common' })}</span>
      }
    },
    { title: t('columns.type'), dataIndex: 'gene_type', width: 120 },
    {
      title: t('columns.species'),
      dataIndex: 'species_name',
      width: 120,
      render: (speciesName: string) => translateSpecies(speciesName)
    },
    { title: t('columns.chromosome'), dataIndex: 'chromosome', width: 100 },
    { title: t('columns.start'), dataIndex: 'gene_start', width: 120 },
    { title: t('columns.end'), dataIndex: 'gene_end', width: 120 },
    { title: t('columns.regulations'), dataIndex: 'regulation_count', width: 100 },
    {
      title: tCommon('action.view'),
      key: 'actions',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, record: GeneListItem) => (
        <Button
          type="link"
          size="small"
          onClick={() => navigate(`/genes/${record.gene_id}`)}
        >
          {tCommon('link.view')}
        </Button>
      )
    },
  ], [t, tCommon, navigate, translateSpecies])

  if (activeTab === 'browse' && isLoading) return <LoadingState />
  if (activeTab === 'browse' && error) return <ErrorState error={error} />

  const rowSelection: TableProps<GeneListItem>['rowSelection'] = {
    selectedRowKeys,
    onChange: (keys, rows) => {
      setSelectedRowKeys(keys)
      setSelectedRows(rows)
    },
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{t('title')}</h1>
        <Button icon={<DownloadOutlined />} onClick={handleExportCsv}>
          {t('export.csv')}
        </Button>
      </Space>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key as ActiveTab)
          setPage(1)
        }}
        items={[
          {
            key: 'browse',
            label: t('tabs.browse'),
            children: (
              <Space wrap style={{ marginBottom: 16 }}>
                <Input.Search
                  placeholder={t('search.placeholder')}
                  value={searchInput}
                  onChange={(e) => {
                    const next = e.target.value
                    setSearchInput(next)
                    if (next === '') {
                      setSearch(undefined)
                      setPage(1)
                    }
                  }}
                  onSearch={handleSearch}
                  style={{ width: 260 }}
                  allowClear
                />
                <Select
                  placeholder={t('search.geneType')}
                  style={{ width: 160 }}
                  value={geneType}
                  onChange={(value) => {
                    setGeneType(value)
                    setPage(1)
                  }}
                  allowClear
                  options={[
                    { label: t('geneTypes.lncRNA'), value: 'lncRNA' },
                    { label: t('geneTypes.proteinCoding'), value: 'protein_coding' },
                  ]}
                />
                <Select
                  placeholder={t('filters.species')}
                  style={{ width: 160 }}
                  value={speciesId}
                  onChange={(value) => {
                    setSpeciesId(value)
                    setPage(1)
                  }}
                  allowClear
                  options={speciesOptions}
                />
                <Input
                  placeholder={t('filters.chromosome')}
                  style={{ width: 140 }}
                  value={chromosome}
                  onChange={(e) => {
                    setChromosome(e.target.value || undefined)
                    setPage(1)
                  }}
                  allowClear
                />
                <Select
                  placeholder={t('filters.hasRegulation')}
                  style={{ width: 200 }}
                  value={hasRegulation}
                  onChange={(value) => {
                    setHasRegulation(value)
                    setPage(1)
                  }}
                  options={[
                    { label: t('filters.hasRegulationAll'), value: 'all' },
                    { label: t('filters.hasRegulationYes'), value: 'with' },
                    { label: t('filters.hasRegulationNo'), value: 'without' },
                  ]}
                />
                <InputNumber
                  placeholder={t('filters.minRegulationCount')}
                  style={{ width: 200 }}
                  min={0}
                  value={minRegulationCount}
                  onChange={(value) => {
                    setMinRegulationCount(value ?? undefined)
                    setPage(1)
                  }}
                />
                <Button onClick={handleResetFilters}>
                  {tCommon('action.reset')}
                </Button>
              </Space>
            ),
          },
          {
            key: 'batch',
            label: t('tabs.batch'),
            children: (
              <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
                <Space wrap>
                  <Select
                    placeholder={t('filters.species')}
                    style={{ width: 160 }}
                    value={speciesId}
                    onChange={(value) => setSpeciesId(value)}
                    allowClear
                    options={speciesOptions}
                  />
                  <Select
                    placeholder={t('search.geneType')}
                    style={{ width: 160 }}
                    value={geneType}
                    onChange={(value) => setGeneType(value)}
                    allowClear
                    options={[
                      { label: t('geneTypes.lncRNA'), value: 'lncRNA' },
                      { label: t('geneTypes.proteinCoding'), value: 'protein_coding' },
                    ]}
                  />
                </Space>

                <Input.TextArea
                  value={batchInput}
                  onChange={(e) => setBatchInput(e.target.value)}
                  placeholder={t('batch.placeholder')}
                  rows={6}
                />

                <Space>
                  <Button type="primary" loading={batchResolve.isPending} onClick={handleRunBatch}>
                    {t('batch.run')}
                  </Button>
                  <Button onClick={handleClearBatch}>
                    {tCommon('action.clear')}
                  </Button>
                </Space>

                {(batchResults.length > 0 || batchMissing.length > 0) && (
                  <Alert
                    type={batchMissing.length > 0 ? 'warning' : 'success'}
                    showIcon
                    message={t('batch.summary', { matched: batchResults.length, missing: batchMissing.length })}
                  />
                )}
              </Space>
            ),
          },
        ]}
      />

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={tableData}
        rowKey="gene_id"
        loading={activeTab === 'batch' ? batchResolve.isPending : isLoading}
        pagination={activeTab === 'browse' ? {
          current: page,
          pageSize,
          total: data?.total,
          showSizeChanger: true,
          showTotal: (total) => t('pagination.total', { count: total }),
          onChange: (p, ps) => {
            if (ps !== pageSize) {
              setPage(1)
              setPageSize(ps)
            } else {
              setPage(p)
            }
          },
        } : false}
      />
    </div>
  )
}
