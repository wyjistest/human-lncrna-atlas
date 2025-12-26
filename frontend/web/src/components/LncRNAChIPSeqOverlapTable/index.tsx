/**
 * LncRNAChIPSeqOverlapTable Main Component
 * Phase 3.0 - Task 1.8 (Updated Phase 3.0 Phase 2)
 *
 * Main container component for lncRNA-ChIP-seq overlap analysis.
 * Displays overlaps between lncRNA binding sites and ChIP-seq peaks.
 *
 * Features:
 * - Advanced filtering (mark type, cell type, chromosome, thresholds)
 * - Statistics cards (Phase 2)
 * - Visualization charts (Phase 3.0 Phase 2)
 *   - Mark type distribution bar chart
 *   - Cell type distribution pie chart
 *   - Overlap heatmap matrix (collapsible)
 * - Sortable, paginated data table
 * - IGV Genome Browser integration (Phase 3.4)
 *   - Split layout (table top, IGV bottom)
 *   - Click table row to navigate IGV
 *   - Dynamic overlap track loading
 * - Export functionality (BED, CSV) (Phase 2)
 * - Responsive design
 *
 * Backend Integration:
 * - GET /api/v1/lncrna-chipseq-overlap (paginated query)
 * - GET /api/v1/lncrna-chipseq-overlap/summary (Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/heatmap (Phase 3.0 Phase 2)
 * - GET /api/v1/lncrna-chipseq-overlap/export (Phase 2)
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import {
  Space,
  Card,
  Button,
  message,
  Empty,
  Alert,
  Switch,
  Row,
  Col,
  Tabs,
  Dropdown,
  Modal,
  Tooltip,
  Spin,
  Collapse,
  Select,
  Tag,
  Typography,
} from 'antd'
import type { MenuProps } from 'antd'
import {
  DownloadOutlined,
  ReloadOutlined,
  FilterOutlined,
  BarChartOutlined,
  HeatMapOutlined,
  PieChartOutlined,
  FileTextOutlined,
  FileExcelOutlined,
  DownOutlined,
  InfoCircleOutlined,
  EyeOutlined,
  SyncOutlined,
  SettingOutlined,
  BgColorsOutlined,
  LoadingOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'

// Components
import { OverlapFilterPanel } from './OverlapFilterPanel'
import { OverlapTable } from './OverlapTable'
import { OverlapStatsCards } from './OverlapStatsCards'
import { OverlapMarkDistChart } from './OverlapMarkDistChart'
import { OverlapCellTypeChart } from './OverlapCellTypeChart'
import { OverlapHeatmapMatrix } from './OverlapHeatmapMatrix'
import { LoadingState } from '@/components/LoadingState'
import GenomeBrowser, { type GenomeBrowserHandle } from '@/components/GenomeBrowser'
import GenomeBrowserToolbar from '@/components/GenomeBrowser/GenomeBrowserToolbar'
import { RepeatMaskerLegend } from '@/components/RepeatMaskerLegend'

// API and configs
import { getRepeatMaskerClassTracks, type RepeatMaskerClassTrack } from '@/api/features'
import { genomeApi, type IGVTrackConfig } from '@/api/genome'
import { API_BASE_URL } from '@/config/api'
import { openInNewTab } from '@/utils/safeWindow'
import { getMarkColor, getMarksGroupedByCategory, MARK_CONFIGS } from '@/config/markConfigs'
import type { MarkType } from '@/types/chipseq'

const { Text } = Typography

// Hooks
import {
  useLncRNAChIPSeqOverlaps,
  useLncRNAChIPSeqOverlapSummary,
} from '@/hooks/useLncRNAChIPSeqOverlap'

// Types
import type { OverlapFilters, OverlapResult } from '@/types/lncRNAChIPSeqOverlap'

interface LncRNAChIPSeqOverlapTableProps {
  /** Optional: Pre-filter by lncRNA gene ID */
  lncrnaGeneId?: number
  /** Optional: Pre-filter by target gene ID */
  targetGeneId?: number
  /** Optional: Initial mark types (comma-separated) */
  initialMarkTypes?: string
  /** Optional: Initial cell types (comma-separated) */
  initialCellTypes?: string
  /** Optional: Initial chromosome filter (undefined = all chromosomes, requires materialized view optimization) */
  initialChromosome?: string
  /** Default page size */
  defaultPageSize?: number
  /** Enable statistics cards (Phase 2 feature) */
  enableStats?: boolean
  /** Enable export functionality (Phase 2 feature) */
  enableExport?: boolean
  /** Enable visualization charts (Phase 3.0 Phase 2 feature) */
  enableVisualization?: boolean
  /** Enable IGV genome browser integration (Phase 3.4 feature) */
  enableIGV?: boolean
}

/**
 * LncRNAChIPSeqOverlapTable Component
 *
 * Comprehensive viewer for lncRNA-ChIP-seq overlap analysis.
 * Allows filtering, sorting, and browsing overlap data.
 *
 * @example Basic usage
 * ```tsx
 * <LncRNAChIPSeqOverlapTable />
 * ```
 *
 * @example Pre-filtered by lncRNA
 * ```tsx
 * <LncRNAChIPSeqOverlapTable
 *   lncrnaGeneId={123}
 *   initialMarkTypes="H3K27me3,H3K4me3"
 * />
 * ```
 *
 * @example With statistics (Phase 2)
 * ```tsx
 * <LncRNAChIPSeqOverlapTable
 *   enableStats
 *   enableExport
 * />
 * ```
 */
