/**
 * Conservation Page
 * Cross-species conservation analysis of lncRNA regulations
 *
 * Features:
 * - Overview statistics cards
 * - Species selector (2-4 species)
 * - Conservation heatmap matrix
 * - Paginated conserved regulations table
 */

import { useState, useMemo, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Space,
  Input,
  Button,
  Tag,
  Slider,
  Typography,
  Breadcrumb,
  message,
  Tooltip
} from 'antd'
import type { TableProps } from 'antd'
import {
  HomeOutlined,
  SearchOutlined,
  DownloadOutlined,
  InfoCircleOutlined,
  BranchesOutlined
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'

import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { conservationApi } from '@/api/conservation'
import { SpeciesSelector } from './components/SpeciesSelector'
import { ConservationMatrix } from './components/ConservationMatrix'
import { ConservationDetailsDrawer } from './components/ConservationDetailsDrawer'
import type { ConservedRegulation } from '@/types/conservationPage'
import { CONSERVATION_SPECIES } from '@/types/conservationPage'
import { CONSERVATION_COLORS, getConservationCategory } from '@/types/conservation'
import { getMinMax } from '@/utils/minMax'

const { Title, Paragraph, Text } = Typography

/**
 * Species color mapping for tags
 */
const SPECIES_TAG_COLORS: Record<number, string> = {
  1: 'blue',      // Human
  2: 'green',     // Chimpanzee
  3: 'orange',    // Macaque
  4: 'magenta'    // Marmoset
}

/**
 * Conservation Analysis Page
 */
export default function Conservation() {
  const { t } = useTranslation('conservation')

  // State
  const [selectedSpecies, setSelectedSpecies] = useState<number[]>([1, 2, 3, 4])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [minConservation, setMinConservation] = useState(2)
  const [minBA, setMinBA] = useState(0)
  const [lncrnaSearch, setLncrnaSearch] = useState('')
  const [targetSearch, setTargetSearch] = useState('')

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedPair, setSelectedPair] = useState<{ speciesX: number; speciesY: number; value: number } | null>(null)

  // API Queries - errors propagate to ErrorState component
  const {
    data: overviewData,
    isLoading: overviewLoading,
    error: overviewError
  } = useQuery({
    queryKey: ['conservation-overview'],
    queryFn: async ({ signal }) => {
      const apiData = await conservationApi.getOverview(undefined, signal)
      // Transform backend format to frontend expected format
      const distribution = apiData.distribution || []
      const getCountByLevel = (level: number) =>
        distribution.find((d: { conservation_count: number }) => d.conservation_count === level)?.regulation_count || 0

      return {
        total_conserved: distribution
          .filter((d: { conservation_count: number }) => d.conservation_count >= 2)
          .reduce((sum: number, d: { regulation_count: number }) => sum + d.regulation_count, 0),
        four_species: getCountByLevel(4),
        three_species: getCountByLevel(3),
        two_species: getCountByLevel(2),
        by_combination: apiData.top_combinations || []
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    meta: { skipGlobalErrorHandler: true },
  })

  const {
    data: matrixApiData,
    isLoading: matrixLoading,
    error: matrixError
  } = useQuery({
    queryKey: ['conservation-matrix'],
    queryFn: ({ signal }) => conservationApi.getMatrix([1, 2, 3, 4], signal),
    enabled: selectedSpecies.length >= 2,
    staleTime: 5 * 60 * 1000,
    meta: { skipGlobalErrorHandler: true },
  })

  const matrixData = useMemo(() => {
    if (!matrixApiData) return null

    // Transform backend format to frontend expected format
    const speciesInfo = matrixApiData.species || []

    // Preserve backend ordering (Human -> Chimp -> Macaque -> Marmoset), but filter to selected species
    const selectedOrdered = speciesInfo
      .map(s => s.id)
      .filter(id => selectedSpecies.includes(id))

    const nameById = new Map(speciesInfo.map(s => [s.id, s.name] as const))
    const indexById = new Map(speciesInfo.map((s, idx) => [s.id, idx] as const))

    const indices = selectedOrdered
      .map(id => indexById.get(id))
      .filter((idx): idx is number => idx !== undefined)

    const sourceMatrix = matrixApiData.regulation_matrix || []
    const matrix = indices.map(i => indices.map(j => sourceMatrix[i]?.[j] ?? 0))

    // Calculate min/max values（安全遍历：避免 Math.min/max(...arr) 大数组问题）
    const flatValues = matrix.flat().filter((v): v is number => typeof v === 'number')
    const { min: minValue, max: maxValue } = getMinMax(flatValues, { defaultMin: 0, defaultMax: 0 })

    return {
      species: selectedOrdered,
      species_names: selectedOrdered.map(id => nameById.get(id) ?? String(id)),
      matrix,
      max_value: maxValue,
      min_value: minValue
    }
  }, [matrixApiData, selectedSpecies])

  const {
    data: regulationsData,
    isLoading: regulationsLoading,
    error: regulationsError
  } = useQuery({
    queryKey: ['conservation-regulations', selectedSpecies, page, pageSize, minConservation, minBA, lncrnaSearch, targetSearch],
    queryFn: ({ signal }) => conservationApi.getConservedRegulations({
      species_ids: selectedSpecies,
      page,
      page_size: pageSize,
      min_conservation: minConservation,
      min_ba: minBA > 0 ? minBA : undefined,
      lncrna_gene_name: lncrnaSearch || undefined,
      target_gene_name: targetSearch || undefined
    }, signal),
    enabled: selectedSpecies.length >= 2,
    staleTime: 2 * 60 * 1000,
    meta: { skipGlobalErrorHandler: true },
  })

  // Handlers
  const handleSpeciesChange = useCallback((speciesIds: number[]) => {
    setSelectedSpecies(speciesIds)
    setPage(1) // Reset pagination
  }, [])

  // Handle matrix cell click
  const handleCellClick = useCallback((speciesX: number, speciesY: number, value: number) => {
    setSelectedPair({ speciesX, speciesY, value })
    setDrawerOpen(true)
  }, [])

  const handleExport = useCallback(async () => {
    if (selectedSpecies.length < 2) {
      message.warning(t('export.selectSpeciesFirst', 'Please select at least 2 species'))
      return
    }

    const hideLoading = message.loading(t('export.preparing', 'Preparing export...'), 0)

    try {
      const blob = await conservationApi.exportRegulations({
        species_ids: selectedSpecies,
        min_conservation: minConservation,
        min_ba: minBA > 0 ? minBA : undefined,
        lncrna_gene_name: lncrnaSearch || undefined,
        target_gene_name: targetSearch || undefined
      })

      // Create download link
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `conservation_regulations_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      hideLoading()
      message.success(t('export.success', 'Export successful'))
    } catch (error) {
      hideLoading()
      message.error(t('export.failed', 'Export failed'))
      console.error('Export error:', error)
    }
  }, [selectedSpecies, minConservation, minBA, lncrnaSearch, targetSearch, t])

  // Table columns
  const columns: TableProps<ConservedRegulation>['columns'] = useMemo(() => [
    {
      title: t('table.coreId', 'Core ID'),
      dataIndex: 'core_id',
      key: 'core_id',
      width: 100
    },
    {
      title: t('table.lncrna', 'LncRNA'),
      dataIndex: 'lncrna_gene_name',
      key: 'lncrna',
      width: 150,
      render: (name: string | null, record: ConservedRegulation) => (
        <Tooltip title={record?.lncrna_ensembl_id ?? '-'}>
          <Link to={`/genes?search=${encodeURIComponent(name ?? '')}`}>{name ?? '-'}</Link>
        </Tooltip>
      )
    },
    {
      title: t('table.target', 'Target Gene'),
      dataIndex: 'target_gene_name',
      key: 'target',
      width: 150,
      render: (name: string | null, record: ConservedRegulation) => (
        <Tooltip title={record?.target_ensembl_id ?? '-'}>
          <Text>{name ?? '-'}</Text>
        </Tooltip>
      )
    },
    {
      title: t('table.conservedIn', 'Conserved In'),
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
      title: t('table.conservationLevel', 'Level'),
      dataIndex: 'species_count',
      key: 'conservation_level',
      width: 120,
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
    },
    {
      title: t('table.avgBA', 'Avg. BA'),
      dataIndex: 'avg_binding_affinity',
      key: 'avg_ba',
      width: 100,
      render: (ba: number) => ba?.toFixed(2) ?? '-',
      sorter: (a, b) => (a.avg_binding_affinity ?? 0) - (b.avg_binding_affinity ?? 0)
    }
  ], [t])

  // Loading state
  if (overviewLoading && matrixLoading) {
    return <LoadingState />
  }

  // Error state - show if ANY query failed
  if (overviewError || matrixError || regulationsError) {
    return <ErrorState error={overviewError || matrixError || regulationsError} />
  }

  return (
    <div style={{ padding: 24 }} data-testid="conservation-page">
      {/* Breadcrumb */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/">
                <HomeOutlined />
              </Link>
            )
          },
          {
            title: (
              <>
                <BranchesOutlined />
                <span style={{ marginLeft: 4 }}>
                  {t('breadcrumb.conservation', 'Conservation')}
                </span>
              </>
            )
          }
        ]}
      />

      {/* Page Header */}
      <Space orientation="vertical" size="small" style={{ width: '100%', marginBottom: 24 }}>
        <Title level={2}>
          {t('title', 'Cross-Species Conservation Analysis')}
        </Title>
        <Paragraph type="secondary">
          {t(
            'description',
            'Analyze conserved lncRNA regulatory relationships across primate species. ' +
            'Compare Human, Chimpanzee, Macaque, and Marmoset to identify evolutionarily conserved regulations.'
          )}
        </Paragraph>
      </Space>

      {/* Overview Statistics */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={
                <Space>
                  {t('stats.totalConserved', 'Total Conserved')}
                  <Tooltip title={t('stats.totalConservedHelp', 'Regulations found in 2+ species')}>
                    <InfoCircleOutlined style={{ color: '#999' }} />
                  </Tooltip>
                </Space>
              }
              value={overviewData?.total_conserved || 0}
              loading={overviewLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('stats.fourSpecies', '4 Species')}
              value={overviewData?.four_species || 0}
              styles={{ content: { color: CONSERVATION_COLORS.high } }}
              loading={overviewLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('stats.threeSpecies', '3 Species')}
              value={overviewData?.three_species || 0}
              styles={{ content: { color: CONSERVATION_COLORS.medium } }}
              loading={overviewLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('stats.twoSpecies', '2 Species')}
              value={overviewData?.two_species || 0}
              styles={{ content: { color: CONSERVATION_COLORS.low } }}
              loading={overviewLoading}
            />
          </Card>
        </Col>
      </Row>

      {/* Species Selector */}
      <SpeciesSelector
        selectedSpecies={selectedSpecies}
        onSelectionChange={handleSpeciesChange}
        disabled={overviewLoading}
      />

      {/* Conservation Heatmap */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <div data-testid="conservation-matrix">
            <ConservationMatrix
              data={matrixData || null}
              loading={matrixLoading}
              title={t('matrix.title', 'Conservation Matrix')}
              height={450}
              onCellClick={handleCellClick}
            />
          </div>
        </Col>
      </Row>

      {/* Filters */}
      <Card
        title={t('filters.title', 'Filters')}
        size="small"
        style={{ marginBottom: 16 }}
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('filters.lncrnaName', 'LncRNA Name')}
              </Text>
              <Input
                placeholder={t('filters.lncrnaPlaceholder', 'e.g., MALAT1')}
                prefix={<SearchOutlined />}
                value={lncrnaSearch}
                onChange={(e) => {
                  setLncrnaSearch(e.target.value)
                  setPage(1)
                }}
                allowClear
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('filters.targetName', 'Target Gene')}
              </Text>
              <Input
                placeholder={t('filters.targetPlaceholder', 'e.g., TP53')}
                prefix={<SearchOutlined />}
                value={targetSearch}
                onChange={(e) => {
                  setTargetSearch(e.target.value)
                  setPage(1)
                }}
                allowClear
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('filters.minConservation', 'Min. Conservation')}: {minConservation} {t('filters.species', 'species')}
              </Text>
              <Slider
                min={2}
                max={4}
                value={minConservation}
                onChange={(value) => {
                  setMinConservation(value)
                  setPage(1)
                }}
                marks={{ 2: '2', 3: '3', 4: '4' }}
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Space orientation="vertical" style={{ width: '100%' }} size={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('filters.minBA', 'Min. Binding Affinity')}: {minBA}
              </Text>
              <Slider
                min={0}
                max={100}
                value={minBA}
                onChange={(value) => {
                  setMinBA(value)
                  setPage(1)
                }}
                marks={{ 0: '0', 50: '50', 100: '100' }}
              />
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Conserved Regulations Table */}
      <Card
        title={
          <Space>
            {t('table.title', 'Conserved Regulations')}
            <Tag color="blue">{regulationsData?.total || 0}</Tag>
          </Space>
        }
        extra={
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
            disabled={!regulationsData || regulationsData.total === 0}
          >
            {t('table.export', 'Export CSV')}
          </Button>
        }
      >
        <div data-testid="conservation-table">
          <Table<ConservedRegulation>
            columns={columns}
            dataSource={regulationsData?.items || []}
            rowKey={(record) => {
              // 注意：同一个 core_id 可能对应多个 target gene，不能直接用 core_id 作为 key（会触发 React 重复 key 警告）
              const targetKey = record.target_ensembl_id || record.target_gene_name || 'unknown-target'
              return `${record.core_id}-${targetKey}-${record.conservation_label}`
            }}
            loading={regulationsLoading}
            pagination={{
              current: page,
              pageSize,
              total: regulationsData?.total || 0,
              showSizeChanger: true,
              showTotal: (total) => t('table.total', { count: total }),
              onChange: (p, ps) => {
                if (ps !== pageSize) {
                  setPage(1)
                  setPageSize(ps)
                } else {
                  setPage(p)
                }
              }
            }}
            virtual={(regulationsData?.items?.length ?? 0) >= 100}
            scroll={{ x: 900, y: (regulationsData?.items?.length ?? 0) >= 100 ? 520 : undefined }}
            size="middle"
          />
        </div>
      </Card>

      {/* Conservation Details Drawer */}
      <ConservationDetailsDrawer
        open={drawerOpen}
        speciesPair={selectedPair}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  )
}
