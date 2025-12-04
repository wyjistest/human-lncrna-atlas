/**
 * GenomeBrowser Page
 * Route: /genome-browser
 *
 * Provides an interactive genome browser for visualizing lncRNA and regulatory data
 * using IGV.js integration.
 *
 * URL Parameters:
 * - gene: Gene name to load (e.g., CATG00000000011.1) - takes precedence
 * - locus: Genomic locus to navigate to (e.g., chr1:1000000-2000000)
 * - species: Species ID (1-4, default: 1 for Human)
 *
 * Two viewing modes:
 * 1. Species browsing mode: Select a species to load its full genome
 * 2. Gene search mode: Enter a gene name to auto-locate (maintains current functionality)
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Typography, Card, Input, Button, Space, message, Divider, Alert, Select, Radio, Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import { SearchOutlined, ExperimentOutlined, GlobalOutlined, AimOutlined, DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GenomeBrowser, { type GenomeBrowserHandle } from '@/components/GenomeBrowser'
import GenomeBrowserToolbar from '@/components/GenomeBrowser/GenomeBrowserToolbar'

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
  const urlLocus = searchParams.get('locus')

  // Determine initial mode based on URL params
  const getInitialMode = (): ViewMode => {
    if (urlGene) return 'gene'
    if (urlLocus) return 'species' // Locus mode uses species browsing
    if (urlSpecies) return 'species'
    return 'gene' // Default to gene mode for backward compatibility
  }

  // Get initial locus from URL
  const getInitialLocus = (): string | undefined => {
    return urlLocus || undefined
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
  const [currentLocus, setCurrentLocus] = useState<string | undefined>(getInitialLocus())
  const browserRef = useRef<HTMLDivElement>(null)
  const browserHandleRef = useRef<GenomeBrowserHandle | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  // Species options
  const speciesOptions = [
    { label: tCommon('species.human'), value: 1 },
    { label: tCommon('species.chimpanzee'), value: 2 },
    { label: tCommon('species.macaque'), value: 3 },
    { label: tCommon('species.marmoset'), value: 4 },
  ]

  // Sync URL params when mode/species/gene/locus changes
  useEffect(() => {
    const newParams = new URLSearchParams()

    if (viewMode === 'gene' && geneName) {
      newParams.set('gene', geneName)
    } else if (viewMode === 'species') {
      newParams.set('species', speciesId.toString())
      // Preserve locus parameter for navigation from Regulation page
      if (currentLocus) {
        newParams.set('locus', currentLocus)
      }
    }

    setSearchParams(newParams, { replace: true })
  }, [viewMode, speciesId, geneName, currentLocus, setSearchParams])

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

  // Handle browser ready callback
  const handleBrowserReady = useCallback((handle: GenomeBrowserHandle) => {
    browserHandleRef.current = handle
  }, [])

  // Handle toolbar search - navigate IGV to the selected locus
  const handleToolbarSearch = useCallback((locus: string) => {
    if (browserHandleRef.current) {
      browserHandleRef.current.navigateToLocus(locus)
        .then(() => {
          message.success(`Navigated to ${locus}`)
          setCurrentLocus(locus)
        })
        .catch((err) => {
          console.error('Navigation failed:', err)
          message.error(t('searchError') || 'Navigation failed')
        })
    } else {
      message.warning('Browser is loading, please wait...')
    }
  }, [t])

  // Generate filename for exports
  const getExportFilename = useCallback((extension: string) => {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
    const locusStr = currentLocus ? `-${currentLocus.replace(/[:\s]/g, '_')}` : ''
    return `igv-export${locusStr}-${timestamp}.${extension}`
  }, [currentLocus])

  // Export to SVG
  const handleExportSVG = useCallback(() => {
    if (!browserHandleRef.current) {
      message.warning(t('exportNotReady'))
      return
    }

    setIsExporting(true)
    try {
      const svg = browserHandleRef.current.toSVG()
      if (!svg) {
        message.error(t('exportFailed'))
        return
      }

      const blob = new Blob([svg], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = getExportFilename('svg')
      a.click()
      URL.revokeObjectURL(url)
      message.success(t('exportSuccess'))
    } catch (err) {
      console.error('SVG export failed:', err)
      message.error(t('exportFailed'))
    } finally {
      setIsExporting(false)
    }
  }, [t, getExportFilename])

  // Export to PNG (SVG -> Canvas -> PNG)
  const handleExportPNG = useCallback(() => {
    if (!browserHandleRef.current) {
      message.warning(t('exportNotReady'))
      return
    }

    setIsExporting(true)
    try {
      const svg = browserHandleRef.current.toSVG()
      if (!svg) {
        message.error(t('exportFailed'))
        setIsExporting(false)
        return
      }

      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        // Use a higher resolution for better quality
        const scale = 2
        canvas.width = img.width * scale
        canvas.height = img.height * scale
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.scale(scale, scale)
          ctx.drawImage(img, 0, 0)
          canvas.toBlob((blob) => {
            if (blob) {
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = getExportFilename('png')
              a.click()
              URL.revokeObjectURL(url)
              message.success(t('exportSuccess'))
            } else {
              message.error(t('exportFailed'))
            }
            setIsExporting(false)
          }, 'image/png')
        } else {
          message.error(t('exportFailed'))
          setIsExporting(false)
        }
      }
      img.onerror = () => {
        message.error(t('exportFailed'))
        setIsExporting(false)
      }
      // Encode SVG properly for data URI
      img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)))
    } catch (err) {
      console.error('PNG export failed:', err)
      message.error(t('exportFailed'))
      setIsExporting(false)
    }
  }, [t, getExportFilename])

  // Export menu items
  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'svg',
      label: t('exportSVG'),
      onClick: handleExportSVG,
    },
    {
      key: 'png',
      label: t('exportPNG'),
      onClick: handleExportPNG,
    },
  ]

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
        <Space orientation="vertical" style={{ width: '100%', marginBottom: 16 }}>
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

            {/* Export Button */}
            <Dropdown menu={{ items: exportMenuItems }} disabled={isExporting}>
              <Button icon={<DownloadOutlined />} loading={isExporting}>
                {t('export')}
              </Button>
            </Dropdown>
          </Space>

          {/* Mode-specific Alert */}
          {viewMode === 'gene' ? (
            <Alert
              type="info"
              showIcon
              title={t('geneLoadMode')}
              description={t('geneLoadModeDesc')}
              style={{ marginTop: 8 }}
            />
          ) : (
            <Alert
              type="success"
              showIcon
              title={t('speciesBrowseMode')}
              description={t('speciesBrowseModeDesc')}
              style={{ marginTop: 8 }}
            />
          )}

          {/* Remote genome loading note for non-Human species */}
          {speciesId !== 1 && viewMode === 'species' && (
            <Alert
              type="warning"
              showIcon
              title={t('remoteGenomeNote')}
              description={t('remoteGenomeNoteDesc')}
              style={{ marginTop: 8 }}
            />
          )}
        </Space>

        <Divider style={{ margin: '12px 0' }} />

        {/* Gene Search Input */}
        <Space orientation="vertical" style={{ width: '100%', marginBottom: 16 }}>
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

        {/* Gene Search Toolbar with AutoComplete */}
        <GenomeBrowserToolbar
          speciesId={speciesId}
          onSpeciesChange={handleSpeciesChange}
          onSearch={handleToolbarSearch}
          disabled={false}
        />

        {/* Genome Browser */}
        <div ref={browserRef}>
          <GenomeBrowser
            key={viewMode === 'gene' ? `gene-${geneName}` : `species-${speciesId}`}
            speciesId={speciesId}
            geneName={viewMode === 'gene' ? geneName : undefined}
            locus={currentLocus}
            onLocusChange={handleLocusChange}
            onBrowserReady={handleBrowserReady}
            height={750}
          />
        </div>
      </Card>
    </div>
  )
}
