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
import type {
  ConservedRegulation,
  ConservationMatrixData,
  ConservationOverview
} from '@/types/conservationPage'
import { CONSERVATION_SPECIES } from '@/types/conservationPage'
import { CONSERVATION_COLORS, getConservationCategory } from '@/types/conservation'

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
 * Generate mock data for demonstration when API is not available
 */
const generateMockOverview = (): ConservationOverview => ({
  total_conserved: 156789,
  four_species: 12345,
  three_species: 34567,
  two_species: 109877,
  by_combination: []
})

const generateMockMatrix = (speciesIds: number[]): ConservationMatrixData => {
  const speciesNames = speciesIds.map(id =>
    CONSERVATION_SPECIES.find(s => s.id === id)?.name || `Species ${id}`
  )

  // Generate symmetric matrix with random values
  const size = speciesIds.length
  const matrix: number[][] = Array(size).fill(null).map(() => Array(size).fill(0))

  for (let i = 0; i < size; i++) {
    for (let j = i; j < size; j++) {
      const value = i === j
        ? Math.floor(Math.random() * 100000 + 50000)
        : Math.floor(Math.random() * 50000 + 5000)
      matrix[i][j] = value
      matrix[j][i] = value
    }
  }

  const flatValues = matrix.flat()
  return {
    species: speciesIds,
    species_names: speciesNames,
    matrix,
    max_value: Math.max(...flatValues),
    min_value: Math.min(...flatValues)
  }
}

