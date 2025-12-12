/**
 * OrthologBrowser Component
 * Interactive browser for ortholog genes across species
 *
 * Phase 6.2 - Ortholog Browser feature
 *
 * Features:
 * - Species tabs with colored indicators
 * - Click to navigate to ortholog gene detail
 * - View regulations drawer
 * - Species-specific colors (Human=blue, Chimp=orange, Macaque=green, Marmoset=purple)
 */

import { useState, useMemo } from 'react'
import {
  Card,
  Table,
  Tabs,
  Tag,
  Button,
  Drawer,
  Space,
  Spin,
  Empty,
  Tooltip
} from 'antd'
import type { TableProps, TabsProps } from 'antd'
import {
  ExportOutlined,
  EyeOutlined,
  ArrowRightOutlined,
  TeamOutlined
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useGeneOrthologs, useGeneRegulations } from '@/hooks/useGenes'
import { createSpeciesTranslator } from '@/utils/species'
import type { components } from '@/types'

type OrthologInfo = components['schemas']['OrthologInfo']

/**
 * Species color mapping
 * Using distinct colors for each primate species
 */
const SPECIES_COLORS: Record<number, { primary: string; bg: string; border: string }> = {
  1: { primary: '#1890ff', bg: '#e6f7ff', border: '#91d5ff' }, // Human - Blue
  2: { primary: '#fa8c16', bg: '#fff7e6', border: '#ffd591' }, // Chimp - Orange
  3: { primary: '#52c41a', bg: '#f6ffed', border: '#b7eb8f' }, // Macaque - Green
  4: { primary: '#722ed1', bg: '#f9f0ff', border: '#d3adf7' }, // Marmoset - Purple
}

/**
 * Species name mapping for display
 */
const SPECIES_NAMES: Record<number, string> = {
  1: 'Human',
  2: 'Chimpanzee',
  3: 'Macaque',
  4: 'Marmoset',
}

interface OrthologBrowserProps {
  /** Current gene ID */
  geneId: number
  /** Current gene's species ID */
  currentSpeciesId: number
  /** Pre-loaded orthologs data (optional, will fetch if not provided) */
  orthologs?: OrthologInfo[]
  /** Callback when navigating to ortholog gene */
  onNavigate?: (geneId: number) => void
}

/**
 * Regulations drawer component for viewing ortholog regulations
 */
interface RegulationsDrawerProps {
  open: boolean
  onClose: () => void
  geneId: number
  geneName: string
}

const RegulationsDrawer: React.FC<RegulationsDrawerProps> = ({
  open,
  onClose,
  geneId,
  geneName
}) => {
  const { t } = useTranslation('genes')
  const { t: tReg } = useTranslation('regulations')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const { data: regulations, isLoading } = useGeneRegulations(
    open ? geneId : 0,
    { page, page_size: pageSize }
  )

  const columns: TableProps<any>['columns'] = [
    {
      title: t('detail.targetGene'),
      dataIndex: 'target_gene_name',
      width: 150,
      ellipsis: true,
    },
    {
      title: t('detail.chromosome'),
      dataIndex: 'target_chromosome',
      width: 80,
    },
    {
      title: t('detail.bindingAffinity'),
      dataIndex: 'binding_affinity',
      width: 100,
      render: (val: number) => val?.toFixed(2) || 'N/A',
    },
    {
      title: t('detail.bestAvgBA'),
      dataIndex: 'best_avg_ba',
      width: 100,
      render: (val: number) => val?.toFixed(2) || 'N/A',
    },
  ]

  return (
    <Drawer
      title={t('ortholog.regulationsDrawerTitle', { geneName })}
      placement="right"
      width={600}
      onClose={onClose}
      open={open}
      extra={
        <Tag color="blue">{regulations?.total || 0} {tReg('total')}</Tag>
      }
    >
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : (
        <Table
          dataSource={regulations?.items || []}
          columns={columns}
          rowKey="regulation_id"
          size="small"
          pagination={{
            current: page,
            pageSize: pageSize,
            total: regulations?.total || 0,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50],
            showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
            onChange: (p, ps) => {
              if (ps !== pageSize) {
                setPageSize(ps)
                setPage(1)
              } else {
                setPage(p)
              }
            },
          }}
        />
      )}
    </Drawer>
  )
}

