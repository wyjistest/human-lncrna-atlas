/**
 * GenomeBrowser Page
 * Route: /genome-browser
 *
 * Provides an interactive genome browser for visualizing lncRNA and regulatory data
 * using IGV.js integration.
 *
 * URL Parameters:
 * - gene: Gene name to load (e.g., CATG00000000011.1) - takes precedence
 * - species: Species ID (1-4, default: 1 for Human) - used when gene not specified
 *
 * Two viewing modes:
 * 1. Species browsing mode: Select a species to load its full genome
 * 2. Gene search mode: Enter a gene name to auto-locate (maintains current functionality)
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Typography, Card, Input, Button, Space, message, Divider, Alert, Select, Radio } from 'antd'
import { SearchOutlined, ExperimentOutlined, GlobalOutlined, AimOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GenomeBrowser from '@/components/GenomeBrowser'

const { Title, Paragraph, Text } = Typography
const { Search } = Input

type ViewMode = 'species' | 'gene'

export default function GenomeBrowserPage() {
  const { t } = useTranslation('genomeBrowser')
  const { t: tCommon } = useTranslation('common')
  const [searchParams, setSearchParams] = useSearchParams()

  // Get initial values from URL params
  const urlGene = searchParams.get('gene')
  const urlSpecies = searchParams.get('species')

  // Determine initial mode based on URL params
  const getInitialMode = (): ViewMode => {
    if (urlGene) return 'gene'
    if (urlSpecies) return 'species'
    return 'gene' // Default to gene mode for backward compatibility
  }

  const getInitialSpecies = (): number => {
    if (urlSpecies) {
      const parsed = parseInt(urlSpecies, 10)
      if (parsed >= 1 && parsed <= 4) return parsed
    }
    return 1 // Default to Human
  }

  const getInitialGene = (): string => {
    return urlGene || 'CATG00000000011.1' // Default gene
  }

  const [viewMode, setViewMode] = useState<ViewMode>(getInitialMode)
  const [speciesId, setSpeciesId] = useState<number>(getInitialSpecies)
  const [geneName, setGeneName] = useState<string | undefined>(
    getInitialMode() === 'gene' ? getInitialGene() : undefined
  )
  const [searchInput, setSearchInput] = useState<string>(getInitialGene())
  const [currentLocus, setCurrentLocus] = useState<string | undefined>(undefined)
  const browserRef = useRef<HTMLDivElement>(null)

  // Species options
  const speciesOptions = [
    { label: tCommon('species.human'), value: 1 },
    { label: tCommon('species.chimpanzee'), value: 2 },
    { label: tCommon('species.macaque'), value: 3 },
    { label: tCommon('species.marmoset'), value: 4 },
  ]

  // Sync URL params when mode/species/gene changes
  useEffect(() => {
    const newParams = new URLSearchParams()

    if (viewMode === 'gene' && geneName) {
      newParams.set('gene', geneName)
    } else if (viewMode === 'species') {
      newParams.set('species', speciesId.toString())
    }

    setSearchParams(newParams, { replace: true })
  }, [viewMode, speciesId, geneName, setSearchParams])

  // Handle view mode change
  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode)
    setCurrentLocus(undefined)

    if (mode === 'species') {
      // Switching to species mode - clear gene
      setGeneName(undefined)
    } else {
      // Switching to gene mode - set default gene if none
      if (!geneName && searchInput) {
        setGeneName(searchInput)
      }
    }
  }, [geneName, searchInput])

  // Handle species change
  const handleSpeciesChange = useCallback((value: number) => {
    setSpeciesId(value)
    setCurrentLocus(undefined)
    // Clear gene when changing species in species mode
    if (viewMode === 'species') {
      setGeneName(undefined)
      setSearchInput('')
    }
  }, [viewMode])

  // Handle gene search
  const handleGeneSearch = useCallback((value: string) => {
    const trimmed = value.trim()
    if (!trimmed) {
      message.warning(t('enterGeneName') || 'Please enter a gene name')
      return
    }

    // Switch to gene mode
    setViewMode('gene')
    setGeneName(trimmed)
    setCurrentLocus(undefined)
  }, [t])

  // Handle locus change from IGV browser (user navigation)
  const handleLocusChange = useCallback((locus: string) => {
    setCurrentLocus(locus)
  }, [])

  // Quick load examples
  const exampleGenes = [
    'CATG00000000011.1',
    'CATG00000000034.1',
    'CATG00000000072.1',
  ]

  return (
    <div style={{ padding: 24 }}>
      <Typography>
        <Title level={2}>
          <ExperimentOutlined style={{ marginRight: 8 }} />
          {t('title')}
        </Title>
        <Paragraph style={{ color: '#666', marginBottom: 16 }}>
          {t('description')}
        </Paragraph>
      </Typography>

      <Card
        styles={{
          body: { padding: 16 }
        }}
      >
        {/* View Mode Selector */}
        <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
          <Space wrap align="center" size="large">
            <Radio.Group
              value={viewMode}
              onChange={(e) => handleViewModeChange(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="gene">
                <AimOutlined style={{ marginRight: 4 }} />
                {t('geneFocusMode')}
              </Radio.Button>
              <Radio.Button value="species">
                <GlobalOutlined style={{ marginRight: 4 }} />
                {t('speciesBrowseMode')}
              </Radio.Button>
            </Radio.Group>

            {/* Species Selector - always visible */}
            <Space>
              <Text strong>{t('species')}:</Text>
              <Select
                value={speciesId}
                onChange={handleSpeciesChange}
                options={speciesOptions}
                style={{ width: 140 }}
              />
            </Space>
          </Space>

          {/* Mode-specific Alert */}
          {viewMode === 'gene' ? (
            <Alert
              type="info"
              showIcon
              message={t('geneLoadMode')}
              description={t('geneLoadModeDesc')}
              style={{ marginTop: 8 }}
            />
          ) : (
            <Alert
              type="success"
              showIcon
              message={t('speciesBrowseMode')}
              description={t('speciesBrowseModeDesc')}
              style={{ marginTop: 8 }}
            />
          )}
        </Space>

        <Divider style={{ margin: '12px 0' }} />

        {/* Gene Search Input */}
        <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
          <Space wrap>
            <Search
              placeholder={t('searchPlaceholder') || "Enter gene name (e.g., CATG00000000011.1)"}
              allowClear
              enterButton={<><SearchOutlined /> {t('load') || 'Load'}</>}
              size="large"
              style={{ width: 400 }}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onSearch={handleGeneSearch}
            />
            <Text type="secondary" style={{ marginLeft: 16 }}>
              {t('quickLoad') || 'Quick load'}:
            </Text>
            {exampleGenes.map((gene) => (
              <Button
                key={gene}
                size="small"
                onClick={() => {
                  setSearchInput(gene)
                  handleGeneSearch(gene)
                }}
                type={geneName === gene ? 'primary' : 'default'}
              >
                {gene}
              </Button>
            ))}
          </Space>

          {/* Current Status Display */}
          <Space>
            {viewMode === 'species' && (
              <Text>
                {t('currentSpecies')}: <Text strong>{speciesOptions.find(s => s.value === speciesId)?.label}</Text>
              </Text>
            )}
            {viewMode === 'gene' && geneName && (
              <Text>
                {t('currentGene')}: <Text strong code>{geneName}</Text>
              </Text>
            )}
            {currentLocus && (
              <Text type="secondary">
                @ {currentLocus}
              </Text>
            )}
          </Space>
        </Space>

        <Divider style={{ margin: '12px 0' }} />

        {/* Genome Browser */}
        <div ref={browserRef}>
          <GenomeBrowser
            key={viewMode === 'gene' ? `gene-${geneName}` : `species-${speciesId}`}
            speciesId={speciesId}
            geneName={viewMode === 'gene' ? geneName : undefined}
            locus={currentLocus}
            onLocusChange={handleLocusChange}
            height={600}
          />
        </div>
      </Card>
    </div>
  )
}