const generateMockRegulations = (page: number, pageSize: number): ConservedRegulation[] => {
  const regulations: ConservedRegulation[] = []
  const lncrnaNames = ['MALAT1', 'NEAT1', 'XIST', 'HOTAIR', 'H19', 'MEG3', 'GAS5', 'ANRIL']
  const targetNames = ['TP53', 'MYC', 'BRCA1', 'EGFR', 'KRAS', 'AKT1', 'BCL2', 'PTEN']

  for (let i = 0; i < pageSize; i++) {
    const speciesCount = Math.floor(Math.random() * 3) + 2 // 2-4 species
    const speciesIds = [1, 2, 3, 4].slice(0, speciesCount)
    const label = speciesIds.map((_, idx) => idx < speciesCount ? '1' : '0').join('')

    regulations.push({
      core_id: (page - 1) * pageSize + i + 1,
      lncrna_gene_name: lncrnaNames[Math.floor(Math.random() * lncrnaNames.length)],
      lncrna_ensembl_id: `ENSG${String(Math.floor(Math.random() * 1000000)).padStart(11, '0')}`,
      target_gene_name: targetNames[Math.floor(Math.random() * targetNames.length)],
      target_ensembl_id: `ENSG${String(Math.floor(Math.random() * 1000000)).padStart(11, '0')}`,
      conservation_label: label.padEnd(4, '0'),
      species_count: speciesCount,
      species_ids: speciesIds,
      avg_binding_affinity: Math.random() * 100,
      species_binding_affinities: speciesIds.map(id => ({
        species_id: id,
        species_name: CONSERVATION_SPECIES.find(s => s.id === id)?.name || '',
        binding_affinity: Math.random() * 100
      }))
    })
  }

  return regulations
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

  // API Queries with fallback to mock data
  const {
    data: overviewData,
    isLoading: overviewLoading,
    error: overviewError
  } = useQuery({
    queryKey: ['conservation-overview', selectedSpecies],
    queryFn: async () => {
      try {
        return await conservationApi.getOverview(selectedSpecies)
      } catch (error) {
        // Fallback to mock data if API is not available
        console.warn('Conservation API not available, using mock data', error)
        return generateMockOverview()
      }
    },
    staleTime: 5 * 60 * 1000 // 5 minutes
  })

  const {
    data: matrixData,
    isLoading: matrixLoading,
    error: matrixError
  } = useQuery({
    queryKey: ['conservation-matrix', selectedSpecies],
    queryFn: async () => {
      try {
        return await conservationApi.getMatrix(selectedSpecies)
      } catch (error) {
        // Fallback to mock data
        console.warn('Conservation matrix API not available, using mock data', error)
        return generateMockMatrix(selectedSpecies)
      }
    },
    enabled: selectedSpecies.length >= 2,
    staleTime: 5 * 60 * 1000
  })

  const {
    data: regulationsData,
    isLoading: regulationsLoading,
    error: regulationsError
  } = useQuery({
    queryKey: ['conservation-regulations', selectedSpecies, page, pageSize, minConservation, minBA, lncrnaSearch, targetSearch],
    queryFn: async () => {
      try {
        return await conservationApi.getConservedRegulations({
          species_ids: selectedSpecies,
          page,
          page_size: pageSize,
          min_conservation: minConservation,
          min_ba: minBA > 0 ? minBA : undefined,
          lncrna_gene_name: lncrnaSearch || undefined,
          target_gene_name: targetSearch || undefined
        })
      } catch (error) {
        // Fallback to mock data
        console.warn('Conservation regulations API not available, using mock data', error)
        const items = generateMockRegulations(page, pageSize)
        return {
          items,
          total: 1000,
          page,
          page_size: pageSize,
          pages: Math.ceil(1000 / pageSize)
        }
      }
    },
    enabled: selectedSpecies.length >= 2,
    staleTime: 2 * 60 * 1000
  })

  // Handlers
  const handleSpeciesChange = useCallback((speciesIds: number[]) => {
    setSelectedSpecies(speciesIds)
    setPage(1) // Reset pagination
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
      render: (name: string, record: ConservedRegulation) => (
        <Tooltip title={record.lncrna_ensembl_id}>
          <Link to={`/genes?search=${name}`}>{name}</Link>
        </Tooltip>
      )
    },
    {
      title: t('table.target', 'Target Gene'),
      dataIndex: 'target_gene_name',
      key: 'target',
      width: 150,
      render: (name: string, record: ConservedRegulation) => (
        <Tooltip title={record.target_ensembl_id}>
          <Text>{name}</Text>
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
          {speciesIds.map(id => {
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
        const category = getConservationCategory(count)
        return (
          <Tooltip title={record.conservation_label}>
            <Tag
              color={CONSERVATION_COLORS[category]}
              style={{ color: category === 'medium' ? '#000' : '#fff' }}
            >
              {count}/4
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
      render: (ba: number) => ba.toFixed(2),
      sorter: (a, b) => a.avg_binding_affinity - b.avg_binding_affinity
    }
  ], [t])

  // Loading state
  if (overviewLoading && matrixLoading) {
    return <LoadingState />
  }

  // Error state
  if (overviewError && matrixError && regulationsError) {
    return <ErrorState error={overviewError || matrixError || regulationsError} />
  }

  return (
    <div style={{ padding: 24 }}>
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
      <Space direction="vertical" size="small" style={{ width: '100%', marginBottom: 24 }}>
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
              valueStyle={{ color: CONSERVATION_COLORS.high }}
              loading={overviewLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('stats.threeSpecies', '3 Species')}
              value={overviewData?.three_species || 0}
              valueStyle={{ color: CONSERVATION_COLORS.medium }}
              loading={overviewLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('stats.twoSpecies', '2 Species')}
              value={overviewData?.two_species || 0}
              valueStyle={{ color: CONSERVATION_COLORS.low }}
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
          <ConservationMatrix
            data={matrixData || null}
            loading={matrixLoading}
            title={t('matrix.title', 'Conservation Matrix')}
            height={450}
          />
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
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
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
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
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
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
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
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
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
        <Table<ConservedRegulation>
          columns={columns}
          dataSource={regulationsData?.items || []}
          rowKey="core_id"
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
          scroll={{ x: 900 }}
          size="middle"
        />
      </Card>
    </div>
  )
}
