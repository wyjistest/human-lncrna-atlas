/**
 * GenomeBrowser Component
 * Integrates IGV.js for genomic data visualization
 *
 * @see https://github.com/igvteam/igv.js
 *
 * IGV.js is an imperative library, so we use useRef + useEffect pattern
 * similar to Cytoscape.js integration in the Network page.
 */
import { useRef, useEffect, useState, useCallback, memo } from 'react'
import { message, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { genomeApi, type IGVConfig } from '@/api/genome'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import type { IGVBrowser, IGVBrowserOptions, IGVTrackConfig } from 'igv'

// Dynamic import for IGV.js (large bundle, lazy load)
// IGV.js exports a default object with createBrowser, removeBrowser, etc.
interface IGVModule {
  createBrowser: (container: HTMLElement, options: IGVBrowserOptions) => Promise<IGVBrowser>
  removeBrowser: (browser: IGVBrowser) => void
}

let igvModule: IGVModule | null = null

const loadIGV = async (): Promise<IGVModule> => {
  if (!igvModule) {
    // IGV.js uses default export in ESM
    const module = await import('igv')
    // Handle both default export and named exports
    igvModule = (module.default || module) as IGVModule
  }
  return igvModule
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
  height?: number | string
}

const GenomeBrowser = memo(({
  speciesId = 1,
  geneName,
  padding = 50000,
  locus,
  onLocusChange,
  height = 500
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
    queryFn: async () => {
      // If geneName is provided, use gene-specific API
      if (geneName) {
        const res = await genomeApi.getIGVConfigForGene(geneName, padding)
        return res.data.data
      }
      // Otherwise use species-wide API
      const res = await genomeApi.getIGVConfig(speciesId)
      // API returns {success: true, data: IGVConfig}, extract the inner data
      return res.data.data
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 2,
  })

  // Load IGV.js module
  useEffect(() => {
    loadIGV()
      .then(() => setIsIGVLoaded(true))
      .catch((err) => {
        console.error('Failed to load IGV.js:', err)
        setIgvError(err)
      })
  }, [])

  // Store onLocusChange in ref to avoid dependency issues
  const onLocusChangeRef = useRef(onLocusChange)
  useEffect(() => {
    onLocusChangeRef.current = onLocusChange
  }, [onLocusChange])

  // Store initial locus in ref (only used during initialization)
  const initialLocusRef = useRef(locus)

  // Store t function in ref
  const tRef = useRef(t)
  useEffect(() => {
    tRef.current = t
  }, [t])

  // Initialize or reinitialize IGV browser when config changes
  useEffect(() => {
    if (!isIGVLoaded || !config || !containerRef.current) return

    const initBrowser = async () => {
      try {
        const igv = await loadIGV()

        // Clean up existing browser instance
        if (browserRef.current) {
          try {
            igv.removeBrowser(browserRef.current)
          } catch (e) {
            console.warn('Error removing previous IGV browser:', e)
          }
          browserRef.current = null
        }

        // Clear container safely by removing all child nodes
        if (containerRef.current) {
          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild)
          }
        }

        // Build browser options from backend config
        // Support two modes:
        // 1. genome: use built-in genome ID (e.g., "hg19")
        // 2. reference: use custom genome configuration
        const options: IGVBrowserOptions = {
          locus: initialLocusRef.current || config.locus,
          tracks: config.tracks as IGVTrackConfig[],
          showNavigation: true,
          showRuler: true,
          showCenterGuide: true,
          showCursorTrackingGuide: true,
          showControls: true,
        }

        // Use genome ID for built-in genomes, otherwise use reference
        if (config.genome) {
          // @ts-expect-error - IGV.js accepts genome string
          options.genome = config.genome
        } else if (config.reference) {
          options.reference = config.reference
        }

        // Process track URLs: convert relative paths to absolute backend URLs
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
        if (options.tracks) {
          options.tracks = options.tracks.map(track => ({
            ...track,
            // Convert relative paths to absolute URLs pointing to backend
            url: track.url?.startsWith('/')
              ? `${API_BASE_URL}${track.url}`
              : track.url,
            indexURL: track.indexURL?.startsWith('/')
              ? `${API_BASE_URL}${track.indexURL}`
              : track.indexURL,
          }))
        }

        // Create new browser instance
        const browser = await igv.createBrowser(containerRef.current!, options)
        browserRef.current = browser

        // Listen for locus changes
        browser.on('locuschange', () => {
          const currentLoci = browser.currentLoci()
          if (currentLoci && currentLoci.length > 0 && onLocusChangeRef.current) {
            onLocusChangeRef.current(currentLoci[0])
          }
        })

        setIgvError(null)
      } catch (err) {
        console.error('Failed to initialize IGV browser:', err)
        setIgvError(err as Error)
        message.error(tRef.current('initError'))
      }
    }

    initBrowser()

    // Cleanup on unmount or config change
    return () => {
      if (browserRef.current && igvModule) {
        try {
          igvModule.removeBrowser(browserRef.current)
        } catch (e) {
          console.warn('Error cleaning up IGV browser:', e)
        }
        browserRef.current = null
      }
    }
  }, [isIGVLoaded, config, speciesId, geneName, padding])

  // Handle external locus changes (navigation)
  useEffect(() => {
    if (browserRef.current && locus) {
      browserRef.current.search(locus).catch((err) => {
        console.warn('IGV search failed:', err)
      })
    }
  }, [locus])

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
        height,
        width: '100%',
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        overflow: 'hidden',
        backgroundColor: '#fff'
      }}
    />
  )
})

GenomeBrowser.displayName = 'GenomeBrowser'

export default GenomeBrowser
export { GenomeBrowser }
export type { GenomeBrowserProps }