export const OrthologBrowser: React.FC<OrthologBrowserProps> = ({
  geneId,
  currentSpeciesId,
  orthologs: preloadedOrthologs,
  onNavigate
}) => {
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')

  // State for active species filter
  const [activeSpecies, setActiveSpecies] = useState<string>('all')

  // State for regulations drawer
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedOrtholog, setSelectedOrtholog] = useState<OrthologInfo | null>(null)

  // Fetch orthologs if not pre-loaded
  const { data: fetchedOrthologs, isLoading } = useGeneOrthologs(
    preloadedOrthologs ? 0 : geneId
  )

  // Use pre-loaded or fetched orthologs
  const orthologs = preloadedOrthologs || fetchedOrthologs || []

  // Species translator
  const baseTranslate = createSpeciesTranslator(tCommon)
  const translateSpecies = (speciesName: string | undefined | null) => {
    if (!speciesName) return 'N/A'
    return baseTranslate(speciesName)
  }

  // Get unique species from orthologs (excluding current species)
  const availableSpecies = useMemo(() => {
    const speciesSet = new Set<number>()
    orthologs.forEach(o => {
      if (o.species_id !== currentSpeciesId) {
        speciesSet.add(o.species_id)
      }
    })
    return Array.from(speciesSet).sort()
  }, [orthologs, currentSpeciesId])

  // Filter orthologs by active species
  const filteredOrthologs = useMemo(() => {
    if (activeSpecies === 'all') {
      return orthologs.filter(o => o.species_id !== currentSpeciesId)
    }
    return orthologs.filter(o => o.species_id === parseInt(activeSpecies))
  }, [orthologs, activeSpecies, currentSpeciesId])

  // Handle view regulations
  const handleViewRegulations = (ortholog: OrthologInfo) => {
    setSelectedOrtholog(ortholog)
    setDrawerOpen(true)
  }

  // Handle navigate to gene
  const handleNavigate = (orthologGeneId: number) => {
    if (onNavigate) {
      onNavigate(orthologGeneId)
    }
  }

  // Build tabs items
  const tabItems: TabsProps['items'] = [
    {
      key: 'all',
      label: (
        <Space>
          <TeamOutlined />
          {t('ortholog.allSpecies')}
          <Tag>{orthologs.filter(o => o.species_id !== currentSpeciesId).length}</Tag>
        </Space>
      ),
    },
    ...availableSpecies.map(speciesId => ({
      key: String(speciesId),
      label: (
        <Space>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: SPECIES_COLORS[speciesId]?.primary || '#999',
            }}
          />
          {translateSpecies(SPECIES_NAMES[speciesId])}
          <Tag color={SPECIES_COLORS[speciesId]?.primary}>
            {orthologs.filter(o => o.species_id === speciesId).length}
          </Tag>
        </Space>
      ),
    })),
  ]

  // Table columns
  const columns: TableProps<OrthologInfo>['columns'] = [
    {
      title: t('columns.species'),
      dataIndex: 'species_name',
      width: 120,
      render: (_, record) => (
        <Space>
          <span
            style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: SPECIES_COLORS[record.species_id]?.primary || '#999',
            }}
          />
          {translateSpecies(record.species_name)}
        </Space>
      ),
    },
    {
      title: t('columns.geneName'),
      dataIndex: 'gene_name',
      width: 150,
      ellipsis: true,
      render: (val: string | null, record) => (
        <Tooltip title={record.gene_ensembl_id}>
          <span style={{ fontWeight: 500 }}>{val || record.gene_ensembl_id || 'N/A'}</span>
        </Tooltip>
      ),
    },
    {
      title: 'Ensembl ID',
      dataIndex: 'gene_ensembl_id',
      width: 180,
      ellipsis: true,
    },
    {
      title: t('ortholog.position'),
      key: 'position',
      width: 200,
      render: (_, record) => (
        <span>
          {record.chromosome || 'N/A'}:
          {record.gene_start?.toLocaleString() || '?'}-{record.gene_end?.toLocaleString() || '?'}
        </span>
      ),
    },
    {
      title: tCommon('action.actions'),
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title={t('ortholog.viewRegulations')}>
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                handleViewRegulations(record)
              }}
            />
          </Tooltip>
          <Tooltip title={t('ortholog.goToDetail')}>
            <Button
              type="text"
              size="small"
              icon={<ArrowRightOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                handleNavigate(record.gene_id)
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  // Loading state
  if (isLoading) {
    return (
      <Card size="small">
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
          <div style={{ marginTop: 8, color: '#999' }}>{t('ortholog.loading')}</div>
        </div>
      </Card>
    )
  }

  // Empty state
  if (!orthologs.length || !filteredOrthologs.length) {
    return (
      <Card size="small">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t('ortholog.noOrthologs')}
        />
      </Card>
    )
  }

  return (
    <>
      <Card
        size="small"
        title={
          <Space>
            <TeamOutlined />
            {t('ortholog.title')}
            <Tag color="blue">
              {t('ortholog.speciesCount', { count: availableSpecies.length })}
            </Tag>
          </Space>
        }
        extra={
          <Tooltip title="View in full page">
            <Button type="text" size="small" icon={<ExportOutlined />} />
          </Tooltip>
        }
        styles={{ body: { padding: 0 } }}
      >
        {/* Species Tabs */}
        <div style={{ borderBottom: '1px solid #f0f0f0' }}>
          <Tabs
            activeKey={activeSpecies}
            onChange={setActiveSpecies}
            items={tabItems}
            size="small"
            tabBarStyle={{ marginBottom: 0, paddingLeft: 16 }}
          />
        </div>

        {/* Orthologs Table */}
        <Table
          dataSource={filteredOrthologs}
          columns={columns}
          rowKey="gene_id"
          size="small"
          pagination={false}
          scroll={{ x: 800 }}
          onRow={(record) => ({
            onClick: () => handleNavigate(record.gene_id),
            style: {
              cursor: 'pointer',
              backgroundColor: SPECIES_COLORS[record.species_id]?.bg || 'transparent',
            },
            onMouseEnter: (e) => {
              e.currentTarget.style.backgroundColor =
                SPECIES_COLORS[record.species_id]?.border || '#f5f5f5'
            },
            onMouseLeave: (e) => {
              e.currentTarget.style.backgroundColor =
                SPECIES_COLORS[record.species_id]?.bg || 'transparent'
            },
          })}
        />
      </Card>

      {/* Regulations Drawer */}
      <RegulationsDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedOrtholog(null)
        }}
        geneId={selectedOrtholog?.gene_id || 0}
        geneName={selectedOrtholog?.gene_name || selectedOrtholog?.gene_ensembl_id || ''}
      />
    </>
  )
}

export default OrthologBrowser
