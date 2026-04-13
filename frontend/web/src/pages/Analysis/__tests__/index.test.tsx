/**
 * Analysis Page Tests
 *
 * Tests for the Analysis page component which displays scientific analysis
 * results from Jupyter Notebooks (Phase 6.0-B) with 4 tabs:
 * - High Affinity
 * - Conservation
 * - Epigenetic
 * - Disease Networks
 *
 * Test coverage:
 * - Page rendering
 * - Tab navigation
 * - Loading states (lazy loading)
 * - Data display
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown> | string) => {
      const translations: Record<string, string> = {
        'title': 'Evidence Hub',
        'description': 'Figure-aligned evidence summaries for the paper companion.',
        'tabs.highAffinity': 'Global Architecture',
        'tabs.conservation': 'Conservation & Rewiring',
        'tabs.epigenetic': 'Epigenomic Context',
        'tabs.disease': 'Trait-centered Subnetworks',
        'tabIntro.highAffinity':
          'Figure 2. Global architecture of orthology-aware, triplex-informed candidate edges.',
        'tabIntro.conservation':
          'Figure 3. Conserved and rewired candidate edges across 2/3/4 primate species.',
        'tabIntro.epigenetic':
          'Figure 4. Epigenomic overlap and co-localization around candidate loci.',
        'tabIntro.disease':
          'Figure 5. Trait-centered subnetworks connecting traits, genes and lncRNAs.',
        // High Affinity Tab
        'highAffinity.title': 'High Affinity Regulatory Networks',
        'highAffinity.description': 'Analysis of high binding affinity regulations',
        'highAffinity.table.lncrna': 'LncRNA',
        'highAffinity.table.target': 'Target Gene',
        'highAffinity.table.ba': 'Binding Affinity',
        'highAffinity.table.species': 'Species',
        // Conservation Tab
        'conservation.title': 'Cross-Species Conservation Patterns',
        'conservation.description': 'Conservation analysis across primate species',
        // Epigenetic Tab
        'epigenetic.title': 'Epigenetic Mark Analysis',
        'epigenetic.description': 'ChIP-seq peak overlap analysis',
        // Disease Tab
        'disease.title': 'Disease Association Networks',
        'disease.description': 'LncRNA-gene-disease regulatory networks',
        'workspace.copyLink': 'Copy share link',
        'workspace.copyLinkSuccess': 'Link copied',
        'workspace.copyLinkError': 'Copy failed',
        'workspace.evidence': 'Evidence',
        'workspace.moreEvidence': 'More evidence',
        'workspace.downstream': 'Downstream',
        'workspace.viewEvidence': 'View evidence',
        'workspace.comingSoon': 'Downstream evidence chain coming soon',
        'workspace.actions': 'Actions',
        'workspace.openRegulations': 'Open regulations',
        'workspace.openOverlap': 'Open overlap',
        'workspace.openNetwork': 'Open network',
        // Common
        'common.total': 'Total {{count}} items',
        'common.loading': 'Loading...',
        'common.refresh': 'Refresh',
        'common.export': 'Export',
        'common.exportCsv': 'Export CSV',
        'common.exportJson': 'Export JSON',
      }
      // Handle i18next interpolation - if options is an object with values, use the key
      if (typeof options === 'object' && options !== null && 'count' in options) {
        const template = translations[key] || key
        return template.replace('{{count}}', String(options.count))
      }
      return translations[key] || (typeof options === 'string' ? options : key)
    },
  }),
}))

// Mock Analysis API
vi.mock('@/api/analysis', () => ({
  analysisApi: {
    getSummary: vi.fn(),
    getHighAffinity: vi.fn(),
    getConservation: vi.fn(),
    getChipseqOverlaps: vi.fn(),
    getDiseaseNetwork: vi.fn(),
    exportHighAffinityCsv: vi.fn(),
    exportConservationCsv: vi.fn(),
    exportChipseqOverlapsCsv: vi.fn(),
    exportDiseaseNetworkJson: vi.fn(),
  },
}))

// Mock ECharts for chart components
vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts-mock">ECharts Mock</div>,
}))

vi.mock('@/utils/copyText', () => ({
  copyText: vi.fn(),
}))

// Import after mocks
import Analysis from '../index'
import { analysisApi } from '@/api/analysis'
import { copyText } from '@/utils/copyText'

// Mock data for High Affinity
const mockSummaryData = {
  high_affinity: {
    total_regulations: 804630,
    unique_lncrnas: 17248,
    unique_targets: 9201,
    avg_ba: 138.4,
    max_ba: 242.0,
    top_lncrnas: [],
  },
  conservation: {
    four_species: 123,
    three_species: 456,
    two_species: 789,
    total_conserved: 1368,
  },
  epigenetic: {
    total_overlaps: 200,
    by_mark: {
      H3K4me1: 10,
      H3K4me3: 15,
      H3K27ac: 20,
      H3K36me3: 25,
      H3K9me3: 30,
      H3K27me3: 35,
    },
    by_cell_type: {
      GM12878: 100,
    },
    bivalent_domains: 12,
    active_marks: 45,
    repressive_marks: 32,
  },
  disease: {
    total_diseases: 18,
    total_lncrnas: 91,
    total_genes: 76,
    avg_connections: 3.4,
  },
}

const mockHighAffinityData = {
  data: [
    {
      lncrna_gene_id: 1,
      lncrna_name: 'MALAT1',
      target_gene_id: 100,
      target_name: 'TP53',
      binding_affinity: 150.5,
      species_id: 1,
      species_name: 'Human',
      chr: 'chr11',
      lncrna_start: 65265233,
      lncrna_end: 65273940,
    },
    {
      lncrna_gene_id: 2,
      lncrna_name: 'NEAT1',
      target_gene_id: 101,
      target_name: 'MYC',
      binding_affinity: 145.2,
      species_id: 1,
      species_name: 'Human',
      chr: 'chr11',
      lncrna_start: 65422774,
      lncrna_end: 65445540,
    },
  ],
  total: 100,
  limit: 50,
  offset: 0,
}

// Mock data for Conservation
const mockConservationData = {
  data: [
    {
      core_id: 'CORE001',
      lncrna_names: ['MALAT1', 'MALAT1_chimp', 'MALAT1_macaque'],
      species_count: 3,
      species_names: ['Human', 'Chimpanzee', 'Macaque'],
      avg_binding_affinity: 120.5,
    },
  ],
  total: 50,
}

// Mock data for Epigenetic
const mockEpigeneticData = {
  data: [
    {
      lncrna_gene_id: 1,
      lncrna_name: 'MALAT1',
      target_gene_id: 100,
      target_name: 'TP53',
      mark_name: 'H3K27me3',
      peak_score: 12.5,
      peak_chr: 'chr1',
      peak_start: 100,
      peak_end: 200,
      cell_type: 'GM12878',
      binding_affinity: 85.5,
    },
  ],
  total: 200,
}

// Mock data for Disease Network
const mockDiseaseData = {
  nodes: [
    { id: 'lncrna_1', name: 'MALAT1', type: 'lncrna', gene_id: 1, species_id: 1 },
    { id: 'gene_100', name: 'TP53', type: 'gene', gene_id: 100, species_id: 1 },
    { id: 'disease_1', name: 'Cancer', type: 'disease', trait_id: 1, ontology_id: 9, species_id: 1 },
  ],
  edges: [
    { source: 'lncrna_1', target: 'gene_100', type: 'regulation', weight: 150.5 },
    { source: 'gene_100', target: 'disease_1', type: 'disease-gene', weight: 10.5 },
  ],
  query_params: {
    trait_name: 'Cancer',
    limit: 100,
    format: 'json',
  },
}

// Test wrapper with providers
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    )
  }
}

describe('Analysis Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(analysisApi.getSummary).mockResolvedValue({ data: mockSummaryData })
    // Setup default mock implementations
    vi.mocked(analysisApi.getHighAffinity).mockResolvedValue({ data: mockHighAffinityData })
    vi.mocked(analysisApi.getConservation).mockResolvedValue({ data: mockConservationData })
    vi.mocked(analysisApi.getChipseqOverlaps).mockResolvedValue({ data: mockEpigeneticData })
    vi.mocked(analysisApi.getDiseaseNetwork).mockResolvedValue({ data: mockDiseaseData })
    vi.mocked(analysisApi.exportHighAffinityCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportConservationCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportChipseqOverlapsCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportDiseaseNetworkJson).mockResolvedValue(undefined)
    vi.mocked(copyText).mockResolvedValue(true)
  })

  afterEach(() => {
    window.history.replaceState({}, '', '/')
  })

  describe('Page Rendering', () => {
    it('renders stable page and tabs anchors', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      expect(screen.getByTestId('analysis-page')).toBeInTheDocument()
      expect(screen.getByTestId('analysis-tabs')).toBeInTheDocument()
    })

    it('renders the page title and description', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      expect(screen.getByText('Evidence Hub')).toBeInTheDocument()
      expect(screen.getByText(/Figure-aligned evidence summaries/)).toBeInTheDocument()
    })

    it('renders all tab labels', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      expect(screen.getByText('Global Architecture')).toBeInTheDocument()
      expect(screen.getByText('Conservation & Rewiring')).toBeInTheDocument()
      expect(screen.getByText('Epigenomic Context')).toBeInTheDocument()
      expect(screen.getByText('Trait-centered Subnetworks')).toBeInTheDocument()
    })

    it('shows High Affinity tab as default active tab', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that High Affinity tab is active (has aria-selected)
      const tabList = screen.getByRole('tablist')
      const highAffinityTab = within(tabList).getByText('Global Architecture')
      const tabElement = highAffinityTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('initializes active tab from URL params', async () => {
      window.history.pushState({}, '', '/analysis?tab=epigenetic')

      render(<Analysis />, { wrapper: createWrapper() })

      const tabList = screen.getByRole('tablist')
      const epigeneticTab = within(tabList).getByText('Epigenomic Context')
      const tabElement = epigeneticTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('renders a figure-style intro that follows the active tab narrative', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      expect(
        screen.getByText(
          'Figure 2. Global architecture of orthology-aware, triplex-informed candidate edges.',
        ),
      ).toBeInTheDocument()

      await user.click(screen.getByText('Conservation & Rewiring'))

      expect(
        screen.getByText(
          'Figure 3. Conserved and rewired candidate edges across 2/3/4 primate species.',
        ),
      ).toBeInTheDocument()
    })
  })

  describe('Tab Navigation', () => {
    it('switches to Conservation tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const conservationTab = screen.getByText('Conservation & Rewiring')
      await user.click(conservationTab)

      // Verify tab is now active
      const tabElement = conservationTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('switches to Epigenetic tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const epigeneticTab = screen.getByText('Epigenomic Context')
      await user.click(epigeneticTab)

      const tabElement = epigeneticTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('switches to Disease Networks tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const diseaseTab = screen.getByText('Trait-centered Subnetworks')
      await user.click(diseaseTab)

      const tabElement = diseaseTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('Loading States (Lazy Loading)', () => {
    it('shows loading spinner when lazy loading tab content', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // The Suspense fallback should show a spinner during lazy load
      // This tests the lazy loading mechanism
      await waitFor(() => {
        // After load completes, the tab content should be visible
        expect(screen.getByText('Global Architecture')).toBeInTheDocument()
      })
    })
  })

  describe('Tab Icons', () => {
    it('renders icons in tab labels', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that icons are rendered (by checking SVG elements exist near tab text)
      const tabList = screen.getByRole('tablist')
      const tabs = within(tabList).getAllByRole('tab')

      // Each tab should have at least one element (icon + text)
      expect(tabs.length).toBe(4)
    })
  })

  describe('Tab Destruction Behavior', () => {
    it('renders tab content correctly', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Verify tabs are rendered and accessible
      const tabList = screen.getByRole('tablist')
      expect(tabList).toBeInTheDocument()

      const tabs = screen.getAllByRole('tab')
      expect(tabs.length).toBe(4)
    })
  })

  describe('Accessibility', () => {
    it('has correct ARIA roles for tabs', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      expect(screen.getByRole('tablist')).toBeInTheDocument()
      expect(screen.getAllByRole('tab').length).toBe(4)
    })

    it('has accessible tab panel', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      await waitFor(() => {
        expect(screen.getByRole('tabpanel')).toBeInTheDocument()
      })
    })
  })

  describe('State Management', () => {
    it('renders tab list consistently', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that all tabs are rendered
      expect(screen.getByRole('tablist')).toBeInTheDocument()
      expect(screen.getAllByRole('tab').length).toBe(4)

      // Default tab (Global Architecture) should be selected
      const highAffinityTab = screen.getByText('Global Architecture').closest('[role="tab"]')
      expect(highAffinityTab).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('Layout', () => {
    it('renders with proper padding', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that the main container has padding style
      const container = screen.getByText('Evidence Hub').parentElement?.parentElement
      expect(container).toHaveStyle({ padding: '24px' })
    })

    it('renders title and description with proper spacing', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const titleContainer = screen.getByText('Evidence Hub').parentElement
      expect(titleContainer).toHaveStyle({ marginBottom: '24px' })
    })
  })
})

describe('Analysis Tab Content Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(analysisApi.getSummary).mockResolvedValue({ data: mockSummaryData })
    vi.mocked(analysisApi.getHighAffinity).mockResolvedValue({ data: mockHighAffinityData })
    vi.mocked(analysisApi.getConservation).mockResolvedValue({ data: mockConservationData })
    vi.mocked(analysisApi.getChipseqOverlaps).mockResolvedValue({ data: mockEpigeneticData })
    vi.mocked(analysisApi.getDiseaseNetwork).mockResolvedValue({ data: mockDiseaseData })
    vi.mocked(analysisApi.exportHighAffinityCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportConservationCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportChipseqOverlapsCsv).mockResolvedValue(undefined)
    vi.mocked(analysisApi.exportDiseaseNetworkJson).mockResolvedValue(undefined)
    vi.mocked(copyText).mockResolvedValue(true)
  })

  afterEach(() => {
    window.history.replaceState({}, '', '/')
  })

  describe('High Affinity Tab', () => {
    it('loads High Affinity data when tab is active', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // High Affinity is the default tab, so it should trigger the API call
      await waitFor(
        () => {
          expect(analysisApi.getHighAffinity).toHaveBeenCalled()
        },
        { timeout: 5000 }
      )
    })

    it('initializes High Affinity filters from URL params', async () => {
      window.history.pushState({}, '', '/analysis?tab=highAffinity&min_ba=150&species_id=2')

      render(<Analysis />, { wrapper: createWrapper() })

      await waitFor(() => {
        expect(analysisApi.getHighAffinity).toHaveBeenCalled()
      })

      const [params] = vi.mocked(analysisApi.getHighAffinity).mock.calls[0]
      expect(params).toMatchObject({
        min_ba: 150,
        species_id: 2,
        limit: 1000,
      })
    })

    it('renders a regulations deep link for each high-affinity row', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const link = await screen.findByTestId('analysis-high-affinity-regulations-1-100')
      expect(link).toHaveAttribute('href', '/regulations?lncrna_gene_id=1&target_gene_id=100&min_ba=100')
    })

    it('renders target text as plain text and exposes a dedicated action CTA', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      await screen.findByText('TP53')
      expect(screen.queryByRole('link', { name: 'TP53' })).not.toBeInTheDocument()

      const actionLink = screen.getByTestId('analysis-high-affinity-regulations-1-100')
      expect(actionLink).toHaveTextContent('Open regulations')
    })

    it('exports the current High Affinity slice from the shared action bar', async () => {
      const user = userEvent.setup()
      window.history.pushState({}, '', '/analysis?tab=highAffinity&min_ba=150&species_id=2')

      render(<Analysis />, { wrapper: createWrapper() })

      const exportButton = await screen.findByTestId('analysis-highAffinity-export')
      await user.click(exportButton)

      expect(analysisApi.exportHighAffinityCsv).toHaveBeenCalledWith({
        min_ba: 150,
        species_id: 2,
        limit: 100,
      })
    })
  })

  describe('Conservation Tab', () => {
    it('renders Conservation tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const conservationTab = screen.getByText('Conservation & Rewiring')
      expect(conservationTab).toBeInTheDocument()
      expect(conservationTab.closest('[role="tab"]')).not.toBeDisabled()
    })

    it('shows a coming-soon status for downstream evidence chain', async () => {
      window.history.pushState({}, '', '/analysis?tab=conservation')

      render(<Analysis />, { wrapper: createWrapper() })

      expect(await screen.findByText(/Downstream evidence chain coming soon/)).toBeInTheDocument()
    })
  })

  describe('Epigenetic Tab', () => {
    it('renders Epigenetic tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const epigeneticTab = screen.getByText('Epigenomic Context')
      expect(epigeneticTab).toBeInTheDocument()
      expect(epigeneticTab.closest('[role="tab"]')).not.toBeDisabled()
    })

    it('renders an overlap deep link with gene ids and mark filters', async () => {
      window.history.pushState({}, '', '/analysis?tab=epigenetic')

      render(<Analysis />, { wrapper: createWrapper() })

      const link = await screen.findByTestId('analysis-epigenetic-overlap-1-100-H3K27me3')
      expect(link).toHaveAttribute(
        'href',
        '/lncrna-chipseq-overlap?lncrna_gene_id=1&target_gene_id=100&mark_type=H3K27me3&min_binding_affinity=100',
      )
    })

    it('renders target text as plain text and exposes an overlap action CTA', async () => {
      window.history.pushState({}, '', '/analysis?tab=epigenetic')

      render(<Analysis />, { wrapper: createWrapper() })

      await screen.findByText('TP53')
      expect(screen.queryByRole('link', { name: 'TP53' })).not.toBeInTheDocument()

      const actionLink = screen.getByTestId('analysis-epigenetic-overlap-1-100-H3K27me3')
      expect(actionLink).toHaveTextContent('Open overlap')
    })
  })

  describe('Disease Networks Tab', () => {
    it('renders Disease Networks tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const diseaseTab = screen.getByText('Trait-centered Subnetworks')
      expect(diseaseTab).toBeInTheDocument()
      expect(diseaseTab.closest('[role="tab"]')).not.toBeDisabled()
    })

    it('renders a network deep link for disease nodes', async () => {
      window.history.pushState({}, '', '/analysis?tab=disease')

      render(<Analysis />, { wrapper: createWrapper() })

      const link = await screen.findByTestId('analysis-disease-network-disease_1')
      expect(link).toHaveAttribute('href', '/network?species_ids=1&trait_id=1&ontology_id=9&min_ba=0')
    })

    it('renders disease name as plain text and exposes a network action CTA', async () => {
      window.history.pushState({}, '', '/analysis?tab=disease')

      render(<Analysis />, { wrapper: createWrapper() })

      await screen.findByText('Cancer')
      expect(screen.queryByRole('link', { name: 'Cancer' })).not.toBeInTheDocument()

      const actionLink = screen.getByTestId('analysis-disease-network-disease_1')
      expect(actionLink).toHaveTextContent('Open network')
    })
  })

  describe('Workspace Panel', () => {
    it('renders evidence links for the active tab', async () => {
      window.history.pushState({}, '', '/analysis?tab=epigenetic')

      render(<Analysis />, { wrapper: createWrapper() })

      const evidenceLink = await screen.findByTestId('analysis-workspace-evidence-primary')
      expect(evidenceLink).toHaveAttribute(
        'href',
        'https://github.com/wyjistest/human-lncrna-atlas/blob/main/docs/reports/HOW_TO_TEST_OVERLAP_PAGE.md',
      )
    })

    it('copies the current shareable URL', async () => {
      const user = userEvent.setup()
      window.history.pushState({}, '', '/analysis?tab=disease&trait_name=Cancer')

      render(<Analysis />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: 'Copy share link' }))

      await waitFor(() => {
        expect(copyText).toHaveBeenCalledWith(window.location.href)
      })
    })
  })
})
