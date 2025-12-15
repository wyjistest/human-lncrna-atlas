import { useState, useMemo, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Input, Select, Space, Button } from 'antd'
import type { TableProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useGenes, usePrefetchGenes } from '@/hooks/useGenes'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import type { components } from '@/types'

type GeneListItem = components['schemas']['GeneListItem']

// 中文物种名到翻译 key 的映射
const SPECIES_NAME_TO_KEY: Record<string, string> = {
  '人类': 'human',
  '黑猩猩': 'chimpanzee',
  '猕猴': 'macaque',
  '狨猴': 'marmoset'
}

export default function Genes() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [search, setSearch] = useState('')
  const [geneType, setGeneType] = useState<string>()
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // 翻译物种名称
  const translateSpecies = useCallback((speciesName: string) => {
    const key = SPECIES_NAME_TO_KEY[speciesName]
    return key ? tCommon(`species.${key}`) : speciesName
  }, [tCommon])

  // 搜索/筛选时重置页码到第一页
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    setPage(1)
  }, [])

  const handleGeneTypeChange = useCallback((value: string | undefined) => {
    setGeneType(value)
    setPage(1)
  }, [])

  const { data, isLoading, error } = useGenes({ page, page_size: pageSize, search, gene_type: geneType })

  // 预加载相邻页
  const prefetchGenes = usePrefetchGenes()

  // 当前页加载完成后，预加载下一页和上一页
  useEffect(() => {
    if (data) {
      const totalPages = Math.ceil((data.total || 0) / pageSize)

      // 预加载下一页
      if (page < totalPages) {
        prefetchGenes({ page: page + 1, page_size: pageSize, search, gene_type: geneType })
      }

      // 预加载上一页（用户可能回退）
      if (page > 1) {
        prefetchGenes({ page: page - 1, page_size: pageSize, search, gene_type: geneType })
      }
    }
  }, [data, page, pageSize, search, geneType, prefetchGenes])

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
          // 去掉物种后缀 (如 _marmoset, _macaque, _chimpanzee, _chimp)
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
          // 去掉物种后缀 (如 _marmoset, _macaque, _chimpanzee, _chimp)
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
  ], [t, translateSpecies, tCommon, navigate])

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} />

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('title')}</h1>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder={t('search.placeholder')}
          onSearch={handleSearchChange}
          style={{ width: 250 }}
          allowClear
        />
        <Select
          placeholder={t('search.geneType')}
          style={{ width: 150 }}
          onChange={handleGeneTypeChange}
          allowClear
          options={[
            { label: t('geneTypes.lncRNA'), value: 'lncRNA' },
            { label: t('geneTypes.proteinCoding'), value: 'protein_coding' },
          ]}
        />
      </Space>
      <Table
        columns={columns}
        dataSource={data?.items}
        rowKey="gene_id"
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
