import { useState, useMemo } from 'react'
import { Table, Input } from 'antd'
import type { TableProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useDiseases, useDiseaseGenes } from '@/hooks/useDiseases'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { createSpeciesTranslator } from '@/utils/species'

export default function Diseases() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [search, setSearch] = useState('')
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([])
  const { t, i18n } = useTranslation('diseases')
  const { t: tCommon } = useTranslation('common')

  const translateSpecies = createSpeciesTranslator(tCommon)

  const { data, isLoading, error } = useDiseases({ page, page_size: pageSize, search })

  const columns: TableProps<any>['columns'] = useMemo(() => [
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
  ], [t, i18n.language, translateSpecies])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('title')}</h1>
      <p style={{ color: '#666', marginBottom: 16 }}>
        {t('description')}
      </p>
      <Input.Search
        placeholder={t('search.placeholder')}
        onSearch={setSearch}
        style={{ width: 300, marginBottom: 16 }}
        allowClear
      />
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
          expandedRowRender: (record) => <DiseaseAssociations traitId={record.trait_id} ontologyId={record.ontology_id} />,
        }}
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
    </div>
  )
}

function DiseaseAssociations({ traitId, ontologyId }: { traitId: number; ontologyId: number }) {
  const { t, i18n } = useTranslation('diseases')

  const { data, isLoading, error } = useDiseaseGenes(traitId, {
    page: 1,
    page_size: 1000,
    ontology_id: ontologyId,
  })

  const columns: TableProps<any>['columns'] = useMemo(() => [
    { title: t('expanded.gene'), dataIndex: 'gene_name', width: 150 },
    { title: t('expanded.type'), dataIndex: 'gene_type', width: 120 },
    { title: t('expanded.oddsRatio'), dataIndex: 'odds_ratio', width: 100 },
    { title: t('expanded.fdr'), dataIndex: 'fdr', width: 100 },
    { title: t('expanded.literature'), dataIndex: 'literature_support', width: 100, render: (val: boolean) => val ? '✓' : '-' },
  ], [t, i18n.language])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <Table
      columns={columns}
      dataSource={data?.items}
      rowKey="association_id"
      size="small"
      pagination={false}
    />
  )
}
