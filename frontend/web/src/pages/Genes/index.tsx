import { cloneElement, isValidElement, useCallback, useEffect, useMemo, useState } from 'react'
import type { Key, ReactElement } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
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

const DEFAULT_PAGE = 1
const DEFAULT_PAGE_SIZE = 100
const MAX_PAGE_SIZE = 1000
const MAX_PAGE = 1_000_000
const BATCH_MAX_IDENTIFIERS = 200

function parseIntParam(value: string | null, min: number, max: number): number | undefined {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return undefined
  if (parsed < min || parsed > max) return undefined
  return parsed
}

function parseGeneType(value: string | null): string | undefined {
  if (!value) return undefined
  if (value === 'lncRNA' || value === 'protein_coding') return value
  return undefined
}

function parseSpeciesId(value: string | null): number | undefined {
  const parsed = parseIntParam(value, 1, 4)
  if (!parsed) return undefined
  return parsed
}

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
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTab: ActiveTab = searchParams.get('tab') === 'batch' ? 'batch' : 'browse'
  const page = parseIntParam(searchParams.get('page'), 1, MAX_PAGE) ?? DEFAULT_PAGE
  const pageSize = parseIntParam(searchParams.get('page_size'), 1, MAX_PAGE_SIZE) ?? DEFAULT_PAGE_SIZE
  const search = searchParams.get('search')?.trim() || undefined
  const geneType = parseGeneType(searchParams.get('gene_type'))
  const speciesId = parseSpeciesId(searchParams.get('species_id'))
  const chromosome = searchParams.get('chromosome')?.trim() || undefined
  const hasRegulationParam = searchParams.get('has_regulation')
  const hasRegulation: HasRegulationFilter =
    hasRegulationParam === 'true' ? 'with' : hasRegulationParam === 'false' ? 'without' : 'all'
  const minRegulationCount = parseIntParam(searchParams.get('min_regulation_count'), 0, 1_000_000)

  const updateParams = useCallback((apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }, [setSearchParams])

  const [searchInput, setSearchInput] = useState(() => search ?? '')
  useEffect(() => {
    setSearchInput(search ?? '')
  }, [search])

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
    updateParams((params) => {
      params.delete('search')
      params.delete('gene_type')
      params.delete('species_id')
      params.delete('chromosome')
      params.delete('has_regulation')
      params.delete('min_regulation_count')
      params.delete('page')
      params.delete('page_size')
    })
  }, [updateParams])

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
  const shouldVirtualizeTable = (tableData?.length ?? 0) >= 100
  const tableScroll = useMemo(
    () => ({
      x: 1500,
      y: shouldVirtualizeTable ? 520 : undefined,
    }),
    [shouldVirtualizeTable]
  )
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
    updateParams((params) => {
      if (next) params.set('search', next)
      else params.delete('search')
      params.delete('page')
    })
  }, [updateParams])

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
    getTitleCheckboxProps: () => ({
      'aria-label': tCommon('table.selectAll', { defaultValue: 'Select all rows' }),
    }),
    renderCell: (_checked, record, _index, originNode) => {
      const ariaLabel = tCommon('table.selectRow', {
        defaultValue: `Select row ${record.gene_name || record.core_id || record.gene_id}`,
      })

      if (isValidElement(originNode)) {
        return cloneElement(originNode as ReactElement<Record<string, unknown>>, { 'aria-label': ariaLabel })
      }
      return originNode
    },
  }

  return (
    <div style={{ padding: 24 }} data-testid="genes-page">
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{t('title')}</h1>
        <Button icon={<DownloadOutlined />} onClick={handleExportCsv}>
          {t('export.csv')}
        </Button>
      </Space>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          const nextTab = key as ActiveTab
          updateParams((params) => {
            if (nextTab === 'browse') params.delete('tab')
            else params.set('tab', nextTab)
            params.delete('page')
          })
        }}
        items={[
          {
            key: 'browse',
            label: t('tabs.browse'),
            children: (
              <Space wrap style={{ marginBottom: 16 }}>
                <Input.Search
                  aria-label={t('search.placeholder')}
                  placeholder={t('search.placeholder')}
                  value={searchInput}
                  onChange={(e) => {
                    const next = e.target.value
                    setSearchInput(next)
                    if (next === '') {
                      updateParams((params) => {
                        params.delete('search')
                        params.delete('page')
                      })
                    }
                  }}
                  onSearch={handleSearch}
                  style={{ width: 260 }}
                  allowClear
                />
                <Select
                  aria-label={t('search.geneType')}
                  placeholder={t('search.geneType')}
                  style={{ width: 160 }}
                  value={geneType}
                  onChange={(value) => {
                    updateParams((params) => {
                      if (value) params.set('gene_type', value)
                      else params.delete('gene_type')
                      params.delete('page')
                    })
                  }}
                  allowClear
                  options={[
                    { label: t('geneTypes.lncRNA'), value: 'lncRNA' },
                    { label: t('geneTypes.proteinCoding'), value: 'protein_coding' },
                  ]}
                />
                <Select
                  aria-label={t('filters.species')}
                  placeholder={t('filters.species')}
                  style={{ width: 160 }}
                  value={speciesId}
                  onChange={(value) => {
                    updateParams((params) => {
                      if (typeof value === 'number') params.set('species_id', String(value))
                      else params.delete('species_id')
                      params.delete('page')
                    })
                  }}
                  allowClear
                  options={speciesOptions}
                />
                <Input
                  aria-label={t('filters.chromosome')}
                  placeholder={t('filters.chromosome')}
                  style={{ width: 140 }}
                  value={chromosome}
                  onChange={(e) => {
                    const value = e.target.value.trim()
                    updateParams((params) => {
                      if (value) params.set('chromosome', value)
                      else params.delete('chromosome')
                      params.delete('page')
                    })
                  }}
                  allowClear
                />
                <Select
                  aria-label={t('filters.hasRegulation')}
                  placeholder={t('filters.hasRegulation')}
                  style={{ width: 200 }}
                  value={hasRegulation}
                  onChange={(value) => {
                    updateParams((params) => {
                      if (value === 'with') params.set('has_regulation', 'true')
                      else if (value === 'without') params.set('has_regulation', 'false')
                      else params.delete('has_regulation')
                      params.delete('page')
                    })
                  }}
                  options={[
                    { label: t('filters.hasRegulationAll'), value: 'all' },
                    { label: t('filters.hasRegulationYes'), value: 'with' },
                    { label: t('filters.hasRegulationNo'), value: 'without' },
                  ]}
                />
                <InputNumber
                  aria-label={t('filters.minRegulationCount')}
                  placeholder={t('filters.minRegulationCount')}
                  style={{ width: 200 }}
                  min={0}
                  value={minRegulationCount}
                  onChange={(value) => {
                    updateParams((params) => {
                      if (typeof value === 'number') params.set('min_regulation_count', String(value))
                      else params.delete('min_regulation_count')
                      params.delete('page')
                    })
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
              <Space orientation="vertical" style={{ width: '100%', marginBottom: 16 }}>
                <Space wrap>
                  <Select
                    aria-label={t('filters.species')}
                    placeholder={t('filters.species')}
                    style={{ width: 160 }}
                    value={speciesId}
                    onChange={(value) => {
                      updateParams((params) => {
                        if (typeof value === 'number') params.set('species_id', String(value))
                        else params.delete('species_id')
                        params.delete('page')
                      })
                    }}
                    allowClear
                    options={speciesOptions}
                  />
                  <Select
                    aria-label={t('search.geneType')}
                    placeholder={t('search.geneType')}
                    style={{ width: 160 }}
                    value={geneType}
                    onChange={(value) => {
                      updateParams((params) => {
                        if (value) params.set('gene_type', value)
                        else params.delete('gene_type')
                        params.delete('page')
                      })
                    }}
                    allowClear
                    options={[
                      { label: t('geneTypes.lncRNA'), value: 'lncRNA' },
                      { label: t('geneTypes.proteinCoding'), value: 'protein_coding' },
                    ]}
                  />
                </Space>

                <Input.TextArea
                  aria-label={t('batch.placeholder')}
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

      <div data-testid="genes-table">
        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={tableData}
          rowKey="gene_id"
          loading={activeTab === 'batch' ? batchResolve.isPending : isLoading}
          virtual={shouldVirtualizeTable}
          scroll={tableScroll}
          pagination={activeTab === 'browse' ? {
            current: page,
            pageSize,
            total: data?.total,
            showSizeChanger: true,
            showTotal: (total) => t('pagination.total', { count: total }),
            onChange: (p, ps) => {
              updateParams((params) => {
                const nextPageSize = ps ?? DEFAULT_PAGE_SIZE
                if (nextPageSize !== pageSize) {
                  if (nextPageSize === DEFAULT_PAGE_SIZE) params.delete('page_size')
                  else params.set('page_size', String(nextPageSize))
                  params.delete('page')
                  return
                }

                if (p <= 1) params.delete('page')
                else params.set('page', String(p))
              })
            },
          } : false}
        />
      </div>
    </div>
  )
}
