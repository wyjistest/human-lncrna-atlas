/**
 * Gene Detail Page
 * Displays complete gene information with tabs for core data and genomic features
 *
 * Phase 2.1: Added Tabs structure with Genomic Features tab including RepeatMasker
 * Phase 2.2: Added ChIP-seq Peaks sub-tab with multi-mark support
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useGeneDetail, useGeneRegulations, useGeneDiseases } from '@/hooks/useGenes'
import { useTranslation } from 'react-i18next'
import {
  Card,
  Descriptions,
  Button,
  Tag,
  Divider,
  Table,
  Result,
  Collapse,
  Spin,
  Tabs
} from 'antd'
import type { TableProps, TabsProps } from 'antd'
import {
  ArrowLeftOutlined,
  LinkOutlined,
  EyeOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  AppstoreOutlined,
  AreaChartOutlined
} from '@ant-design/icons'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { SequenceViewer } from '@/components/SequenceViewer'
import { RepeatMaskerTable } from '@/components/RepeatMaskerTable'
import { ChIPSeqPeaksTable } from '@/components/ChIPSeqPeaksTable'
import { ConservationBadge } from '@/components/ConservationBadge'
import { OrthologBrowser } from '@/components/OrthologBrowser'
import { createSpeciesTranslator } from '@/utils/species'

export default function GeneDetail() {
  const { geneId } = useParams<{ geneId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation('genes')
  const { t: tCommon } = useTranslation('common')
  const { t: tReg } = useTranslation('regulations')
  const { t: tGB } = useTranslation('genomeBrowser')

  // Pagination state for regulations
  const [regulationPage, setRegulationPage] = useState(1)
  const [regulationPageSize, setRegulationPageSize] = useState(10)

  // Sequence viewer state
  const [sequenceViewerOpen, setSequenceViewerOpen] = useState(false)
  const [selectedRegulationId, setSelectedRegulationId] = useState<number | null>(null)

  // Active tab state
  const [activeTab, setActiveTab] = useState('core')
  const [genomicSubTab, setGenomicSubTab] = useState('repeats')

  // Convert to number, handle NaN
  const geneIdNum = geneId ? parseInt(geneId, 10) : 0
  const isValidId = !isNaN(geneIdNum) && geneIdNum > 0

  // Data queries
  const { data: gene, isLoading, error } = useGeneDetail(isValidId ? geneIdNum : 0)
  const { data: regulations, isLoading: regulationsLoading } = useGeneRegulations(
    isValidId ? geneIdNum : 0,
    { page: regulationPage, page_size: regulationPageSize }
  )
  const { data: diseases, isLoading: diseasesLoading } = useGeneDiseases(isValidId ? geneIdNum : 0)

  const baseTranslate = createSpeciesTranslator(tCommon)
  const translateSpecies = (speciesName: string | undefined | null) => {
    if (!speciesName) return 'N/A'
    return baseTranslate(speciesName)
  }

  const cleanEnsemblId = (id: string | null | undefined) => {
    if (!id) return null
    return id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')
  }

  if (isLoading) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={() => window.location.reload()} />
  if (!gene) return <Result status="404" title="404" subTitle={t('detail.notFound')} />

  const cleanId = cleanEnsemblId(gene.gene_ensembl_id)

  // Regulation columns
  const regulationColumns: TableProps<any>['columns'] = [
    {
      title: t('detail.targetGene'),
      dataIndex: 'target_gene_name',
      width: 150,
    },
    {
      title: t('detail.chromosome'),
      dataIndex: 'target_chromosome',
      width: 90,
    },
    {
      title: t('detail.position'),
      key: 'position',
      width: 200,
      render: (_: unknown, record: any) =>
        `${record.target_start?.toLocaleString()} - ${record.target_end?.toLocaleString()}`,
    },
    {
      title: t('detail.bindingAffinity'),
      dataIndex: 'binding_affinity',
      width: 100,
      render: (val: string | number) => val ? Number(val).toFixed(2) : 'N/A',
    },
    {
      title: t('detail.bestAvgBA'),
      dataIndex: 'best_avg_ba',
      width: 100,
      render: (val: string | number) => val ? Number(val).toFixed(2) : 'N/A',
    },
    {
      title: t('detail.numPeaks'),
      dataIndex: 'num_peaks',
      width: 80,
    },
    {
      title: tReg('sequence.view'),
      key: 'action',
      width: 100,
      render: (_: unknown, record: any) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setSelectedRegulationId(record.regulation_id)
            setSequenceViewerOpen(true)
          }}
        >
          {tReg('sequence.view')}
        </Button>
      ),
    },
  ]

  // Disease columns
  const diseaseColumns: TableProps<any>['columns'] = [
    {
      title: t('detail.traitName'),
      dataIndex: 'trait_name',
      width: 200,
    },
    {
      title: t('detail.ontology'),
      dataIndex: 'ontology_name',
      width: 150,
    },
    {
      title: t('detail.oddsRatio'),
      dataIndex: 'odds_ratio',
      width: 100,
      render: (val: string | number) => val ? Number(val).toFixed(3) : 'N/A',
    },
    {
      title: t('detail.fdr'),
      dataIndex: 'fdr',
      width: 100,
      render: (val: string | number) => val ? Number(val).toExponential(2) : 'N/A',
    },
    {
      title: t('detail.literature'),
      dataIndex: 'literature_support',
      width: 80,
      render: (val: boolean) => (val ? <Tag color="green">Yes</Tag> : <Tag>No</Tag>),
    },
  ]

  // Collapse items for regulations and diseases
  const collapseItems = [
    {
      key: 'regulations',
      label: (
        <span>
          {t('detail.regulations')} <Tag color="blue">{gene.regulation_count}</Tag>
        </span>
      ),
      children: regulationsLoading ? (
        <Spin />
      ) : regulations?.items?.length ? (
        <Table
          dataSource={regulations.items}
          columns={regulationColumns}
          rowKey="regulation_id"
          size="small"
          pagination={{
            current: regulationPage,
            pageSize: regulationPageSize,
            total: regulations.total,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50],
            showQuickJumper: true,
            showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
            onChange: (page, pageSize) => {
              if (pageSize !== regulationPageSize) {
                setRegulationPageSize(pageSize)
                setRegulationPage(1)
              } else {
                setRegulationPage(page)
              }
            },
          }}
        />
      ) : (
        <div style={{ color: '#999', padding: 16 }}>{t('detail.noRegulations')}</div>
      ),
    },
    {
      key: 'diseases',
      label: (
        <span>
          {t('detail.diseases')} <Tag color="orange">{gene.disease_count}</Tag>
        </span>
      ),
      children: diseasesLoading ? (
        <Spin />
      ) : diseases?.length ? (
        <Table
          dataSource={diseases}
          columns={diseaseColumns}
          rowKey="association_id"
          size="small"
          pagination={{ pageSize: 10, showSizeChanger: false }}
        />
      ) : (
        <div style={{ color: '#999', padding: 16 }}>{t('detail.noDiseases')}</div>
      ),
    },
  ]

  // Navigate to IGV genome browser with gene name
  const handleViewInIGV = () => {
    if (gene.gene_name) {
      navigate(`/genome-browser?gene=${encodeURIComponent(gene.gene_name)}`)
    }
  }

  // Core Data Tab Content
  const CoreDataContent = () => (
    <>
      {/* Statistics - Collapsible panels */}
      <h4 style={{ marginBottom: 16 }}>{t('detail.statistics')}</h4>
      <Collapse items={collapseItems} defaultActiveKey={['regulations']} />

      <Divider />

      {/* Orthologs - Enhanced Browser */}
      {gene.orthologs && gene.orthologs.length > 0 && (
        <>
          <h4>{t('detail.orthologs')}</h4>
          <OrthologBrowser
            geneId={geneIdNum}
            currentSpeciesId={gene.species_id}
            orthologs={gene.orthologs}
            onNavigate={(id) => navigate(`/genes/${id}`)}
          />
        </>
      )}
    </>
  )

  // Genomic Features Tab Content - with sub-tabs for RepeatMasker and ChIP-seq
  const GenomicFeaturesContent = () => {
    const genomicSubTabs: TabsProps['items'] = [
      {
        key: 'repeats',
        label: (
          <span>
            <AppstoreOutlined />
            {t('detail.repeats.title')}
          </span>
        ),
        children: <RepeatMaskerTable geneId={geneIdNum} />
      },
      {
        key: 'chipseq',
        label: (
          <span>
            <AreaChartOutlined />
            {t('detail.chipseq.title')}
          </span>
        ),
        children: <ChIPSeqPeaksTable geneId={geneIdNum} enableComparison />
      }
    ]

    return (
      <Tabs
        activeKey={genomicSubTab}
        onChange={setGenomicSubTab}
        items={genomicSubTabs}
        size="small"
      />
    )
  }

  // Tab items configuration
  const tabItems: TabsProps['items'] = [
    {
      key: 'core',
      label: (
        <span>
          <DatabaseOutlined />
          {t('detail.tabs.core')}
        </span>
      ),
      children: <CoreDataContent />
    },
    {
      key: 'genomic',
      label: (
        <span>
          <AppstoreOutlined />
          {t('detail.tabs.genomicFeatures')}
        </span>
      ),
      children: <GenomicFeaturesContent />
    }
  ]

  return (
    <div style={{ padding: 24 }}>
      {/* Header buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/genes')}
        >
          {tCommon('action.back')}
        </Button>
        {gene.gene_name && (
          <Button
            type="primary"
            icon={<ExperimentOutlined />}
            onClick={handleViewInIGV}
          >
            {tGB('viewInIGV')}
          </Button>
        )}
      </div>

      <Card title={`${t('detail.title')}: ${gene.gene_name || gene.gene_id}`}>
        {/* Basic Information */}
        <Descriptions title={t('detail.basicInfo')} column={2} bordered size="small">
          <Descriptions.Item label="Gene ID">{gene.gene_id}</Descriptions.Item>
          <Descriptions.Item label="Core ID">{gene.core_id}</Descriptions.Item>
          <Descriptions.Item label="Ensembl ID">
            {cleanId ? (
              <a
                href={`https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${cleanId}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {gene.gene_ensembl_id} <LinkOutlined />
              </a>
            ) : (
              gene.gene_ensembl_id || 'N/A'
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.type')}>
            <Tag color={gene.gene_type === 'lncRNA' ? 'blue' : 'green'}>{gene.gene_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.conservation')}>
            <ConservationBadge
              conservationLabel={(gene as any).conservation_label}
              conservationCount={(gene as any).conservation_count}
            />
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.species')}>
            {translateSpecies(gene.species_name)}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.chromosome')}>{gene.chromosome || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('columns.start')}>
            {gene.gene_start?.toLocaleString() || 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label={t('columns.end')}>
            {gene.gene_end?.toLocaleString() || 'N/A'}
          </Descriptions.Item>
        </Descriptions>

        <Divider />

        {/* Tabs for Core Data and Genomic Features */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          type="card"
          size="large"
        />
      </Card>

      {/* Sequence Viewer Modal */}
      <SequenceViewer
        regulationId={selectedRegulationId}
        open={sequenceViewerOpen}
        onClose={() => {
          setSequenceViewerOpen(false)
          setSelectedRegulationId(null)
        }}
      />
    </div>
  )
}