export function LncRNAChIPSeqOverlapTable({
  lncrnaGeneId,
  targetGeneId,
  initialMarkTypes,
  initialCellTypes,
  initialChromosome,  // No default - allows querying all chromosomes (requires backend materialized view)
  defaultPageSize = 20,
  enableStats = false,
  enableExport = false,
  enableVisualization = false,
  enableIGV = false,
}: LncRNAChIPSeqOverlapTableProps) {
  const { t } = useTranslation('overlap')
  const { t: tCommon } = useTranslation('common')
  const { t: tGenomeBrowser } = useTranslation('genomeBrowser')

  // UI state
  const [showFilters, setShowFilters] = useState(true)
  const [showStats, setShowStats] = useState(enableStats)
  const [showVisualization, setShowVisualization] = useState(enableVisualization)
  const [showIGV, setShowIGV] = useState(enableIGV)
  const [activeTab, setActiveTab] = useState<string>('table')

  // IGV browser handle reference
  const browserHandleRef = useRef<GenomeBrowserHandle | null>(null)
  const browserContainerRef = useRef<HTMLDivElement>(null)

  // Overlap track state
  const [autoSyncTrack, setAutoSyncTrack] = useState(false)
  const [trackLoading, setTrackLoading] = useState(false)

  // IGV control state (like GenomeBrowser page)
  const [igvSpeciesId, setIgvSpeciesId] = useState<number>(1) // Default to Human
  const [currentLocus, setCurrentLocus] = useState<string | undefined>()
  const [isExporting, setIsExporting] = useState(false)

  // RepeatMasker track controls
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

  // RepeatMasker color configuration
  const REPEAT_CLASS_COLORS: Record<string, string> = {
    SINE: '#FF0000',
    LINE: '#0000CC',
    LTR: '#00CC00',
    DNA: '#CC00CC',
    Simple: '#000000',
    LowComplexity: '#666666',
    Other: '#888888',
  }

  // Filter state - No default chromosome (backend uses materialized view for all-chromosome queries)
  // NOTE: This must be defined BEFORE loadOverlapTrack which depends on filters
  const [filters, setFilters] = useState<OverlapFilters>(() => ({
    lncrna_gene_id: lncrnaGeneId,
    target_gene_id: targetGeneId,
    mark_type: initialMarkTypes,
    cell_type: initialCellTypes,
    chromosome: initialChromosome,
    page: 1,
    page_size: defaultPageSize,
  }))

  // Load Overlap Track into IGV browser
  // NOTE: This callback must be defined AFTER filters state
  const loadOverlapTrack = useCallback(async () => {
    if (!browserHandleRef.current) {
      message.warning(t('igv.browserNotReady', 'IGV browser is not ready'))
      return
    }

    setTrackLoading(true)
    message.loading({
      content: t('igv.trackLoading', 'Loading track...'),
      key: 'overlapTrack',
      duration: 0,
    })

    try {
      // Remove existing overlap track first
      browserHandleRef.current.removeTrack('Overlap Track')

      // Build URL parameters from current filters
      const params = new URLSearchParams()
      if (filters.chromosome) params.append('chr', filters.chromosome)
      if (filters.mark_type) params.append('mark_type', filters.mark_type)
      if (filters.cell_type) params.append('cell_line', filters.cell_type)
      if (filters.min_overlap_length !== undefined) {
        params.append('min_overlap_length', String(filters.min_overlap_length))
      }
      if (filters.min_binding_affinity !== undefined) {
        params.append('min_binding_affinity', String(filters.min_binding_affinity))
      }

      // Load new track with dynamic URL
      await browserHandleRef.current.loadTrack({
        name: 'Overlap Track',
        type: 'annotation',
        format: 'bed',
        url: `${API_BASE_URL}/api/v1/igv/overlap-track?${params.toString()}`,
        displayMode: 'EXPANDED',
        color: '#722ed1',  // Purple color for overlap track
        height: 60,
        removable: true,
        visibilityWindow: 5000000,  // 5MB window for BED format
      })

      message.success({
        content: t('igv.trackLoaded', 'Track loaded'),
        key: 'overlapTrack',
        duration: 2,
      })
    } catch (error) {
      console.error('Failed to load overlap track:', error)
      message.error({
        content: t('igv.trackLoadError', 'Failed to load track'),
        key: 'overlapTrack',
        duration: 3,
      })
    } finally {
      setTrackLoading(false)
    }
  }, [filters, t])

  // Load Regulation Track into IGV browser
  // Shows lncRNA → target gene regulatory relationships in the current view
  const loadRegulationTrack = useCallback(async () => {
    if (!browserHandleRef.current) {
      message.warning(t('igv.browserNotReady', 'IGV browser is not ready'))
      return
    }

    setTrackLoading(true)
    message.loading({
      content: t('igv.trackLoading', 'Loading track...'),
      key: 'regulationTrack',
      duration: 0,
    })

    try {
      // Remove existing regulation track first
      browserHandleRef.current.removeTrack('Regulation Track')

      // Build URL parameters - use chromosome filter if available
      const params = new URLSearchParams()
      if (filters.chromosome) params.append('chr', filters.chromosome)

      // Load new track with dynamic URL
      await browserHandleRef.current.loadTrack({
        name: 'Regulation Track',
        type: 'annotation',
        format: 'bed',
        url: `${API_BASE_URL}/api/v1/igv/tracks/regulations/${igvSpeciesId}.bed?${params.toString()}`,
        displayMode: 'EXPANDED',
        color: '#13c2c2',  // Cyan/teal color for regulation track (distinct from purple overlap)
        height: 60,
        removable: true,
        visibilityWindow: 5000000,  // 5MB window for BED format
      })

      message.success({
        content: t('igv.trackLoaded', 'Track loaded'),
        key: 'regulationTrack',
        duration: 2,
      })
    } catch (error) {
      console.error('Failed to load regulation track:', error)
      message.error({
        content: t('igv.trackLoadError', 'Failed to load track'),
        key: 'regulationTrack',
        duration: 3,
      })
    } finally {
      setTrackLoading(false)
    }
  }, [filters.chromosome, igvSpeciesId, t])

  // Auto-sync track when filters change (if enabled)
  useEffect(() => {
    if (autoSyncTrack && showIGV && browserHandleRef.current) {
      // Debounce the auto-sync to avoid rapid re-loads
      const timer = setTimeout(() => {
        loadOverlapTrack()
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [autoSyncTrack, showIGV, filters.chromosome, filters.mark_type, filters.cell_type, loadOverlapTrack])

  // ==================== IGV Control Logic (from GenomeBrowser page) ====================

  // Fetch available repeat class tracks when species changes
  useEffect(() => {
    const controller = new AbortController()

    const fetchRepeatClassTracks = async () => {
      try {
        const response = await getRepeatMaskerClassTracks(igvSpeciesId, controller.signal)
        if (controller.signal.aborted) {
          return
        }
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
    if (showIGV) {
      fetchRepeatClassTracks()
    }
    return () => controller.abort()
  }, [igvSpeciesId, showIGV])

  // Fetch available ChIP-seq marks for the selected species
  const {
    data: availableChIPSeqMarks,
    isLoading: isLoadingChIPSeqMarks,
    error: chipseqMarksError
  } = useQuery({
    queryKey: ['chipseq-marks', igvSpeciesId],
    queryFn: async ({ signal }) => {
      const response = await genomeApi.getChIPSeqMarks(igvSpeciesId, signal)
      return response.data.data.marks
    },
    enabled: showChIPSeq && showIGV,
    staleTime: 5 * 60 * 1000,
  })

  // Validate selected marks when available marks change
  useEffect(() => {
    if (availableChIPSeqMarks && selectedChIPSeqMarks.length > 0) {
      const availableMarkTypes = new Set(availableChIPSeqMarks.map(m => m.mark_name))
      const validMarks = selectedChIPSeqMarks.filter(mark => availableMarkTypes.has(mark))
      if (validMarks.length !== selectedChIPSeqMarks.length) {
        setSelectedChIPSeqMarks(validMarks)
        if (validMarks.length < selectedChIPSeqMarks.length) {
          message.warning(tGenomeBrowser('chipseq.someMarksUnavailable') || 'Some selected marks are not available for this species')
        }
      }
    }
  }, [availableChIPSeqMarks, selectedChIPSeqMarks, tGenomeBrowser])

  // Handle ChIP-seq toggle
  const handleChIPSeqToggle = useCallback((checked: boolean) => {
    setShowChIPSeq(checked)
    if (!checked) {
      setSelectedChIPSeqMarks([])
    }
  }, [])

  // Handle ChIP-seq mark selection change
  const handleChIPSeqMarksChange = useCallback((marks: string[]) => {
    setSelectedChIPSeqMarks(marks)
  }, [])

  // Load a specific repeat class track
  const loadRepeatClassTrack = useCallback(async (repeatClass: string) => {
    if (!browserHandleRef.current) {
      message.warning(tGenomeBrowser('exportNotReady'))
      return
    }

    const track = repeatClassTracks.find(t => t.id.includes(repeatClass))
    if (!track) {
      message.error(tGenomeBrowser('trackLoadFailed', { name: repeatClass }))
      return
    }

    setLoadingRepeatClasses(prev => ({ ...prev, [repeatClass]: true }))
    try {
      await browserHandleRef.current.loadTrack(track as unknown as IGVTrackConfig)
      message.success(tGenomeBrowser('trackLoaded', { name: tGenomeBrowser(`repeatClasses.${repeatClass}`) }))
    } catch (error) {
      console.error(`Failed to load ${repeatClass} track:`, error)
      message.error(tGenomeBrowser('trackLoadFailed', { name: repeatClass }))
      setEnabledRepeatClasses(prev => ({ ...prev, [repeatClass]: false }))
    } finally {
      setLoadingRepeatClasses(prev => ({ ...prev, [repeatClass]: false }))
    }
  }, [repeatClassTracks, tGenomeBrowser])

  // Remove a specific repeat class track
  const removeRepeatClassTrack = useCallback((repeatClass: string) => {
    if (browserHandleRef.current) {
      const track = repeatClassTracks.find(t => t.id.includes(repeatClass))
      if (track) {
        browserHandleRef.current.removeTrack(track.id)
        message.info(tGenomeBrowser('trackRemoved', { name: tGenomeBrowser(`repeatClasses.${repeatClass}`) }))
      }
    }
  }, [repeatClassTracks, tGenomeBrowser])

  // Handle repeat class toggle
  const handleRepeatClassToggle = useCallback(async (repeatClass: string, enabled: boolean) => {
    setEnabledRepeatClasses(prev => ({ ...prev, [repeatClass]: enabled }))
    if (enabled) {
      await loadRepeatClassTrack(repeatClass)
    } else {
      removeRepeatClassTrack(repeatClass)
    }
  }, [loadRepeatClassTrack, removeRepeatClassTrack])

  // Handle select all / deselect all for RepeatMasker
  const handleSelectAllRepeats = useCallback(() => {
    Object.keys(enabledRepeatClasses).forEach(repeatClass => {
      if (!enabledRepeatClasses[repeatClass]) {
        handleRepeatClassToggle(repeatClass, true)
      }
    })
  }, [enabledRepeatClasses, handleRepeatClassToggle])

  const handleDeselectAllRepeats = useCallback(() => {
    Object.keys(enabledRepeatClasses).forEach(repeatClass => {
      if (enabledRepeatClasses[repeatClass]) {
        handleRepeatClassToggle(repeatClass, false)
      }
    })
  }, [enabledRepeatClasses, handleRepeatClassToggle])

  // Handle species change for IGV
  const handleIgvSpeciesChange = useCallback((value: number) => {
    setIgvSpeciesId(value)
    setCurrentLocus(undefined)
    // Reset tracks when species changes
    setSelectedChIPSeqMarks([])
    setEnabledRepeatClasses({
      SINE: false, LINE: false, LTR: false, DNA: false,
      Simple: false, LowComplexity: false, Other: false,
    })
  }, [])

  // Handle locus change from IGV browser
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
          message.error(tGenomeBrowser('searchError') || 'Navigation failed')
        })
    } else {
      message.warning('Browser is loading, please wait...')
    }
  }, [tGenomeBrowser])

  // Generate filename for exports
  const getExportFilename = useCallback((extension: string) => {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
    const locusStr = currentLocus ? `-${currentLocus.replace(/[:\s]/g, '_')}` : ''
    return `igv-overlap-export${locusStr}-${timestamp}.${extension}`
  }, [currentLocus])

  // Export to SVG
  const handleExportSVG = useCallback(() => {
    if (!browserHandleRef.current) {
      message.warning(tGenomeBrowser('exportNotReady'))
      return
    }

    setIsExporting(true)
    try {
      const svg = browserHandleRef.current.toSVG()
      if (!svg) {
        message.error(tGenomeBrowser('exportFailed'))
        return
      }

      const blob = new Blob([svg], { type: 'image/svg+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = getExportFilename('svg')
      a.click()
      URL.revokeObjectURL(url)
      message.success(tGenomeBrowser('exportSuccess'))
    } catch (err) {
      console.error('SVG export failed:', err)
      message.error(tGenomeBrowser('exportFailed'))
    } finally {
      setIsExporting(false)
    }
  }, [tGenomeBrowser, getExportFilename])

  // Export to PNG
  const handleExportPNG = useCallback(() => {
    if (!browserHandleRef.current) {
      message.warning(tGenomeBrowser('exportNotReady'))
      return
    }

    setIsExporting(true)
    try {
      const svg = browserHandleRef.current.toSVG()
      if (!svg) {
        message.error(tGenomeBrowser('exportFailed'))
        setIsExporting(false)
        return
      }

      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
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
              message.success(tGenomeBrowser('exportSuccess'))
            } else {
              message.error(tGenomeBrowser('exportFailed'))
            }
            setIsExporting(false)
          }, 'image/png')
        } else {
          message.error(tGenomeBrowser('exportFailed'))
          setIsExporting(false)
        }
      }
      img.onerror = () => {
        message.error(tGenomeBrowser('exportFailed'))
        setIsExporting(false)
      }
      img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)))
    } catch (err) {
      console.error('PNG export failed:', err)
      message.error(tGenomeBrowser('exportFailed'))
      setIsExporting(false)
    }
  }, [tGenomeBrowser, getExportFilename])

  // Export menu items for IGV
  const igvExportMenuItems: MenuProps['items'] = [
    { key: 'svg', label: tGenomeBrowser('exportSVG'), onClick: handleExportSVG },
    { key: 'png', label: tGenomeBrowser('exportPNG'), onClick: handleExportPNG },
  ]

  // ==================== End IGV Control Logic ====================

  // Data fetching
  const {
    data: overlapData,
    isLoading: dataLoading,
    error: dataError,
    refetch: refetchData,
  } = useLncRNAChIPSeqOverlaps(filters)

  const {
    data: summaryData,
    isLoading: summaryLoading,
  } = useLncRNAChIPSeqOverlapSummary(filters, {
    enabled: showStats && enableStats,
  })

  // Handle filter changes
  const handleFiltersChange = useCallback(
    (newFilters: Partial<OverlapFilters>) => {
      setFilters((prev) => ({
        ...prev,
        ...newFilters,
      }))
    },
    []
  )

  // Reset all filters - No chromosome default (backend handles via materialized view)
  const handleResetFilters = useCallback(() => {
    setFilters({
      lncrna_gene_id: lncrnaGeneId,
      target_gene_id: targetGeneId,
      mark_type: initialMarkTypes,
      cell_type: initialCellTypes,
      chromosome: initialChromosome,
      page: 1,
      page_size: defaultPageSize,
    })
    message.success(tCommon('message.filtersReset', 'Filters reset'))
  }, [lncrnaGeneId, targetGeneId, initialMarkTypes, initialCellTypes, initialChromosome, defaultPageSize, tCommon])

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.mark_type) count++
    if (filters.cell_type) count++
    if (filters.chromosome) count++
    if (filters.min_overlap_length) count++
    if (filters.min_binding_affinity) count++
    return count
  }, [filters])

  // Handle table row click to navigate IGV
  const handleRowClick = useCallback((record: OverlapResult) => {
    if (!browserHandleRef.current) {
      message.warning(t('igv.browserNotReady', 'IGV browser is not ready'))
      return
    }

    // Calculate locus with padding (50kb on each side)
    const padding = 50000
    const start = Math.max(0, record.overlap_start - padding)
    const end = record.overlap_end + padding
    const locus = `${record.chromosome}:${start}-${end}`

    // Navigate IGV
    browserHandleRef.current.navigateToLocus(locus)
      .then(() => {
        message.success(
          t('igv.navigateSuccess', {
            lncrna: record.lncrna_name || `Gene ${record.lncrna_gene_id}`,
            defaultValue: `Navigated to ${record.lncrna_name}`
          })
        )
      })
      .catch((error) => {
        console.error('IGV navigation failed:', error)
        message.error(t('igv.navigateError', 'Failed to navigate IGV'))
      })
  }, [t])

  // Perform export - internal function
  // Note: exportOverlaps opens a new window for download, which has limited error handling
  const performExport = useCallback(
    (format: 'bed' | 'csv') => {
      message.loading({
        content: t('export.starting', `Starting ${format.toUpperCase()} export...`),
        key: 'export',
        duration: 0 // Keep loading until we update it
      })

      try {
        // Build the export URL for validation
        const params = new URLSearchParams()

        // Validate filters and build URL parameters
        if (filters.lncrna_gene_id) params.append('lncrna_gene_id', String(filters.lncrna_gene_id))
        if (filters.target_gene_id) params.append('target_gene_id', String(filters.target_gene_id))
        if (filters.mark_type) params.append('mark_type', filters.mark_type)
        if (filters.cell_type) params.append('cell_type', filters.cell_type)
        if (filters.chromosome) params.append('chromosome', filters.chromosome)
        if (filters.min_overlap_length !== undefined) params.append('min_overlap_length', String(filters.min_overlap_length))
        if (filters.min_binding_affinity !== undefined) params.append('min_binding_affinity', String(filters.min_binding_affinity))
        params.append('format', format)

        const exportUrl = `${API_BASE_URL}/api/v1/lncrna-chipseq-overlap/export?${params.toString()}`

        // Open in new window (secure, with tabnabbing protection)
        const result = openInNewTab(exportUrl)

        // Check if popup was blocked
        if (result.blocked) {
          message.warning({
            content: t('export.popupBlocked', 'Please allow popups to download the file, or try right-clicking and "Save As"'),
            key: 'export',
            duration: 5
          })
        } else {
          // Successful window open - show success message after delay
          setTimeout(() => {
            message.success({
              content: t('export.success', `${format.toUpperCase()} export started - check your downloads`),
              key: 'export',
              duration: 3
            })
          }, 1000)
        }
      } catch (error) {
        console.error('Export failed:', error)
        message.error({
          content: t('export.error.failed', `Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`),
          key: 'export',
          duration: 5
        })
      }
    },
    [filters, t]
  )

  // Export data handler with large data warning
  const handleExport = useCallback(
    (format: 'bed' | 'csv') => {
      // Check for large export warning (no chromosome filter)
      if (!filters.chromosome && overlapData && overlapData.total > 50000) {
        Modal.confirm({
          title: t('export.largeDataWarning.title'),
          content: t('export.largeDataWarning.noChromosomeWarning'),
          okText: t('export.largeDataWarning.proceed'),
          cancelText: t('export.largeDataWarning.cancel'),
          onOk: () => performExport(format),
        })
        return
      }

      performExport(format)
    },
    [filters, overlapData, t, performExport]
  )

  // Check if querying all chromosomes (potentially large query)
  const isAllChromosomeQuery = !filters.chromosome

  // Loading state - show enhanced loading for all-chromosome queries
  if (dataLoading && !overlapData && !dataError) {
    return (
      <LoadingState
        message={isAllChromosomeQuery
          ? t('loading.allChromosomes', 'Loading data from all chromosomes...')
          : t('loading.data', 'Loading data...')
        }
        tip={isAllChromosomeQuery
          ? t('loading.allChromosomesTip', 'This query covers all chromosomes and may take longer. Consider filtering by chromosome for faster results.')
          : undefined
        }
        showProgress={isAllChromosomeQuery}
        estimatedTime={isAllChromosomeQuery ? 15 : undefined}
      />
    )
  }

  // Determine if we should show the table or empty state
  const hasData = overlapData && overlapData.total > 0
  const showEmptyState = !dataError && overlapData && overlapData.total === 0

  // Main layout container style
  // When IGV is shown, use a taller viewport to accommodate both table and browser
  const containerStyle: React.CSSProperties = enableIGV && showIGV
    ? { display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', minHeight: 1200, overflow: 'hidden' }
    : {}

  return (
    <div style={containerStyle}>
      {/* Top Section: Table and Filters (when IGV enabled and shown) */}
      <div style={enableIGV && showIGV ? { flex: '0 0 40%', overflow: 'auto', borderBottom: '2px solid #e8e8e8', padding: '16px' } : {}}>
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* Error Alert - Show at top but allow filter panel to remain visible */}
      {dataError && (
        <Alert
          type="error"
          message={t('error.title', 'Loading Failed')}
          description={
            <Space orientation="vertical" size="small">
              <span>{dataError.message || t('error.unknown', 'An unknown error occurred')}</span>
              <span style={{ fontSize: 12, color: '#999' }}>
                {t('error.tryAdjustFilters', 'Try adjusting filters or retry the request')}
              </span>
            </Space>
          }
          action={
            <Button size="small" onClick={() => refetchData()} loading={dataLoading}>
              {tCommon('action.retry', 'Retry')}
            </Button>
          }
          showIcon
          closable
          style={{ marginBottom: 0 }}
        />
      )}

      {/* Header with controls */}
      <Card size="small">
        <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <Space wrap>
            <Button
              icon={<FilterOutlined />}
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? t('action.hideFilters', 'Hide Filters') : t('action.showFilters', 'Show Filters')}
            </Button>

            {enableIGV && (
              <Space>
                <HeatMapOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showIGV', 'Show IGV Browser')}:
                </span>
                <Switch
                  checked={showIGV}
                  onChange={setShowIGV}
                  size="small"
                />
              </Space>
            )}

            {/* Overlap Track Controls - Only show when IGV is enabled and visible */}
            {enableIGV && showIGV && (
              <Space split={<span style={{ color: '#d9d9d9' }}>|</span>}>
                <Tooltip title={t('igv.loadOverlapTrackTip', 'Display overlap data in IGV')}>
                  <Button
                    icon={trackLoading ? <Spin size="small" /> : <EyeOutlined />}
                    onClick={loadOverlapTrack}
                    disabled={trackLoading}
                    size="small"
                  >
                    {t('igv.loadOverlapTrack', 'Load Overlap Track')}
                  </Button>
                </Tooltip>
                <Tooltip title={t('igv.loadRegulationTrackTip', 'Display lncRNA-target regulation relationships in IGV')}>
                  <Button
                    icon={trackLoading ? <Spin size="small" /> : <LinkOutlined />}
                    onClick={loadRegulationTrack}
                    disabled={trackLoading}
                    size="small"
                  >
                    {t('igv.loadRegulationTrack', 'Load Regulation Track')}
                  </Button>
                </Tooltip>
                <Space size="small">
                  <SyncOutlined spin={autoSyncTrack && trackLoading} />
                  <span style={{ fontSize: 12 }}>{t('igv.autoSync', 'Auto Sync')}:</span>
                  <Switch
                    checked={autoSyncTrack}
                    onChange={setAutoSyncTrack}
                    size="small"
                    checkedChildren={t('igv.autoSync', 'Auto')}
                    unCheckedChildren={t('igv.manual', 'Manual')}
                  />
                </Space>
              </Space>
            )}

            {enableStats && (
              <Space>
                <BarChartOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showStats', 'Show Statistics')}:
                </span>
                <Switch
                  checked={showStats}
                  onChange={setShowStats}
                  size="small"
                />
              </Space>
            )}

            {enableVisualization && (
              <Space>
                <PieChartOutlined />
                <span style={{ fontSize: 13 }}>
                  {t('action.showVisualization', 'Show Visualization')}:
                </span>
                <Switch
                  checked={showVisualization}
                  onChange={setShowVisualization}
                  size="small"
                />
              </Space>
            )}

            <Button
              icon={<ReloadOutlined />}
              onClick={() => refetchData()}
              loading={dataLoading}
            >
              {tCommon('action.refresh', 'Refresh')}
            </Button>
          </Space>

          {enableExport && overlapData && overlapData.total > 0 && (
            <Tooltip
              title={
                activeFilterCount > 0
                  ? t('export.tooltipWithFilters', { count: activeFilterCount })
                  : t('export.tooltip')
              }
            >
              <Dropdown.Button
                icon={<DownOutlined />}
                menu={{
                  items: [
                    {
                      key: 'bed',
                      label: t('export.bed'),
                      icon: <FileTextOutlined />,
                    },
                    {
                      key: 'csv',
                      label: t('export.csv'),
                      icon: <FileExcelOutlined />,
                    },
                  ],
                  onClick: ({ key }) => handleExport(key as 'bed' | 'csv'),
                }}
                onClick={() => handleExport('bed')}
              >
                <DownloadOutlined />
                {t('export.button')}
              </Dropdown.Button>
            </Tooltip>
          )}
        </Space>
      </Card>

      {/* Phase 2 Notice */}
      {enableStats && !showStats && (
        <Alert
          type="info"
          message={t('notice.statsPhase2Title', 'Statistics Feature')}
          description={t(
            'notice.statsPhase2Desc',
            'Enable statistics to see aggregate metrics and distributions (Phase 2 feature)'
          )}
          showIcon
          closable
        />
      )}

      {/* Statistics Cards (Phase 2) */}
      {showStats && enableStats && (
        <OverlapStatsCards
          summary={summaryData}
          loading={summaryLoading}
        />
      )}

      {/* Visualization Charts (Phase 3.0 Phase 2) */}
      {showVisualization && enableVisualization && summaryData && (
        <Card
          title={
            <Space>
              <BarChartOutlined />
              {t('visualization.title', 'Overlap Visualizations')}
            </Space>
          }
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'charts',
                label: (
                  <Space>
                    <PieChartOutlined />
                    {t('visualization.distributionCharts', 'Distribution Charts')}
                  </Space>
                ),
                children: (
                  <Row gutter={[16, 16]}>
                    {/* Mark Type Distribution Bar Chart */}
                    <Col xs={24} lg={12}>
                      <Card size="small" bordered={false}>
                        <OverlapMarkDistChart
                          data={summaryData.by_mark_type}
                          loading={summaryLoading}
                        />
                      </Card>
                    </Col>
                    {/* Cell Type Distribution Pie Chart */}
                    <Col xs={24} lg={12}>
                      <Card size="small" bordered={false}>
                        <OverlapCellTypeChart
                          data={summaryData.by_cell_type}
                          loading={summaryLoading}
                        />
                      </Card>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'heatmap',
                label: (
                  <Space>
                    <HeatMapOutlined />
                    {t('visualization.heatmap', 'Heatmap Matrix')}
                  </Space>
                ),
                children: (
                  <OverlapHeatmapMatrix
                    initialXAxis="mark_type"
                    initialYAxis="lncrna"
                    initialMetric="count"
                    filters={filters}
                    showControls
                  />
                ),
              },
              {
                key: 'table',
                label: t('visualization.tableView', 'Table View'),
                children: null, // Table is shown outside tabs
              },
            ]}
          />
        </Card>
      )}

      {/* All Chromosomes Info Alert */}
      {isAllChromosomeQuery && !dataLoading && hasData && (
        <Alert
          type="info"
          icon={<InfoCircleOutlined />}
          message={t('info.allChromosomesQuery', 'Querying All Chromosomes')}
          description={t(
            'info.allChromosomesDesc',
            'You are viewing data from all chromosomes. For faster queries and exports, consider selecting a specific chromosome from the filter panel.'
          )}
          showIcon
          closable
          style={{ marginBottom: 0 }}
        />
      )}

      {/* Filter Panel */}
      {showFilters && (
        <OverlapFilterPanel
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onReset={handleResetFilters}
        />
      )}

      {/* Data Table */}
      <Card
        title={
          <Space>
            {t('table.title', 'lncRNA-ChIP-seq Overlaps')}
            {hasData && (
              <span style={{ fontWeight: 'normal', color: '#999' }}>
                ({overlapData.total.toLocaleString()})
              </span>
            )}
          </Space>
        }
      >
        {/* Show table when we have data */}
        {hasData && (
          <OverlapTable
            items={overlapData.items}
            total={overlapData.total}
            page={overlapData.page}
            pageSize={overlapData.page_size}
            loading={dataLoading}
            filters={filters}
            onFiltersChange={handleFiltersChange}
            onRowClick={enableIGV && showIGV ? handleRowClick : undefined}
          />
        )}

        {/* Empty state - no data found with current filters */}
        {showEmptyState && (
          <Empty
            description={
              <Space orientation="vertical">
                <span>{t('empty.noOverlaps', 'No overlaps found')}</span>
                <span style={{ fontSize: 12, color: '#999' }}>
                  {t('empty.tryAdjustFilters', 'Try adjusting your filters')}
                </span>
              </Space>
            }
          >
            <Button onClick={handleResetFilters} icon={<ReloadOutlined />}>
              {tCommon('action.resetFilters', 'Reset Filters')}
            </Button>
          </Empty>
        )}

        {/* Error state - show message with suggestion to adjust filters */}
        {dataError && !hasData && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space orientation="vertical">
                <span>{t('error.noDataDueToError', 'Unable to load data')}</span>
                <span style={{ fontSize: 12, color: '#999' }}>
                  {t('error.adjustFiltersAbove', 'Adjust filters above and retry')}
                </span>
              </Space>
            }
          />
        )}
      </Card>

      {/* Context Info */}
      {(lncrnaGeneId || targetGeneId) && (
        <Alert
          type="info"
          message={t('info.filteredView', 'Filtered View')}
          description={
            <Space orientation="vertical" size={0}>
              {lncrnaGeneId && (
                <span>
                  {t('info.filteredByLncRNA', 'Filtered by lncRNA')}:{' '}
                  <strong>Gene ID {lncrnaGeneId}</strong>
                </span>
              )}
              {targetGeneId && (
                <span>
                  {t('info.filteredByTarget', 'Filtered by target gene')}:{' '}
                  <strong>Gene ID {targetGeneId}</strong>
                </span>
              )}
            </Space>
          }
          showIcon
        />
      )}
    </Space>
      </div>

      {/* Bottom Section: IGV Genome Browser (when enabled and shown) */}
      {enableIGV && showIGV && (
        <div style={{ flex: '1 1 60%', padding: '16px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Card
            title={
              <Space>
                <HeatMapOutlined />
                {t('igv.title', 'Genome Browser')}
                <span style={{ fontWeight: 'normal', color: '#999', fontSize: 13 }}>
                  ({t('igv.clickHint', 'Click table row to navigate')})
                </span>
                {currentLocus && (
                  <Text type="secondary" style={{ marginLeft: 8 }}>
                    @ {currentLocus}
                  </Text>
                )}
              </Space>
            }
            extra={
              <Space>
                {/* Export Button */}
                <Dropdown menu={{ items: igvExportMenuItems }} disabled={isExporting}>
                  <Button icon={<DownloadOutlined />} loading={isExporting} size="small">
                    {tGenomeBrowser('export')}
                  </Button>
                </Dropdown>
              </Space>
            }
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', padding: '8px', overflow: 'auto' } }}
          >
            {/* Gene Search Toolbar */}
            <GenomeBrowserToolbar
              speciesId={igvSpeciesId}
              onSpeciesChange={handleIgvSpeciesChange}
              onSearch={handleToolbarSearch}
              disabled={false}
            />

            {/* Track Controls Panel */}
            <Collapse
              size="small"
              style={{ marginBottom: 12 }}
              items={[
                {
                  key: 'trackControls',
                  label: (
                    <Space>
                      <SettingOutlined />
                      <span>{tGenomeBrowser('trackControls')}</span>
                      {(selectedChIPSeqMarks.length > 0 || Object.values(enabledRepeatClasses).some(v => v)) && (
                        <Tag color="blue">
                          {selectedChIPSeqMarks.length + Object.values(enabledRepeatClasses).filter(v => v).length}
                        </Tag>
                      )}
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
                                <span style={{ fontWeight: 500 }}>{tGenomeBrowser('chipseq.title')}</span>
                                {selectedChIPSeqMarks.length > 0 && (
                                  <Tag color="blue">{selectedChIPSeqMarks.length}</Tag>
                                )}
                              </Space>
                            ),
                            children: (
                              <Space orientation="vertical" style={{ width: '100%' }}>
                                <Space align="center">
                                  <Switch
                                    checked={showChIPSeq}
                                    onChange={handleChIPSeqToggle}
                                    size="small"
                                  />
                                  <span>{tGenomeBrowser('chipseq.enableTracks')}</span>
                                </Space>

                                {showChIPSeq && (
                                  <>
                                    {isLoadingChIPSeqMarks ? (
                                      <Space>
                                        <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
                                        <span>{tGenomeBrowser('chipseq.loadingMarks')}</span>
                                      </Space>
                                    ) : chipseqMarksError ? (
                                      <Alert type="error" message={tGenomeBrowser('chipseq.loadMarksFailed')} />
                                    ) : (
                                      <>
                                        <Text type="secondary" style={{ fontSize: 12 }}>
                                          {tGenomeBrowser('chipseq.selectMarksHint')}
                                        </Text>
                                        <Select
                                          mode="multiple"
                                          placeholder={tGenomeBrowser('chipseq.selectPlaceholder')}
                                          style={{ width: '100%' }}
                                          listHeight={400}
                                          value={selectedChIPSeqMarks}
                                          onChange={handleChIPSeqMarksChange}
                                          options={(() => {
                                            const availableMarkTypes = new Set(
                                              availableChIPSeqMarks?.map(m => m.mark_name) || []
                                            )
                                            const allGroups = getMarksGroupedByCategory()
                                            return allGroups
                                              .map(group => {
                                                const filteredMarks = group.marks.filter(mark =>
                                                  availableMarkTypes.has(mark.value)
                                                )
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
                                          })()}
                                          maxTagCount={3}
                                          allowClear
                                        />
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

                      {/* RepeatMasker Tracks */}
                      <Collapse
                        size="small"
                        items={[
                          {
                            key: 'repeatMasker',
                            label: <span style={{ fontWeight: 500 }}>{tGenomeBrowser('repeatClasses.title')}</span>,
                            children: (
                              <Space orientation="vertical" style={{ width: '100%' }}>
                                <Space>
                                  <Button size="small" onClick={handleSelectAllRepeats}>
                                    {tGenomeBrowser('repeatClasses.selectAll')}
                                  </Button>
                                  <Button size="small" onClick={handleDeselectAllRepeats}>
                                    {tGenomeBrowser('repeatClasses.deselectAll')}
                                  </Button>
                                </Space>

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
                                    <span>{tGenomeBrowser(`repeatClasses.${repeatClass}`)}</span>
                                  </Space>
                                ))}
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

            {/* Genome Browser Component */}
            <div ref={browserContainerRef} style={{ position: 'relative', flex: 1, minHeight: 600 }}>
              <GenomeBrowser
                key={`species-${igvSpeciesId}`}
                speciesId={igvSpeciesId}
                onLocusChange={handleLocusChange}
                onBrowserReady={handleBrowserReady}
                height="100%"
                showChIPSeq={showChIPSeq}
                chipseqMarks={selectedChIPSeqMarks}
              />
              {/* RepeatMasker Legend */}
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
      )}
    </div>
  )
}

export default LncRNAChIPSeqOverlapTable
