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
 *
 * Phase 2.1: Added track controls for RepeatMasker layer
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Typography, Card, Input, Button, Space, message, Divider, Alert, Select, Radio, Dropdown, Switch, Collapse, Tag, Spin, InputNumber } from 'antd'
import type { MenuProps } from 'antd'
import { SearchOutlined, ExperimentOutlined, GlobalOutlined, AimOutlined, DownloadOutlined, SettingOutlined, BgColorsOutlined, LoadingOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import GenomeBrowser, { type GenomeBrowserHandle } from '@/components/GenomeBrowser'
import GenomeBrowserToolbar from '@/components/GenomeBrowser/GenomeBrowserToolbar'
import { RepeatMaskerLegend } from '@/components/RepeatMaskerLegend'
import { getRepeatMaskerClassTracks, type RepeatMaskerClassTrack } from '@/api/features'
import { genomeApi, type IGVTrackConfig } from '@/api/genome'
import { getMarkColor, getMarksGroupedByCategory, MARK_CONFIGS } from '@/config/markConfigs'
import type { MarkType } from '@/types/chipseq'

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
  const [browserReadyNonce, setBrowserReadyNonce] = useState(0)

  // Track controls state - RepeatMasker class-based tracks
  const [enabledRepeatClasses, setEnabledRepeatClasses] = useState<Record<string, boolean>>({
    SINE: false,
    LINE: false,
    LTR: false,
    DNA: false,
    Simple: false,
    LowComplexity: false,
    Other: false,
  })
  const [loadingRepeatClasses, setLoadingRepeatClasses] = useState<Record<string, boolean>>({})
  const [repeatClassTracks, setRepeatClassTracks] = useState<RepeatMaskerClassTrack[]>([])

  // ChIP-seq state
  const [showChIPSeq, setShowChIPSeq] = useState(false)
  const [selectedChIPSeqMarks, setSelectedChIPSeqMarks] = useState<string[]>([])

  // UCSC multiz-derived conservation tracks (backend returns available tracks dynamically per species/assembly)
  const [enabledMultizTracks, setEnabledMultizTracks] = useState<Record<string, boolean>>({})
  const [loadingMultizTracks, setLoadingMultizTracks] = useState<Record<string, boolean>>({})
  type MultizDisplayOverrides = {
    min?: number
    max?: number
    height?: number
    graphType?: string
    windowFunction?: string
  }
  const [multizDisplayOverrides, setMultizDisplayOverrides] = useState<Record<string, MultizDisplayOverrides>>({})

  // Color configuration for repeat classes
  const REPEAT_CLASS_COLORS: Record<string, string> = {
    SINE: '#FF0000',
    LINE: '#0000CC',
    LTR: '#00CC00',
    DNA: '#CC00CC',
    Simple: '#000000',
    LowComplexity: '#666666',
    Other: '#888888',
  }

  // Fetch available repeat class tracks when species changes
  useEffect(() => {
    const controller = new AbortController()

    const fetchRepeatClassTracks = async () => {
      try {
        const response = await getRepeatMaskerClassTracks(speciesId, controller.signal)
        if (controller.signal.aborted) {
          return
        }
        // API returns { tracks: [...], species_id, species_name }
        if (response.data?.data?.tracks) {
          setRepeatClassTracks(response.data.data.tracks)
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        console.error('Failed to fetch repeat class tracks:', error)
      }
    }
    fetchRepeatClassTracks()
    return () => controller.abort()
  }, [speciesId])

  // Fetch available ChIP-seq marks for the selected species
  const {
    data: availableChIPSeqMarks,
    isLoading: isLoadingChIPSeqMarks,
    error: chipseqMarksError
  } = useQuery({
    queryKey: ['chipseq-marks', speciesId],
    queryFn: async ({ signal }) => {
      const response = await genomeApi.getChIPSeqMarks(speciesId, signal)
      return response.data.data.marks
    },
    enabled: showChIPSeq, // Only fetch when ChIP-seq toggle is enabled
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    meta: { skipGlobalErrorHandler: true },
  })

  // Validate selected marks when available marks change
  // This ensures any previously selected marks that are no longer available get cleared
  useEffect(() => {
    if (availableChIPSeqMarks && selectedChIPSeqMarks.length > 0) {
      const availableMarkTypes = new Set(availableChIPSeqMarks.map(m => m.mark_name))
      const validMarks = selectedChIPSeqMarks.filter(mark => availableMarkTypes.has(mark))

      // Only update if there are invalid marks
      if (validMarks.length !== selectedChIPSeqMarks.length) {
        setSelectedChIPSeqMarks(validMarks)
        if (validMarks.length < selectedChIPSeqMarks.length) {
          message.warning(t('chipseq.someMarksUnavailable') || 'Some selected marks are not available for this species')
        }
      }
    }
  }, [availableChIPSeqMarks, selectedChIPSeqMarks, t])

  const {
    data: ucscMultizTracks,
    isLoading: isLoadingUCSCMultizTracks,
    error: ucscMultizTracksError,
  } = useQuery({
    queryKey: ['ucsc-multiz-tracks', speciesId],
    queryFn: async ({ signal }) => {
      const response = await genomeApi.getUCSCMultizTracks(speciesId, signal)
      return response.data.data.tracks
    },
    staleTime: 60 * 60 * 1000, // 1 hour
    meta: { skipGlobalErrorHandler: true },
  })

  // Sync multiz track toggles with backend-provided track list (dynamic, per species)
  useEffect(() => {
    if (!ucscMultizTracks) {
      return
    }
    setEnabledMultizTracks((prev) => {
      const next: Record<string, boolean> = {}
      for (const track of ucscMultizTracks) {
        next[track.id] = prev[track.id] ?? false
      }
      return next
    })
    setLoadingMultizTracks((prev) => {
      const next: Record<string, boolean> = {}
      for (const track of ucscMultizTracks) {
        if (prev[track.id]) {
          next[track.id] = true
        }
      }
      return next
    })
    setMultizDisplayOverrides((prev) => {
      const next: Record<string, MultizDisplayOverrides> = {}
      for (const track of ucscMultizTracks) {
        next[track.id] = prev[track.id] ?? {}
      }
      return next
    })
  }, [ucscMultizTracks])

  // Handle ChIP-seq toggle
  const handleChIPSeqToggle = useCallback((checked: boolean) => {
    setShowChIPSeq(checked)
    if (!checked) {
      // Clear selected marks when disabling ChIP-seq
      setSelectedChIPSeqMarks([])
    }
  }, [])

  // Handle ChIP-seq mark selection change
  const handleChIPSeqMarksChange = useCallback((marks: string[]) => {
    setSelectedChIPSeqMarks(marks)
  }, [])

  const enabledRepeatClassesRef = useRef(enabledRepeatClasses)
  useEffect(() => {
    enabledRepeatClassesRef.current = enabledRepeatClasses
  }, [enabledRepeatClasses])

  const enabledMultizTracksRef = useRef(enabledMultizTracks)
  useEffect(() => {
    enabledMultizTracksRef.current = enabledMultizTracks
  }, [enabledMultizTracks])

  // Load a specific repeat class track
  const loadRepeatClassTrack = useCallback(async (repeatClass: string) => {
    if (!browserHandleRef.current) {
      message.warning(t('exportNotReady'))
      return
    }

    const track = repeatClassTracks.find(t => t.id.includes(repeatClass))
    if (!track) {
      message.error(t('trackLoadFailed', { name: repeatClass }))
      return
    }

    setLoadingRepeatClasses(prev => ({ ...prev, [repeatClass]: true }))
    try {
      // Load the track - RepeatMaskerClassTrack is compatible with IGVTrackConfig
      await browserHandleRef.current.loadTrack(track as unknown as IGVTrackConfig)
      message.success(t('trackLoaded', { name: t(`repeatClasses.${repeatClass}`) }))
    } catch (error) {
      console.error(`Failed to load ${repeatClass} track:`, error)
      message.error(t('trackLoadFailed', { name: repeatClass }))
      // Revert the toggle
      setEnabledRepeatClasses(prev => ({ ...prev, [repeatClass]: false }))
    } finally {
      setLoadingRepeatClasses(prev => ({ ...prev, [repeatClass]: false }))
    }
  }, [repeatClassTracks, t])

  // Remove a specific repeat class track
  const removeRepeatClassTrack = useCallback((repeatClass: string) => {
    if (browserHandleRef.current) {
      const track = repeatClassTracks.find(t => t.id.includes(repeatClass))
      if (track) {
        browserHandleRef.current.removeTrack(track.id)
        if (track.name !== track.id) {
          browserHandleRef.current.removeTrack(track.name)
        }
        message.info(t('trackRemoved', { name: t(`repeatClasses.${repeatClass}`) }))
      }
    }
  }, [repeatClassTracks, t])

  // Handle repeat class toggle
  const handleRepeatClassToggle = useCallback(async (repeatClass: string, enabled: boolean) => {
    setEnabledRepeatClasses(prev => ({ ...prev, [repeatClass]: enabled }))

    if (enabled) {
      await loadRepeatClassTrack(repeatClass)
    } else {
      removeRepeatClassTrack(repeatClass)
    }
  }, [loadRepeatClassTrack, removeRepeatClassTrack])

  // Handle select all / deselect all
  const handleSelectAll = useCallback(() => {
    const allClasses = Object.keys(enabledRepeatClasses)
    allClasses.forEach(repeatClass => {
      if (!enabledRepeatClasses[repeatClass]) {
        handleRepeatClassToggle(repeatClass, true)
      }
    })
  }, [enabledRepeatClasses, handleRepeatClassToggle])

  const handleDeselectAll = useCallback(() => {
    const allClasses = Object.keys(enabledRepeatClasses)
    allClasses.forEach(repeatClass => {
      if (enabledRepeatClasses[repeatClass]) {
        handleRepeatClassToggle(repeatClass, false)
      }
    })
  }, [enabledRepeatClasses, handleRepeatClassToggle])

  const getMultizTrackLabel = useCallback((trackId: string) => {
    if (trackId === 'ucsc_multiz_phastCons100way_hg19') {
      return t('conservationTracks.phastCons100way')
    }
    if (trackId === 'ucsc_multiz_phyloP100way_hg19') {
      return t('conservationTracks.phyloP100way')
    }
    const fallback = ucscMultizTracks?.find(t => t.id === trackId)?.name
    return fallback || trackId
  }, [t, ucscMultizTracks])

  const buildMultizTrackConfig = useCallback((trackId: string) => {
    const base = ucscMultizTracks?.find(t => t.id === trackId)
    if (!base) return undefined
    const overrides = multizDisplayOverrides[trackId]
    if (!overrides || Object.keys(overrides).length === 0) return base
    return { ...base, ...overrides }
  }, [ucscMultizTracks, multizDisplayOverrides])

  const loadMultizTrack = useCallback(async (trackId: string, mode: 'load' | 'update' = 'load') => {
    if (!browserHandleRef.current) {
      message.warning(t('exportNotReady'))
      return
    }

    const track = buildMultizTrackConfig(trackId)
    if (!track) {
      message.error(t('trackLoadFailed', { name: getMultizTrackLabel(trackId) }))
      return
    }

    setLoadingMultizTracks(prev => ({ ...prev, [trackId]: true }))
    try {
      await browserHandleRef.current.loadTrack(track as unknown as IGVTrackConfig)
      if (mode === 'update') {
        message.success(t('conservationTracks.updated', { name: getMultizTrackLabel(trackId) }))
      } else {
        message.success(t('trackLoaded', { name: getMultizTrackLabel(trackId) }))
      }
    } catch (error) {
      console.error(`Failed to load UCSC multiz track ${trackId}:`, error)
      message.error(t('trackLoadFailed', { name: getMultizTrackLabel(trackId) }))
      setEnabledMultizTracks(prev => ({ ...prev, [trackId]: false }))
    } finally {
      setLoadingMultizTracks(prev => ({ ...prev, [trackId]: false }))
    }
  }, [buildMultizTrackConfig, getMultizTrackLabel, t])

  const removeMultizTrack = useCallback((trackId: string, silent: boolean = false) => {
    const handle = browserHandleRef.current
    if (!handle) return

    handle.removeTrack(trackId)
    const track = ucscMultizTracks?.find(t => t.id === trackId)
    if (track && track.name !== trackId) {
      handle.removeTrack(track.name)
    }
    if (!silent) {
      message.info(t('trackRemoved', { name: getMultizTrackLabel(trackId) }))
    }
  }, [getMultizTrackLabel, t, ucscMultizTracks])

  const setMultizOverrideNumber = useCallback(
    (trackId: string, key: 'min' | 'max' | 'height', value: number | null) => {
      setMultizDisplayOverrides((prev) => {
        const current = { ...(prev[trackId] ?? {}) }
        if (value === null) {
          delete current[key]
        } else {
          current[key] = value
        }
        return { ...prev, [trackId]: current }
      })
    },
    [],
  )

  const setMultizOverrideString = useCallback(
    (trackId: string, key: 'graphType' | 'windowFunction', value: string | undefined) => {
      setMultizDisplayOverrides((prev) => {
        const current = { ...(prev[trackId] ?? {}) }
        if (!value) {
          delete current[key]
        } else {
          current[key] = value
        }
        return { ...prev, [trackId]: current }
      })
    },
    [],
  )

  const applyMultizDisplay = useCallback(async (trackId: string) => {
    if (!enabledMultizTracks[trackId]) {
      message.info(t('conservationTracks.saved'))
      return
    }
    removeMultizTrack(trackId, true)
    await loadMultizTrack(trackId, 'update')
  }, [enabledMultizTracks, loadMultizTrack, removeMultizTrack, t])

  const resetMultizDisplay = useCallback(async (trackId: string) => {
    setMultizDisplayOverrides((prev) => {
      const next = { ...prev }
      delete next[trackId]
      return next
    })
    if (!enabledMultizTracks[trackId]) {
      message.info(t('conservationTracks.resetSaved'))
      return
    }
    removeMultizTrack(trackId, true)
    await loadMultizTrack(trackId, 'update')
  }, [enabledMultizTracks, loadMultizTrack, removeMultizTrack, t])

  const handleMultizTrackToggle = useCallback(async (trackId: string, enabled: boolean) => {
    setEnabledMultizTracks(prev => ({ ...prev, [trackId]: enabled }))

    if (enabled) {
      await loadMultizTrack(trackId)
    } else {
      removeMultizTrack(trackId)
    }
  }, [loadMultizTrack, removeMultizTrack])

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
    setBrowserReadyNonce(prev => prev + 1)
  }, [])

  // When IGV browser is reinitialized (gene/species switch), re-apply user-enabled tracks.
  useEffect(() => {
    const handle = browserHandleRef.current
    if (!handle) return

    const existingTrackNames = new Set(handle.getTrackNames())

    // Re-apply enabled RepeatMasker class tracks (if any)
    for (const repeatClass of Object.keys(enabledRepeatClassesRef.current)) {
      if (!enabledRepeatClassesRef.current[repeatClass]) continue
      const track = repeatClassTracks.find(t => t.id.includes(repeatClass))
      if (!track) continue
      if (existingTrackNames.has(track.id) || existingTrackNames.has(track.name)) continue
      // Best-effort: reload; errors are handled inside loadRepeatClassTrack
      loadRepeatClassTrack(repeatClass)
    }

    // Re-apply enabled UCSC multiz tracks (if any)
    for (const trackId of Object.keys(enabledMultizTracksRef.current)) {
      if (!enabledMultizTracksRef.current[trackId]) continue
      const track = ucscMultizTracks?.find(t => t.id === trackId)
      if (!track) continue
      if (existingTrackNames.has(track.id) || existingTrackNames.has(track.name)) continue
      loadMultizTrack(trackId)
    }
  }, [browserReadyNonce, loadMultizTrack, loadRepeatClassTrack, repeatClassTracks, ucscMultizTracks])

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

        {/* Track Controls - RepeatMasker Class-based Tracks */}
        <Collapse
          size="small"
          style={{ marginBottom: 16 }}
          items={[
            {
              key: 'trackControls',
              label: (
                <Space>
                  <SettingOutlined />
                  <span>{t('trackControls')}</span>
                </Space>
              ),
              children: (
                <Space orientation="vertical" style={{ width: '100%' }}>
                  {/* ChIP-seq Tracks */}
                  <Collapse
                    size="small"
                    items={[
                      {
                        key: 'chipseq',
                        label: (
                          <Space>
                            <BgColorsOutlined />
                            <span style={{ fontWeight: 500 }}>{t('chipseq.title')}</span>
                            {selectedChIPSeqMarks.length > 0 && (
                              <Tag color="blue">{selectedChIPSeqMarks.length}</Tag>
                            )}
                          </Space>
                        ),
                        children: (
                          <Space orientation="vertical" style={{ width: '100%' }}>
                            {/* ChIP-seq Toggle */}
                            <Space align="center">
                              <Switch
                                checked={showChIPSeq}
                                onChange={handleChIPSeqToggle}
                                size="small"
                              />
                              <span>{t('chipseq.enableTracks')}</span>
                            </Space>

                            {/* ChIP-seq Mark Selector */}
                            {showChIPSeq && (
                              <>
                                {isLoadingChIPSeqMarks ? (
                                  <Space>
                                    <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
                                    <span>{t('chipseq.loadingMarks')}</span>
                                  </Space>
                                ) : chipseqMarksError ? (
                                  <Alert
                                    type="error"
                                    showIcon
                                    message={t('chipseq.loadMarksFailed')}
                                  />
                                ) : (
                                  <>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                      {t('chipseq.selectMarksHint')}
                                    </Text>
                                    <Select
                                      mode="multiple"
                                      placeholder={t('chipseq.selectPlaceholder')}
                                      style={{ width: '100%' }}
                                      listHeight={400}
                                      value={selectedChIPSeqMarks}
                                      onChange={handleChIPSeqMarksChange}
                                      options={(() => {
                                        // Only show marks that exist in the database (from API)
                                        const availableMarkTypes = new Set(
                                          availableChIPSeqMarks?.map(m => m.mark_name) || []
                                        )

                                        // Filter grouped marks to only include available ones
                                        const allGroups = getMarksGroupedByCategory()
                                        const result = allGroups
                                          .map(group => {
                                            const filteredMarks = group.marks.filter(mark =>
                                              availableMarkTypes.has(mark.value)
                                            )

                                            // Skip empty categories
                                            if (filteredMarks.length === 0) return null

                                            return {
                                              label: group.categoryName,
                                              options: filteredMarks.map(mark => ({
                                                label: (
                                                  <Space>
                                                    <div
                                                      style={{
                                                        width: 12,
                                                        height: 12,
                                                        backgroundColor: mark.color,
                                                        borderRadius: 2,
                                                        display: 'inline-block',
                                                      }}
                                                    />
                                                    <span>{mark.label}</span>
                                                  </Space>
                                                ),
                                                value: mark.value,
                                              })),
                                            }
                                          })
                                          .filter((group): group is NonNullable<typeof group> => group !== null)
                                        return result
                                      })()}
                                      maxTagCount={3}
                                      allowClear
                                    />
                                    {/* Show selected marks preview */}
                                    {selectedChIPSeqMarks.length > 0 && (
                                      <Space wrap style={{ marginTop: 8 }}>
                                        {selectedChIPSeqMarks.map(mark => (
                                          <Tag
                                            key={mark}
                                            color={getMarkColor(mark as MarkType)}
                                            closable
                                            onClose={() => {
                                              setSelectedChIPSeqMarks(prev =>
                                                prev.filter(m => m !== mark)
                                              )
                                            }}
                                          >
                                            {MARK_CONFIGS[mark as MarkType]?.shortName || mark}
                                          </Tag>
                                        ))}
                                      </Space>
                                    )}
                                  </>
                                )}
                              </>
                            )}
                          </Space>
                        ),
                      },
                    ]}
                  />

	                  {/* RepeatMasker Grouped Tracks */}
	                  <Collapse
	                    size="small"
	                    items={[
                      {
                        key: 'repeatMasker',
                        label: <span style={{ fontWeight: 500 }}>{t('repeatClasses.title')}</span>,
                        children: (
                          <Space orientation="vertical" style={{ width: '100%' }}>
                            {/* Select All / Deselect All Buttons */}
                            <Space>
                              <Button size="small" onClick={handleSelectAll}>
                                {t('repeatClasses.selectAll')}
                              </Button>
                              <Button size="small" onClick={handleDeselectAll}>
                                {t('repeatClasses.deselectAll')}
                              </Button>
                            </Space>

                            {/* Individual Repeat Class Toggles */}
                            {Object.keys(enabledRepeatClasses).map((repeatClass) => (
                              <Space key={repeatClass} align="center" style={{ width: '100%' }}>
                                <div
                                  style={{
                                    width: 16,
                                    height: 16,
                                    backgroundColor: REPEAT_CLASS_COLORS[repeatClass],
                                    borderRadius: 2,
                                    border: '1px solid #d9d9d9',
                                  }}
                                />
                                <Switch
                                  checked={enabledRepeatClasses[repeatClass]}
                                  onChange={(checked) => handleRepeatClassToggle(repeatClass, checked)}
                                  loading={loadingRepeatClasses[repeatClass]}
                                  size="small"
                                />
                                <span>{t(`repeatClasses.${repeatClass}`)}</span>
                              </Space>
                            ))}
                          </Space>
                        ),
                      },
                    ]}
	                  />

	                  {/* UCSC Multiz (Conservation) Tracks */}
		                  <Collapse
		                    size="small"
		                    items={[
		                      {
		                        key: 'ucscMultiz',
		                        label: <span style={{ fontWeight: 500 }}>{t('conservationTracks.title')}</span>,
		                        children: (
		                          <Space orientation="vertical" style={{ width: '100%' }}>
		                            <Text type="secondary" style={{ fontSize: 12 }}>
		                              {t('conservationTracks.hint')}
		                            </Text>
	
		                            {isLoadingUCSCMultizTracks ? (
		                              <Space>
		                                <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
		                                <span>{tCommon('status.loading') || 'Loading...'}</span>
		                              </Space>
		                            ) : ucscMultizTracksError ? (
		                              <Alert
		                                type="error"
		                                showIcon
		                                message={t('trackLoadFailed', { name: t('conservationTracks.title') })}
		                              />
		                            ) : !ucscMultizTracks || ucscMultizTracks.length === 0 ? (
		                              <Alert
		                                type="info"
		                                showIcon
		                                message={t('conservationTracks.notAvailable')}
		                              />
		                            ) : (
		                              <Space orientation="vertical" style={{ width: '100%' }} size={12}>
		                                {ucscMultizTracks.map((track) => {
		                                  const overrides = multizDisplayOverrides[track.id] || {}
		                                  const graphTypeValue = overrides.graphType || (track.graphType as string | undefined) || '__default__'
		                                  const windowFnValue = overrides.windowFunction || (track.windowFunction as string | undefined) || '__default__'
		                                  return (
		                                    <Space key={track.id} orientation="vertical" style={{ width: '100%' }} size={6}>
		                                      <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
		                                        <Space align="center">
		                                          <Switch
		                                            checked={!!enabledMultizTracks[track.id]}
		                                            onChange={(checked) => handleMultizTrackToggle(track.id, checked)}
		                                            loading={loadingMultizTracks[track.id]}
		                                            size="small"
		                                          />
		                                          <span>{getMultizTrackLabel(track.id)}</span>
		                                        </Space>
		                                        <Space size={6}>
		                                          <Button size="small" onClick={() => applyMultizDisplay(track.id)}>
		                                            {t('conservationTracks.apply')}
		                                          </Button>
		                                          <Button size="small" onClick={() => resetMultizDisplay(track.id)}>
		                                            {t('conservationTracks.reset')}
		                                          </Button>
		                                        </Space>
		                                      </Space>
	
		                                      <Space size="small" wrap>
		                                        <Text type="secondary">{t('conservationTracks.settings.min')}</Text>
		                                        <InputNumber
		                                          size="small"
		                                          style={{ width: 92 }}
		                                          value={overrides.min ?? track.min}
		                                          onChange={(v) => setMultizOverrideNumber(track.id, 'min', v)}
		                                        />
		                                        <Text type="secondary">{t('conservationTracks.settings.max')}</Text>
		                                        <InputNumber
		                                          size="small"
		                                          style={{ width: 92 }}
		                                          value={overrides.max ?? track.max}
		                                          onChange={(v) => setMultizOverrideNumber(track.id, 'max', v)}
		                                        />
		                                        <Text type="secondary">{t('conservationTracks.settings.height')}</Text>
		                                        <InputNumber
		                                          size="small"
		                                          style={{ width: 92 }}
		                                          min={20}
		                                          max={300}
		                                          value={overrides.height ?? track.height}
		                                          onChange={(v) => setMultizOverrideNumber(track.id, 'height', v)}
		                                        />
		                                        <Text type="secondary">{t('conservationTracks.settings.graphType')}</Text>
		                                        <Select
		                                          size="small"
		                                          style={{ width: 120 }}
		                                          value={graphTypeValue}
		                                          options={[
		                                            { value: '__default__', label: t('conservationTracks.settings.default') },
		                                            { value: 'heatmap', label: t('conservationTracks.graphType.heatmap') },
		                                            { value: 'points', label: t('conservationTracks.graphType.points') },
		                                          ]}
		                                          onChange={(v) => setMultizOverrideString(track.id, 'graphType', v === '__default__' ? undefined : v)}
		                                        />
		                                        <Text type="secondary">{t('conservationTracks.settings.windowFunction')}</Text>
		                                        <Select
		                                          size="small"
		                                          style={{ width: 120 }}
		                                          value={windowFnValue}
		                                          options={[
		                                            { value: '__default__', label: t('conservationTracks.settings.default') },
		                                            { value: 'none', label: 'none' },
		                                            { value: 'min', label: 'min' },
		                                            { value: 'max', label: 'max' },
		                                          ]}
		                                          onChange={(v) => setMultizOverrideString(track.id, 'windowFunction', v === '__default__' ? undefined : v)}
		                                        />
		                                      </Space>
		                                    </Space>
		                                  )
		                                })}
		                              </Space>
		                            )}
		                          </Space>
		                        ),
		                      },
		                    ]}
		                  />
	                </Space>
	              ),
	            },
	          ]}
	        />

        {/* Genome Browser */}
        <div ref={browserRef} style={{ position: 'relative' }}>
          <GenomeBrowser
            key={viewMode === 'gene' ? `gene-${geneName}` : `species-${speciesId}`}
            speciesId={speciesId}
            geneName={viewMode === 'gene' ? geneName : undefined}
            locus={currentLocus}
            onLocusChange={handleLocusChange}
            onBrowserReady={handleBrowserReady}
            height={750}
            showChIPSeq={showChIPSeq}
            chipseqMarks={selectedChIPSeqMarks}
          />
          {/* RepeatMasker Legend - Show when any repeat class track is enabled */}
          {Object.values(enabledRepeatClasses).some(enabled => enabled) && (
            <RepeatMaskerLegend
              position="top-right"
              compact={false}
              defaultCollapsed={false}
              style={{ top: 60, right: 16 }}
            />
          )}
        </div>
      </Card>
    </div>
  )
}
