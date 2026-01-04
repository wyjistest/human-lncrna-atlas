/**
 * GenomeBrowser Component
 * Integrates IGV.js for genomic data visualization
 *
 * @see https://github.com/igvteam/igv.js
 *
 * IGV.js is an imperative library, so we use useRef + useEffect pattern
 * similar to Cytoscape.js integration in the Network page.
 */
import { useRef, useEffect, useState, useCallback, useMemo, memo } from 'react'
import { message, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { genomeApi, type IGVConfig } from '@/api/genome'
import { API_BASE_URL } from '@/config/api'
import { getMarkColor } from '@/config/markConfigs'
import type { MarkType } from '@/types/chipseq'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import type { IGVBrowser, IGVBrowserOptions, IGVTrackConfig } from 'igv'

// Dynamic import for IGV.js (large bundle, lazy load)
// IGV.js exports a default object with createBrowser, removeBrowser, etc.
interface IGVModule {
  createBrowser: (container: HTMLElement, options: IGVBrowserOptions) => Promise<IGVBrowser>
  removeBrowser: (browser: IGVBrowser) => void
}

type IGVBrowserWithUnsubscribe = IGVBrowser & {
  un?: (eventName: string, handlerFn: (...args: unknown[]) => void) => void
}

let igvModule: IGVModule | null = null

// 避免 IGV.js 初始化时访问 https://igv.org/genomes/genomes3.json（默认 2s 超时，E2E/离线环境易报错）。
// 仅覆盖项目实际使用的内置基因组（当前为 hg19），并禁用默认基因组列表加载。
const IGV_BUILTIN_GENOME_LIST: Record<
  string,
  {
    id: string
    name: string
    twoBitURL: string
    cytobandURL?: string
    chromSizesURL?: string
    aliasURL?: string
  }
> = {
  hg19: {
    id: 'hg19',
    name: 'Human (GRCh37/hg19)',
    // 使用 UCSC 2bit（支持 HTTP Range），避免本地维护超大 FASTA
    twoBitURL: 'https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.2bit',
    // 使用 UCSC 的压缩 cytoband（本地 hg19/cytoBandIdeo.txt 为 .txt，后端默认禁止该类型）
    cytobandURL: 'https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz',
    // chrom.sizes 本地可用且较小，优先走后端静态文件（更快、更稳定）
    chromSizesURL: `${API_BASE_URL}/genomes/hg19.chrom.sizes`,
    // 染色体别名表（IGV 官方数据仓库）
    aliasURL: 'https://raw.githubusercontent.com/igvteam/igv-data/refs/heads/main/data/hg19/hg19_alias.tab',
  },
}

const loadIGV = async (): Promise<IGVModule> => {
  if (!igvModule) {
    // IGV.js uses default export in ESM
    const module = await import('igv')
    // Handle both default export and named exports
    igvModule = (module.default || module) as IGVModule
  }
  return igvModule
}

/** Handle type for accessing GenomeBrowser methods */
export interface GenomeBrowserHandle {
  /** Get SVG representation of current view */
  toSVG: () => string | undefined
  /** Navigate to a specific locus */
  navigateToLocus: (locus: string) => Promise<void>
  /** Load a new track dynamically */
  loadTrack: (config: import('@/api/genome').IGVTrackConfig) => Promise<void>
  /** Remove a track by name */
  removeTrack: (name: string) => void
  /** Get list of current track names */
  getTrackNames: () => string[]
}

interface GenomeBrowserProps {
  /** Species ID (used when geneName is not provided) */
  speciesId?: number
  /** Gene name to load (e.g., CATG00000000011.1) - takes precedence over speciesId */
  geneName?: string
  /** Padding around gene in bp (default 50000) */
  padding?: number
  /** Locus to navigate to (for external navigation) */
  locus?: string
  onLocusChange?: (locus: string) => void
  /** Callback when browser is ready, provides handle for browser operations */
  onBrowserReady?: (handle: GenomeBrowserHandle) => void
  height?: number | string
  /** ChIP-seq marks to display as tracks (e.g., ['H3K27me3', 'H3K4me3']) */
  chipseqMarks?: string[]
  /** Whether to show ChIP-seq tracks */
  showChIPSeq?: boolean
}


const GenomeBrowser = memo(({
  speciesId = 1,
  geneName,
  padding = 50000,
  locus,
  onLocusChange,
  onBrowserReady,
  height = 500,
  chipseqMarks = [],
  showChIPSeq = false
}: GenomeBrowserProps) => {
  const { t } = useTranslation('genomeBrowser')
  const containerRef = useRef<HTMLDivElement>(null)
  const browserRef = useRef<IGVBrowser | null>(null)
  const [isIGVLoaded, setIsIGVLoaded] = useState(false)
  const [igvError, setIgvError] = useState<Error | null>(null)

  // Determine query key based on whether we're loading by gene or species
  const queryKey = geneName
    ? ['igv-config-gene', geneName, padding]
    : ['igv-config', speciesId]

  // Fetch IGV configuration from backend
  const {
    data: config,
    isLoading: configLoading,
    error: configError,
    refetch: refetchConfig
  } = useQuery<IGVConfig>({
    queryKey,
    queryFn: async ({ signal }) => {
      // If geneName is provided, use gene-specific API
      if (geneName) {
        const res = await genomeApi.getIGVConfigForGene(geneName, padding, signal)
        // API response format: { success: true, data: IGVConfig, message: string }
        // res.data is axios response data, res.data.data is the actual IGVConfig
        return res.data.data
      }
      // Otherwise use species-wide API
      const res = await genomeApi.getIGVConfig(speciesId, signal)
      return res.data.data
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 2,
  })

  // Load IGV.js module
  useEffect(() => {
    let cancelled = false

    loadIGV()
      .then(() => {
        if (cancelled) return
        setIsIGVLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load IGV.js:', err)
        setIgvError(err)
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Store onLocusChange in ref to avoid dependency issues
  const onLocusChangeRef = useRef(onLocusChange)
  useEffect(() => {
    onLocusChangeRef.current = onLocusChange
  }, [onLocusChange])

  // Track IGV event handler for explicit unsubscription
  const locusChangeHandlerRef = useRef<((...args: unknown[]) => void) | null>(null)

  // Store onBrowserReady in ref
  const onBrowserReadyRef = useRef(onBrowserReady)
  useEffect(() => {
    onBrowserReadyRef.current = onBrowserReady
  }, [onBrowserReady])

  // Store initial locus in ref (used during initialization and updated when locus prop changes)
  const initialLocusRef = useRef(locus)

  // Update initialLocusRef when locus prop changes (for navigation from Regulation page)
  useEffect(() => {
    if (locus) {
      initialLocusRef.current = locus
    }
  }, [locus])

  // Store t function in ref
  const tRef = useRef(t)
  useEffect(() => {
    tRef.current = t
  }, [t])

  // Initialize or reinitialize IGV browser when config changes
  useEffect(() => {
    if (!isIGVLoaded || !config || !containerRef.current) return

    let cancelled = false

    const initBrowser = async () => {
      try {
        const igv = await loadIGV()
        if (cancelled) return

        // Clean up existing browser instance
        if (browserRef.current) {
          try {
            const prevHandler = locusChangeHandlerRef.current
            if (prevHandler && typeof (browserRef.current as IGVBrowserWithUnsubscribe).un === 'function') {
              try {
                ;(browserRef.current as IGVBrowserWithUnsubscribe).un?.('locuschange', prevHandler)
              } catch (e) {
                console.warn('Error unsubscribing IGV locuschange handler:', e)
              }
            }
            locusChangeHandlerRef.current = null
            igv.removeBrowser(browserRef.current)
          } catch (e) {
            console.warn('Error removing previous IGV browser:', e)
          }
          browserRef.current = null
          // Clear loaded/pending ChIP-seq marks since the browser is being reinitialized
          loadedChipseqMarksRef.current.clear()
          pendingChipseqMarksRef.current.clear()
        }
        if (cancelled) return

        // Clear container safely by removing all child nodes
        if (containerRef.current) {
          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild)
          }
        }
        if (cancelled || !containerRef.current) return

        // Build browser options from backend config
        // Support two modes:
        // 1. genome: use built-in genome ID (e.g., "hg19")
        // 2. reference: use custom genome configuration

        // Helper to validate genomic locus format (e.g., "chr1:1000-2000")
        const isValidLocus = (l: string | undefined): boolean => {
          if (!l || l === 'all') return false
          // Check if it looks like a valid genomic coordinate: chr + optional coords
          return /^chr[\dXYMT]+/.test(l)
        }

        // Use config.locus as default, only override if a valid locus prop is provided
        const effectiveLocus = isValidLocus(initialLocusRef.current)
          ? initialLocusRef.current!
          : config.locus

        const options: IGVBrowserOptions = {
          locus: effectiveLocus,
          tracks: config.tracks as IGVTrackConfig[],
          showNavigation: true,
          showRuler: true,
          showCenterGuide: true,
          showCursorTrackingGuide: true,
          showControls: true,
          // Enable gene search in IGV's native search box
          // This allows users to search by gene name (e.g., CATG00000000034.1) or coordinates (e.g., chr10:71915113-71916198)
          search: {
            url: `${API_BASE_URL}/api/v1/igv/locus?q=$FEATURE$`,
            chromosomeField: 'chromosome',
            startField: 'start',
            endField: 'end',
          },
        }
        const toAbsoluteURL = (url: string | null | undefined): string | undefined => {
          if (!url) return undefined
          return url.startsWith('/') ? `${API_BASE_URL}${url}` : url
        }

        // Use genome ID for built-in genomes, otherwise use reference
        if (config.genome) {
          options.genome = config.genome

          // 如果是内置基因组（例如 hg19），显式提供 genomeList 并禁用默认列表加载，避免外网依赖与控制台错误。
          const builtin = IGV_BUILTIN_GENOME_LIST[String(config.genome)]
          if (builtin) {
            options.loadDefaultGenomes = false
            options.genomeList = [builtin]
          }
        } else if (config.reference) {
          // 在 reference 模式下也显式禁用默认基因组列表加载，避免 IGV.js 额外访问 igv.org。
          options.loadDefaultGenomes = false

          // Build reference object - prefer twoBitURL over fastaURL for remote genomes
          options.reference = {
            id: config.reference.id,
            name: config.reference.name,
          }

          // Use twoBitURL if available (preferred for remote genomes - more efficient)
          // IMPORTANT: Convert relative paths to absolute URLs pointing to backend
          if (config.reference.twoBitURL) {
            options.reference.twoBitURL = toAbsoluteURL(config.reference.twoBitURL)
          } else if (config.reference.fastaURL) {
            // Fall back to fastaURL if twoBitURL not available
            options.reference.fastaURL = toAbsoluteURL(config.reference.fastaURL)
            options.reference.indexURL = toAbsoluteURL(config.reference.indexURL)
          }

          // Add cytoband if available (for chromosome ideogram visualization)
          if (config.reference.cytobandURL) {
            options.reference.cytobandURL = toAbsoluteURL(config.reference.cytobandURL)
          }

          // Add chromosome sizes if available
          if (config.reference.chromSizesURL) {
            options.reference.chromSizesURL = toAbsoluteURL(config.reference.chromSizesURL)
          }

          // Add chromosome aliases if available (e.g., chrM/MT)
          if (config.reference.aliasURL) {
            options.reference.aliasURL = toAbsoluteURL(config.reference.aliasURL)
          }
        }
        // Process track URLs: convert relative paths to absolute backend URLs
        if (options.tracks) {
          options.tracks = options.tracks.map(track => ({
            ...track,
            url: toAbsoluteURL(track.url),
            indexURL: toAbsoluteURL(track.indexURL),
          }))
        }

        // Note: ChIP-seq tracks are dynamically managed in a separate useEffect
        // to avoid reinitializing the entire browser when marks change

        // Create new browser instance
        const browser = await igv.createBrowser(containerRef.current, options)
        if (cancelled) {
          try {
            igv.removeBrowser(browser)
          } catch (e) {
            console.warn('Error removing IGV browser after cancellation:', e)
          }
          return
        }
        browserRef.current = browser

        // For built-in genomes (like hg19), IGV.js may default to "all" view
        // Need to wait for genome to fully load before navigation works reliably
        // Helper function to navigate with retry
        const navigateToLocus = async (targetLocus: string, retries = 3): Promise<void> => {
          for (let i = 0; i < retries; i++) {
            // Component unmounted / browser replaced while waiting
            if (cancelled || browserRef.current !== browser) {
              return
            }
            try {
              await browser.search(targetLocus)
              const currentLoci = browser.currentLoci()

              // Check if navigation was successful (not showing "all")
              if (currentLoci && currentLoci[0] !== 'all') {
                return
              }

              // If still showing "all", wait and retry
              await new Promise(resolve => setTimeout(resolve, 500))
            } catch {
              if (cancelled || browserRef.current !== browser) {
                return
              }
              if (i < retries - 1) {
                await new Promise(resolve => setTimeout(resolve, 500))
              }
            }
          }
        }

        if (effectiveLocus && effectiveLocus !== 'all') {
          // Small delay to ensure genome is loaded for built-in genomes
          await new Promise(resolve => setTimeout(resolve, 100))
          if (cancelled || browserRef.current !== browser) {
            return
          }
          await navigateToLocus(effectiveLocus)
        }

        // Listen for locus changes
        // Filter out "all" which IGV.js uses for whole-genome view
        const handleLocusChange = () => {
          const currentLoci = browser.currentLoci()
          if (currentLoci && currentLoci.length > 0 && onLocusChangeRef.current) {
            const locus = currentLoci[0]
            // Don't propagate "all" - it's the whole-genome view, not a useful coordinate
            if (locus && locus !== 'all') {
              onLocusChangeRef.current(locus)
            }
          }
        }
        locusChangeHandlerRef.current = handleLocusChange
        browser.on('locuschange', handleLocusChange)

        // Notify parent that browser is ready with handle
        if (onBrowserReadyRef.current) {
          const handle: GenomeBrowserHandle = {
            toSVG: () => {
              try {
                return browserRef.current?.toSVG?.()
              } catch (e) {
                console.warn('Failed to generate SVG:', e)
                return undefined
              }
            },
            navigateToLocus: async (targetLocus: string) => {
              // Use browserRef.current which always points to the latest instance
              const currentBrowser = browserRef.current
              if (!currentBrowser) {
                console.warn('No browser instance available')
                return
              }

              try {
                // Use init=true to force view update
                await currentBrowser.search(targetLocus, true)
                // Force repaint
                window.dispatchEvent(new Event('resize'))
                if (typeof currentBrowser.updateViews === 'function') {
                  currentBrowser.updateViews()
                }
              } catch (err) {
                console.error('IGV navigation failed:', err)
                throw err
              }
            },
            loadTrack: async (trackConfig) => {
              if (browserRef.current) {
                // Convert relative URLs to absolute backend URLs
                const processedConfig = {
                  ...trackConfig,
                  url: toAbsoluteURL(trackConfig.url),
                  indexURL: toAbsoluteURL(trackConfig.indexURL),
                }
                await browserRef.current.loadTrack(processedConfig as IGVTrackConfig)
              }
            },
            removeTrack: (nameOrId: string) => {
              const browser = browserRef.current
              if (!browser) return

              // IGV.js tracks may define both `id` and `name`.
              // Some APIs in this repo use `id` as a stable identifier; support both for robustness.
              const trackToRemove = browser.trackViews?.find(
                (tv: { track?: { name?: string; id?: string } }) =>
                  tv.track?.name === nameOrId || tv.track?.id === nameOrId
              )
              if (trackToRemove?.track) {
                browser.removeTrack(trackToRemove.track)
                return
              }

              // Fallback to IGV.js helper (name-based)
              browser.removeTrackByName(nameOrId)
            },
            getTrackNames: () => {
              if (browserRef.current?.trackViews) {
                return browserRef.current.trackViews
                  .map(tv => tv.track?.name)
                  .filter((name): name is string => !!name)
              }
              return []
            }
          }
          onBrowserReadyRef.current(handle)
        }

        if (!cancelled) {
          setIgvError(null)
        }
      } catch (err) {
        if (cancelled) return
        console.error('Failed to initialize IGV browser:', err)
        setIgvError(err as Error)
        message.error(tRef.current('initError'))
      }
    }

    initBrowser()

    // Cleanup on unmount or config change
    return () => {
      cancelled = true
      if (browserRef.current && igvModule) {
        try {
          const handler = locusChangeHandlerRef.current
          if (handler && typeof (browserRef.current as IGVBrowserWithUnsubscribe).un === 'function') {
            try {
              ;(browserRef.current as IGVBrowserWithUnsubscribe).un?.('locuschange', handler)
            } catch (e) {
              console.warn('Error unsubscribing IGV locuschange handler during cleanup:', e)
            }
          }
          locusChangeHandlerRef.current = null
          igvModule.removeBrowser(browserRef.current)
        } catch (e) {
          console.warn('Error cleaning up IGV browser:', e)
        }
        browserRef.current = null
      }
    }
  }, [isIGVLoaded, config, speciesId, geneName, padding])

  // Track ChIP-seq marks that are currently loaded
  const loadedChipseqMarksRef = useRef<Set<string>>(new Set())
  // Track ChIP-seq marks that are currently loading (to prevent duplicate loads)
  const pendingChipseqMarksRef = useRef<Set<string>>(new Set())
  // Compute desired marks based on current props
  const desiredMarks = useMemo(
    () => (showChIPSeq ? chipseqMarks : []),
    [showChIPSeq, chipseqMarks]
  )

  // Use a ref to store latest desired marks for async callbacks (avoiding stale closures)
  // This ref is updated inside useEffect which is safe
  const desiredMarksSnapshotRef = useRef<Set<string>>(new Set())

  // Dynamically manage ChIP-seq tracks without reinitializing browser
  useEffect(() => {
    if (!browserRef.current) return

    const browser = browserRef.current
    const currentMarks = new Set(desiredMarks)
    // Update snapshot ref at the start of effect (safe pattern)
    desiredMarksSnapshotRef.current = currentMarks
    const loadedMarks = loadedChipseqMarksRef.current
    const pendingMarks = pendingChipseqMarksRef.current

    const removeTrackByName = (trackName: string) => {
      try {
        // IGV.js removeTrackByName API
        const trackToRemove = browser.trackViews?.find(
          (tv: { track?: { name?: string } }) => tv.track?.name === trackName
        )
        if (trackToRemove) {
          browser.removeTrack(trackToRemove.track)
        }
      } catch (e) {
        console.warn(`Failed to remove track ${trackName}:`, e)
      }
    }

    // Remove tracks that are no longer selected
    const marksToRemove = [...loadedMarks].filter(mark => !currentMarks.has(mark))
    marksToRemove.forEach(mark => {
      removeTrackByName(`ChIP-seq: ${mark}`)
      loadedMarks.delete(mark)
    })

    // Add tracks that are newly selected
    desiredMarks.forEach((mark, index) => {
      if (loadedMarks.has(mark) || pendingMarks.has(mark)) {
        return
      }

      pendingMarks.add(mark)

      // DNase-HS uses pre-built bigBed file for better performance
      // Other marks use dynamic BED API with region filtering
      let trackConfig: IGVTrackConfig

      if (mark === 'DNase-HS' && speciesId === 1) {
        // Use bigBed for DNase-HS (Human) - it handles region filtering automatically
        trackConfig = {
          name: `ChIP-seq: ${mark}`,
          type: 'annotation',
          format: 'bigbed',
          url: `${API_BASE_URL}/genomes/dnase_hs_peaks.bb`,
          displayMode: 'SQUISHED' as const,
          color: getMarkColor(mark as MarkType),
          height: 50,
          order: 1000 + index,
          removable: true,
          searchable: false,
        }
      } else {
        // Other marks use BED API
        trackConfig = {
          name: `ChIP-seq: ${mark}`,
          type: 'annotation',
          format: 'bed',
          url: `${API_BASE_URL}/api/v1/igv/tracks/chipseq/${speciesId}.bed?mark_type=${encodeURIComponent(mark)}`,
          displayMode: 'EXPANDED' as const,
          color: getMarkColor(mark as MarkType),
          height: 80,
          order: 1000 + index,
          removable: true,
          searchable: false,
          visibilityWindow: 5000000,
        }
      }

      browser.loadTrack(trackConfig)
        .then(() => {
          pendingMarks.delete(mark)

          // Browser instance changed/unmounted, ignore.
          if (browserRef.current !== browser) {
            return
          }

          // If user toggled off while loading, remove the loaded track to avoid orphan tracks.
          if (!desiredMarksSnapshotRef.current.has(mark)) {
            removeTrackByName(`ChIP-seq: ${mark}`)
            return
          }

          loadedMarks.add(mark)
        })
        .catch((e) => {
          pendingMarks.delete(mark)
          console.warn(`Failed to load track for ${mark}:`, e)
        })
    })
  }, [desiredMarks, speciesId])

  // Handle external locus changes (navigation)
  // Disabled to avoid conflicts with navigateToLocus
  // useEffect(() => {
  //   if (browserRef.current && locus) {
  //     console.log('useEffect[locus] triggered, navigating to:', locus)
  //     browserRef.current.search(locus, true).catch((err) => {
  //       console.warn('IGV search failed:', err)
  //     })
  //   }
  // }, [locus])

  // Public method to navigate to a locus
  const navigateToLocus = useCallback(async (targetLocus: string) => {
    if (browserRef.current) {
      try {
        await browserRef.current.search(targetLocus)
      } catch (err) {
        console.error('Navigation failed:', err)
        message.error(t('searchError'))
      }
    }
  }, [t])

  // Expose navigation method via ref callback pattern
  useEffect(() => {
    // Store navigateToLocus in a data attribute for parent access if needed
    if (containerRef.current) {
      (containerRef.current as HTMLDivElement & { __navigateToLocus?: typeof navigateToLocus }).__navigateToLocus = navigateToLocus
    }
  }, [navigateToLocus])

  // Loading state
  if (!isIGVLoaded || configLoading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid #d9d9d9',
          borderRadius: 8,
          backgroundColor: '#fafafa'
        }}
      >
        <LoadingState />
      </div>
    )
  }

  // Error state
  if (configError || igvError) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid #d9d9d9',
          borderRadius: 8,
          backgroundColor: '#fafafa',
          padding: 24
        }}
      >
        <ErrorState
          error={configError || igvError}
          onRetry={() => {
            setIgvError(null)
            refetchConfig()
          }}
        />
      </div>
    )
  }

  // No config state
  if (!config) {
    return (
      <Alert
        type="warning"
        message={t('noConfig')}
        description={t('noConfigDesc')}
        style={{ margin: 16 }}
      />
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        minHeight: height,
        width: '100%',
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        overflow: 'auto',  // Allow scrolling if content exceeds height
        backgroundColor: '#fff'
      }}
    />
  )
})

GenomeBrowser.displayName = 'GenomeBrowser'

export default GenomeBrowser
export { GenomeBrowser }
export type { GenomeBrowserProps }
