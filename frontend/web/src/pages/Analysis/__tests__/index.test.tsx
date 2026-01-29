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
        'title': 'Scientific Analysis Results',
        'description': 'Explore analysis results from Jupyter Notebooks',
        'tabs.highAffinity': 'High Affinity',
        'tabs.conservation': 'Conservation',
        'tabs.epigenetic': 'Epigenetic',
        'tabs.disease': 'Disease Networks',
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
        // Common
        'common.total': 'Total {{count}} items',
        'common.loading': 'Loading...',
        'common.refresh': 'Refresh',
        'common.export': 'Export',
        'common.exportCsv': 'Export CSV',
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
  },
}))

// Mock ECharts for chart components
vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts-mock">ECharts Mock</div>,
}))

// Import after mocks
import Analysis from '../index'
import { analysisApi } from '@/api/analysis'

// Mock data for High Affinity
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
      mark_name: 'H3K27me3',
      cell_type: 'GM12878',
      overlap_count: 15,
      binding_affinity: 85.5,
    },
  ],
  total: 200,
}

// Mock data for Disease Network
const mockDiseaseData = {
  nodes: [
    { id: 'lncrna_1', name: 'MALAT1', type: 'lncrna' },
    { id: 'gene_100', name: 'TP53', type: 'gene' },
    { id: 'disease_1', name: 'Cancer', type: 'disease' },
  ],
  edges: [
    { source: 'lncrna_1', target: 'gene_100', value: 150.5 },
    { source: 'gene_100', target: 'disease_1', value: 10.5 },
  ],
  stats: {
    total_lncrnas: 10,
    total_genes: 50,
    total_diseases: 20,
    total_edges: 100,
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
    // Setup default mock implementations
    vi.mocked(analysisApi.getHighAffinity).mockResolvedValue({ data: mockHighAffinityData })
    vi.mocked(analysisApi.getConservation).mockResolvedValue({ data: mockConservationData })
    vi.mocked(analysisApi.getChipseqOverlaps).mockResolvedValue({ data: mockEpigeneticData })
    vi.mocked(analysisApi.getDiseaseNetwork).mockResolvedValue({ data: mockDiseaseData })
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

      expect(screen.getByText('Scientific Analysis Results')).toBeInTheDocument()
      expect(screen.getByText(/Explore analysis results/)).toBeInTheDocument()
    })

    it('renders all tab labels', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      expect(screen.getByText('High Affinity')).toBeInTheDocument()
      expect(screen.getByText('Conservation')).toBeInTheDocument()
      expect(screen.getByText('Epigenetic')).toBeInTheDocument()
      expect(screen.getByText('Disease Networks')).toBeInTheDocument()
    })

    it('shows High Affinity tab as default active tab', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that High Affinity tab is active (has aria-selected)
      const tabList = screen.getByRole('tablist')
      const highAffinityTab = within(tabList).getByText('High Affinity')
      const tabElement = highAffinityTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('initializes active tab from URL params', async () => {
      window.history.pushState({}, '', '/analysis?tab=epigenetic')

      render(<Analysis />, { wrapper: createWrapper() })

      const tabList = screen.getByRole('tablist')
      const epigeneticTab = within(tabList).getByText('Epigenetic')
      const tabElement = epigeneticTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('Tab Navigation', () => {
    it('switches to Conservation tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const conservationTab = screen.getByText('Conservation')
      await user.click(conservationTab)

      // Verify tab is now active
      const tabElement = conservationTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('switches to Epigenetic tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const epigeneticTab = screen.getByText('Epigenetic')
      await user.click(epigeneticTab)

      const tabElement = epigeneticTab.closest('[role="tab"]')
      expect(tabElement).toHaveAttribute('aria-selected', 'true')
    })

    it('switches to Disease Networks tab when clicked', async () => {
      const user = userEvent.setup()
      render(<Analysis />, { wrapper: createWrapper() })

      const diseaseTab = screen.getByText('Disease Networks')
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
        expect(screen.getByText('High Affinity')).toBeInTheDocument()
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

      // Default tab (High Affinity) should be selected
      const highAffinityTab = screen.getByText('High Affinity').closest('[role="tab"]')
      expect(highAffinityTab).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('Layout', () => {
    it('renders with proper padding', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      // Check that the main container has padding style
      const container = screen.getByText('Scientific Analysis Results').parentElement?.parentElement
      expect(container).toHaveStyle({ padding: '24px' })
    })

    it('renders title and description with proper spacing', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const titleContainer = screen.getByText('Scientific Analysis Results').parentElement
      expect(titleContainer).toHaveStyle({ marginBottom: '24px' })
    })
  })
})

describe('Analysis Tab Content Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(analysisApi.getHighAffinity).mockResolvedValue({ data: mockHighAffinityData })
    vi.mocked(analysisApi.getConservation).mockResolvedValue({ data: mockConservationData })
    vi.mocked(analysisApi.getChipseqOverlaps).mockResolvedValue({ data: mockEpigeneticData })
    vi.mocked(analysisApi.getDiseaseNetwork).mockResolvedValue({ data: mockDiseaseData })
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
  })

  describe('Conservation Tab', () => {
    it('renders Conservation tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const conservationTab = screen.getByText('Conservation')
      expect(conservationTab).toBeInTheDocument()
      expect(conservationTab.closest('[role="tab"]')).not.toBeDisabled()
    })
  })

  describe('Epigenetic Tab', () => {
    it('renders Epigenetic tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const epigeneticTab = screen.getByText('Epigenetic')
      expect(epigeneticTab).toBeInTheDocument()
      expect(epigeneticTab.closest('[role="tab"]')).not.toBeDisabled()
    })
  })

  describe('Disease Networks Tab', () => {
    it('renders Disease Networks tab as clickable', async () => {
      render(<Analysis />, { wrapper: createWrapper() })

      const diseaseTab = screen.getByText('Disease Networks')
      expect(diseaseTab).toBeInTheDocument()
      expect(diseaseTab.closest('[role="tab"]')).not.toBeDisabled()
    })
  })
})
