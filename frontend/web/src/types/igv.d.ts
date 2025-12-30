/**
 * IGV.js TypeScript type declarations
 * @see https://github.com/igvteam/igv.js
 */
declare module 'igv' {
  /**
   * Search configuration for IGV browser
   * Enables gene name searching in the native IGV search box
   * @see https://github.com/igvteam/igv.js/wiki/Browser-Configuration-Options#search
   */
  export interface IGVSearchConfig {
    /** URL for search requests. Use $FEATURE$ as placeholder for the search term */
    url: string
    /** Field name in response containing the chromosome (default: 'chromosome') */
    chromosomeField?: string
    /** Field name in response containing the start position (default: 'start') */
    startField?: string
    /** Field name in response containing the end position (default: 'end') */
    endField?: string
    /** Function to format search results (optional) */
    resultsField?: string
    /** Coordinate system: 0 or 1 (default: 0) */
    coords?: 0 | 1
  }

  /**
   * Genome list entry used by IGV.js when `genome` is specified.
   * This allows disabling IGV's default remote genome list fetch (https://igv.org/genomes/*).
   *
   * @see https://github.com/igvteam/igv.js/wiki/Browser-Configuration-Options#genomelist
   */
  export interface IGVGenomeListEntry {
    id: string
    name?: string
    fastaURL?: string
    indexURL?: string
    twoBitURL?: string
    cytobandURL?: string
    chromSizesURL?: string
    aliasURL?: string
  }

  export interface IGVBrowserOptions {
    genome?: string
    /**
     * Control whether IGV loads the default genome list from igv.org.
     * Set to false in offline/E2E environments and provide `genomeList` instead.
     */
    loadDefaultGenomes?: boolean
    /**
     * Custom genome list (URL or inlined array).
     * When provided as an array, no network request is needed.
     */
    genomeList?: string | IGVGenomeListEntry[]
    reference?: {
      id: string
      name?: string
      fastaURL?: string       // Optional now - not required if twoBitURL is provided
      indexURL?: string
      cytobandURL?: string
      twoBitURL?: string      // New: 2bit format URL (preferred for remote genomes)
      chromSizesURL?: string  // Optional: chromosome sizes file URL
    }
    locus?: string
    tracks?: IGVTrackConfig[]
    showNavigation?: boolean
    showRuler?: boolean
    showCenterGuide?: boolean
    showCursorTrackingGuide?: boolean
    showControls?: boolean
    /**
     * Search configuration for gene/feature lookup
     * Enables searching by gene name in addition to coordinates
     */
    search?: IGVSearchConfig
  }

