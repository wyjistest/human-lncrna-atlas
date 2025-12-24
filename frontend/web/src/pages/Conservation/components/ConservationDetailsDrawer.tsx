/**
 * ConservationDetailsDrawer Component
 *
 * Displays detailed shared regulatory relationships between two species
 * when a matrix cell is clicked
 */

import { useState, useEffect } from 'react'
import { Drawer, Table, Tag, Space, Typography, Spin, Empty, Tooltip } from 'antd'
import type { TableProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { conservationApi } from '@/api/conservation'
import type { ConservedRegulation } from '@/types/conservationPage'
import { CONSERVATION_SPECIES } from '@/types/conservationPage'
import { CONSERVATION_COLORS, getConservationCategory } from '@/types/conservation'

const { Title, Text } = Typography

/**
 * Species color mapping for tags
 */
const SPECIES_TAG_COLORS: Record<number, string> = {
  1: 'blue',      // Human
  2: 'green',     // Chimpanzee
  3: 'orange',    // Macaque
  4: 'magenta'    // Marmoset
}

interface ConservationDetailsDrawerProps {
  /** Whether the drawer is open */
  open: boolean
  /** Selected species pair (null if no selection) */
  speciesPair: { speciesX: number; speciesY: number; value: number } | null
  /** Callback when closing the drawer */
  onClose: () => void
}

/**
 * Conservation Details Drawer Component
 */
export function ConservationDetailsDrawer({
  open,
  speciesPair,
  onClose
}: ConservationDetailsDrawerProps) {
  const { t } = useTranslation('conservation')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Get species names
  const speciesXName = speciesPair
    ? CONSERVATION_SPECIES.find(s => s.id === speciesPair.speciesX)?.name || 'Unknown'
    : ''
  const speciesYName = speciesPair
    ? CONSERVATION_SPECIES.find(s => s.id === speciesPair.speciesY)?.name || 'Unknown'
    : ''

  // Query shared regulations
  const {
    data: regulationsData,
    isLoading,
  } = useQuery({
    queryKey: ['shared-regulations', speciesPair?.speciesX, speciesPair?.speciesY, page, pageSize],
    queryFn: async () => {
      if (!speciesPair) return null

      // Query regulations that exist in both species
      const speciesIds = [speciesPair.speciesX, speciesPair.speciesY]
      return await conservationApi.getConservedRegulations({
        species_ids: speciesIds,
        min_conservation: 2, // Must be in at least 2 species
        page,
        page_size: pageSize
      })
    },
    enabled: open && !!speciesPair,
    staleTime: 5 * 60 * 1000
  })

  // Reset page when species pair changes
  useEffect(() => {
    setPage(1)
  }, [speciesPair])

  // Table columns
  const columns: TableProps<ConservedRegulation>['columns'] = [
    {
      title: t('drawer.lncrna', 'LncRNA'),
      dataIndex: 'lncrna_gene_name',
      key: 'lncrna',
      width: 150,
      render: (name: string, record: ConservedRegulation) => (
        <Tooltip title={record?.lncrna_ensembl_id ?? '-'}>
          <Link to={`/genes?search=${name ?? ''}`}>{name ?? '-'}</Link>
        </Tooltip>
      )
    },
    {
      title: t('drawer.target', 'Target Gene'),
      dataIndex: 'target_gene_name',
      key: 'target',
      width: 150,
      render: (name: string, record: ConservedRegulation) => (
        <Tooltip title={record?.target_ensembl_id ?? '-'}>
          <Text>{name ?? '-'}</Text>
        </Tooltip>
      )
    },
    {
      title: t('drawer.speciesXBA', `${speciesXName} BA`),
      key: 'speciesXBA',
      width: 120,
      render: (_: unknown, record: ConservedRegulation) => {
        const ba = record.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesX ?? 0)
        )?.binding_affinity
        return ba?.toFixed(2) ?? '-'
      },
      sorter: (a, b) => {
        const baA = a.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesX ?? 0)
        )?.binding_affinity ?? 0
        const baB = b.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesX ?? 0)
        )?.binding_affinity ?? 0
        return baA - baB
      }
    },
    {
      title: t('drawer.speciesYBA', `${speciesYName} BA`),
      key: 'speciesYBA',
      width: 120,
      render: (_: unknown, record: ConservedRegulation) => {
        const ba = record.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesY ?? 0)
        )?.binding_affinity
        return ba?.toFixed(2) ?? '-'
      },
      sorter: (a, b) => {
        const baA = a.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesY ?? 0)
        )?.binding_affinity ?? 0
        const baB = b.species_binding_affinities?.find(
          s => s.species_id === (speciesPair?.speciesY ?? 0)
        )?.binding_affinity ?? 0
        return baA - baB
      }
    },
    {
      title: t('drawer.conservedIn', 'Conserved In'),
      dataIndex: 'species_ids',
      key: 'species',
      width: 200,
      render: (speciesIds: number[]) => (
        <Space size={[4, 4]} wrap>
          {(speciesIds || []).map(id => {
            const species = CONSERVATION_SPECIES.find(s => s.id === id)
            return (
              <Tag key={id} color={SPECIES_TAG_COLORS[id]}>
                {species ? t(`species.${species.name.toLowerCase()}`, species.name) : id}
              </Tag>
            )
          })}
        </Space>
      )
    },
    {
      title: t('drawer.conservationLevel', 'Level'),
      dataIndex: 'species_count',
      key: 'conservation_level',
      width: 100,
      render: (count: number, record: ConservedRegulation) => {
        const category = getConservationCategory(count ?? 0)
        return (
          <Tooltip title={record?.conservation_label ?? '-'}>
            <Tag
              color={CONSERVATION_COLORS[category]}
              style={{ color: category === 'medium' ? '#000' : '#fff' }}
            >
              {count ?? 0}/4
            </Tag>
          </Tooltip>
        )
      }
    }
  ]

  return (
    <Drawer
      title={
        <Space orientation="vertical" size={0}>
          <Title level={4} style={{ margin: 0 }}>
            {t('drawer.title', 'Shared Regulations')}
          </Title>
          <Text type="secondary">
            {speciesXName} ↔ {speciesYName}
            {speciesPair && ` (${speciesPair.value.toLocaleString()} shared)`}
          </Text>
        </Space>
      }
      styles={{ wrapper: { width: 900 } }}
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : !regulationsData || regulationsData.items.length === 0 ? (
        <Empty description={t('drawer.noData', 'No shared regulations found')} />
      ) : (
        <Table<ConservedRegulation>
          columns={columns}
          dataSource={regulationsData.items}
          rowKey="core_id"
          pagination={{
            current: page,
            pageSize,
            total: regulationsData.total,
            showSizeChanger: true,
            showTotal: (total) => t('drawer.total', `Total ${total} regulations`, { count: total }),
            onChange: (p, ps) => {
              if (ps !== pageSize) {
                setPage(1)
                setPageSize(ps)
              } else {
                setPage(p)
              }
            }
          }}
          scroll={{ x: 800, y: 'calc(100vh - 300px)' }}
          size="small"
        />
      )}
    </Drawer>
  )
}

export default ConservationDetailsDrawer
