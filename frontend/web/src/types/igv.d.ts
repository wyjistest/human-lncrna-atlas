/**
 * IGV.js TypeScript type declarations
 * @see https://github.com/igvteam/igv.js
 */
declare module 'igv' {
  export interface IGVBrowserOptions {
    genome?: string
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
  }

  export interface IGVTrackConfig {
    /** Track type - determines how features are rendered */
    type: 'annotation' | 'wig' | 'alignment' | 'variant' | 'seg' | 'interact' | 'interaction' | 'bed'
    /** Display name for the track */
    name: string
    /** URL to the track data file */
    url: string
    /** URL to index file (e.g., .tbi for tabix, .bai for BAM) */
    indexURL?: string
    /**
     * File format. Common values:
     * - 'bed', 'gff3', 'gtf' for text annotation files
     * - 'bigbed' or 'bb' for bigBed binary format (indexed, no visibilityWindow needed)
     * - 'bigwig' or 'bw' for bigWig binary format
     * - 'bam', 'cram' for alignment files
     * - 'vcf' for variant files
     */
    format?: 'bed' | 'gff3' | 'gtf' | 'bigbed' | 'bb' | 'bigwig' | 'bw' | 'bam' | 'cram' | 'vcf' | 'bedpe' | 'interact' | string
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
    search(locus: string): Promise<void>
    loadTrack(config: IGVTrackConfig): Promise<void>
    removeTrackByName(name: string): void
    toSVG(): string
    dispose?(): void
    on(event: string, handler: (...args: unknown[]) => void): void
    off(event: string, handler?: (...args: unknown[]) => void): void
    currentLoci(): string[]
    zoomIn(): void
    zoomOut(): void
  }

  export function createBrowser(
    container: HTMLElement,
    options: IGVBrowserOptions
  ): Promise<IGVBrowser>

  export function removeBrowser(browser: IGVBrowser): void
}