  export interface IGVTrackConfig {
    /** Track type - determines how features are rendered */
    type: 'annotation' | 'wig' | 'alignment' | 'variant' | 'seg' | 'interact' | 'interaction' | 'bed' | 'gene' | string
    /** Display name for the track */
    name: string
    /** URL to the track data file */
    url?: string
    /** URL to index file (e.g., .tbi for tabix, .bai for BAM) */
    indexURL?: string
    /**
     * Source type for the track data.
     * - 'file': (default) Load from a static file
     * - 'service': Load from a web service with URL templates ($CHR$, $START$, $END$)
     *
     * When sourceType is 'service', the URL can contain template variables:
     * - $CHR$ - chromosome name (e.g., "chr1")
     * - $START$ - region start position
     * - $END$ - region end position
     * - $LOCUS$ - full locus string (e.g., "chr1:1000-2000")
     *
     * IGV.js will replace these variables with actual viewport coordinates,
     * enabling on-demand/region-based loading instead of loading all data at once.
     *
     * @see https://github.com/igvteam/igv.js/wiki/Tracks-2.0
     */
    sourceType?: 'file' | 'service'
    /**
     * File format. Common values:
     * - 'bed', 'gff3', 'gtf' for text annotation files
     * - 'bigbed' or 'bb' for bigBed binary format (indexed, no visibilityWindow needed)
     * - 'biggenepred' for bigGenePred format (gene structure with exons/introns)
     * - 'bigwig' or 'bw' for bigWig binary format
     * - 'bam', 'cram' for alignment files
     * - 'vcf' for variant files
     */
    format?: 'bed' | 'gff3' | 'gtf' | 'bigbed' | 'bb' | 'biggenepred' | 'bigwig' | 'bw' | 'bam' | 'cram' | 'vcf' | 'bedpe' | 'interact' | string
    /** How features are displayed vertically */
    displayMode?: 'EXPANDED' | 'COLLAPSED' | 'SQUISHED'
    /** Track color (CSS color string or RGB values like "0,82,41") */
    color?: string
    /** Alternative color for negative strand features (used with colorByStrand) */
    altColor?: string
    /** Track height in pixels */
    height?: number
    /**
     * Row height in EXPANDED display mode (pixels per feature row).
     * Useful for transcript tracks with exon/intron structure.
     */
    expandedRowHeight?: number
    /**
     * Row height in SQUISHED display mode (pixels per feature row).
     * Useful for dense annotation tracks.
     */
    squishedRowHeight?: number
    /**
     * Maximum window size (in bp) for which features are displayed.
     * Not needed for indexed formats like bigBed, bigWig, BAM, CRAM.
     */
    visibilityWindow?: number
    /** Track order (lower numbers appear first) */
    order?: number
    /** Whether the track can be removed by the user */
    removable?: boolean
    /** Whether features in this track are searchable */
    searchable?: boolean
    /** Description shown in track menu (can include HTML) */
    description?: string
    /** Field names to display on hover (for bigBed with extra fields) */
    hoverTextFields?: string[]
    /** Custom function to format hover text */
    hoverText?: (feature: Record<string, unknown>) => string
    /** Whether to use item RGB colors from the file (for bigBed 9+) */
    itemRgb?: boolean
    /**
     * Color features by strand. When set, uses 'color' for positive strand
     * and 'altColor' for negative strand.
     */
    colorByStrand?: string
    /**
     * Maximum height in pixels (format: "max:default:min").
     * Example: "64:32:16" means max 64px, default 32px, min 16px.
     */
    maxHeightPixels?: string
    /**
     * Whether the track height should auto-adjust based on content.
     * Defaults to false for fixed height tracks.
     */
    autoHeight?: boolean
    /**
     * Label fields to display for features (for bigBed/bigGenePred).
     * Can be a single field name or comma-separated list.
     */
    labelFields?: string
    /**
     * Default label field to display (for bigBed/bigGenePred).
     * Specifies which field to show as the primary label.
     */
    defaultLabelFields?: string
    /**
     * Field name to use for feature name (for custom formats).
     */
    nameField?: string
    /**
     * URL template for feature info links. Use $$ as placeholder for feature name.
     * Example: "https://www.ncbi.nlm.nih.gov/gene/?term=$$"
     */
    infoURL?: string

    // Interaction track specific options
    /** Arc type for interaction tracks: 'proportional' scales arc height by distance, 'nested' stacks arcs */
    arcType?: 'proportional' | 'nested'
    /** Arc orientation: 'UP' draws arcs above, 'DOWN' draws below, boolean for auto */
    arcOrientation?: 'UP' | 'DOWN' | boolean
    /** Alpha transparency for arcs (0-1 or string like "0.05") */
    alpha?: number | string
    /** Use logarithmic scale for arc heights */
    logScale?: boolean
    /** Show blocks at arc endpoints */
    showBlocks?: boolean
    /** Maximum value for scaling */
    max?: number
    /** Use score field for coloring/sizing */
    useScore?: boolean
  }

  export interface IGVBrowser {
    /**
     * Search by gene name or locus
     * @param locus - Genomic location or gene name to search for
     * @param init - Force view update/initialization (optional, default: false)
     */
    search(locus: string, init?: boolean): Promise<void>
    /** Navigate to a specific genomic locus (more reliable for coordinates) */
    goto(locus: string): Promise<void>
    loadTrack(config: IGVTrackConfig): Promise<void>
    removeTrackByName(name: string): void
    /** Remove a track by its track object */
    removeTrack(track: unknown): void
    /** Get all track views */
    trackViews: Array<{ track: { name: string; type: string } }>
    /** Find track by name */
    findTrackByName(name: string): { track: IGVTrackConfig } | undefined
    toSVG(): string
    dispose?(): void
    /**
     * Subscribe to browser events
     * Common events: 'locuschange', 'trackclick', 'trackremoved', 'trackorderchanged'
     */
    on(event: string, handler: (...args: unknown[]) => void): void
    off(event: string, handler?: (...args: unknown[]) => void): void
    currentLoci(): string[]
    zoomIn(): void
    zoomOut(): void
    /** Force update/repaint of all track views */
    updateViews?(): void
  }

  export function createBrowser(
    container: HTMLElement,
    options: IGVBrowserOptions
  ): Promise<IGVBrowser>

  export function removeBrowser(browser: IGVBrowser): void
}
