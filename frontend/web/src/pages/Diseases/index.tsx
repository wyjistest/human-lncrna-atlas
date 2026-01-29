import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Table, Input } from 'antd'
import type { TableProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useDiseases, useDiseaseGenes } from '@/hooks/useDiseases'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { createSpeciesTranslator } from '@/utils/species'

const DEFAULT_PAGE = 1
const DEFAULT_PAGE_SIZE = 100
const MAX_PAGE = 1_000_000
const MAX_PAGE_SIZE = 1000

function parseIntParam(value: string | null, min: number, max: number): number | undefined {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return undefined
  if (parsed < min || parsed > max) return undefined
  return parsed
}

export default function Diseases() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseIntParam(searchParams.get('page'), 1, MAX_PAGE) ?? DEFAULT_PAGE
  const pageSize = parseIntParam(searchParams.get('page_size'), 1, MAX_PAGE_SIZE) ?? DEFAULT_PAGE_SIZE
  const search = searchParams.get('search')?.trim() || ''

  const updateParams = useCallback((apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }, [setSearchParams])

  const [searchInput, setSearchInput] = useState(() => search)
  useEffect(() => {
    setSearchInput(search)
  }, [search])

  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([])
  const { t } = useTranslation('diseases')
  const { t: tCommon } = useTranslation('common')

  const translateSpecies = createSpeciesTranslator(tCommon)

  const { data, isLoading, error } = useDiseases({ page, page_size: pageSize, search })

  const handleSearch = useCallback((value: string) => {
    const next = value.trim()
    updateParams((params) => {
      if (next) params.set('search', next)
      else params.delete('search')
      params.delete('page')
    })
  }, [updateParams])

  const columns: TableProps<Record<string, unknown>>['columns'] = useMemo(() => [
    { title: t('columns.traitId'), dataIndex: 'trait_id', width: 80 },
    { title: t('columns.traitName'), dataIndex: 'trait_name', width: 200 },
    {
      title: t('columns.traitLink'),
      width: 150,
      render: (_, record) => {
        if (record.trait_doid) {
          return (
            <a
              href={`https://fantom.gsc.riken.jp/cat/v1/#/traits/${record.trait_doid}`}
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
    { title: t('columns.doid'), dataIndex: 'trait_doid', width: 120 },
    { title: t('columns.ontologyId'), dataIndex: 'ontology_cl_id', width: 130 },
    { title: t('columns.ontologyName'), dataIndex: 'ontology_name', width: 250 },
    {
      title: t('columns.ontologyLink'),
      width: 180,
      render: (_, record) => {
        if (record.ontology_cl_id) {
          return (
            <a
              href={`https://fantom.gsc.riken.jp/cat/v1/#/ontologies/${record.ontology_cl_id}`}
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
      title: t('columns.species'),
      dataIndex: 'species_name',
      width: 100,
      render: (speciesName: string) => translateSpecies(speciesName)
    },
    { title: t('columns.genes'), dataIndex: 'gene_count', width: 80 },
    { title: t('columns.lncrnas'), dataIndex: 'lncrna_count', width: 80 },
  ], [t, translateSpecies])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <div style={{ padding: 24 }} data-testid="diseases-page">
      <h1>{t('title')}</h1>
      <p style={{ color: '#666', marginBottom: 16 }}>
        {t('description')}
      </p>
      <Input.Search
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
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
      <div data-testid="diseases-table">
        <Table
          columns={columns}
          dataSource={data?.items}
          rowKey={(record) => `${record.trait_id}-${record.ontology_id}`}
          expandable={{
            expandedRowKeys,
            onExpand: (expanded, record) => {
              const key = `${record.trait_id}-${record.ontology_id}`
              setExpandedRowKeys(expanded ? [key] : [])
            },
            expandedRowRender: (record) => <DiseaseAssociations traitId={record.trait_id as number} ontologyId={record.ontology_id as number} />,
          }}
          pagination={{
            current: page,
            pageSize,
            total: data?.total,
            showSizeChanger: true,
            showTotal: (total) => t('pagination.total', { count: total }),
            onChange: (p, ps) => {
              updateParams((params) => {
                // 当 pageSize 改变时，重置到第一页避免竞态条件
                if (ps !== pageSize) {
                  if (ps === DEFAULT_PAGE_SIZE) params.delete('page_size')
                  else params.set('page_size', String(ps))
                  params.delete('page')
                  return
                }

                if (p === DEFAULT_PAGE) params.delete('page')
                else params.set('page', String(p))
              })
            },
          }}
        />
      </div>
    </div>
  )
}

function DiseaseAssociations({ traitId, ontologyId }: { traitId: number; ontologyId: number }) {
  const { t } = useTranslation('diseases')

  const { data, isLoading, error } = useDiseaseGenes(traitId, {
    page: 1,
    page_size: 1000,
    ontology_id: ontologyId,
  })

  const columns: TableProps<Record<string, unknown>>['columns'] = useMemo(() => [
    { title: t('expanded.gene'), dataIndex: 'gene_name', width: 150 },
    { title: t('expanded.type'), dataIndex: 'gene_type', width: 120 },
    { title: t('expanded.oddsRatio'), dataIndex: 'odds_ratio', width: 100 },
    { title: t('expanded.fdr'), dataIndex: 'fdr', width: 100 },
    { title: t('expanded.literature'), dataIndex: 'literature_support', width: 100, render: (val: boolean) => val ? '✓' : '-' },
  ], [t])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  const shouldVirtualizeTable = (data?.items?.length ?? 0) >= 100

  return (
    <Table
      columns={columns}
      dataSource={data?.items}
      rowKey="association_id"
      size="small"
      pagination={false}
      virtual={shouldVirtualizeTable}
      scroll={{ x: 700, y: shouldVirtualizeTable ? 360 : undefined }}
    />
  )
}
