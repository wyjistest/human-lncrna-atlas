import { screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Home from './index'

const mocks = vi.hoisted(() => ({
  useStats: vi.fn(),
  apiGet: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        title: 'Human LncRNA Atlas Companion',
        subtitle:
          'Orthology-aware, triplex-informed candidate regulatory networks across primates',
        'hero.description':
          'Interactive evidence layer for trait-associated catalogs, candidate regulatory edges, conservation and epigenomic context.',
        'hero.paperFreeze': 'Paper-facing freeze',
        'hero.paperBaseline': '8 core histone marks + DNase-HS',
        'hero.snapshotLink': 'Submission snapshot',
        'hero.currentStatusLink': 'Current status',
        'stats.species': 'Primate species',
        'stats.candidateEdges': 'Candidate edges',
        'stats.experiments': 'Epigenomic experiments',
        'stats.peaks': 'Paper-facing peaks',
        'status.apiVersion': 'API version',
        'status.dbMode': 'DB mode',
        'status.dbName': 'DB name',
        'sections.startHere': 'Start here',
        'sections.advancedTools': 'Advanced tools',
        'cards.byGene.title': 'By gene',
        'cards.byTrait.title': 'By trait',
        'cards.conservation.title': 'Conservation & Rewiring',
        'cards.epigenomic.title': 'Epigenomic Context',
        'cards.edges.title': 'Candidate Regulatory Edges',
        'cards.genomeBrowser.title': 'Genome Browser',
        'cards.statistics.title': 'Statistics',
        'cards.compare.title': 'ChIP-seq Compare',
      }
      return translations[key] ?? key
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useStats', () => ({
  useStats: mocks.useStats,
}))

vi.mock('@/api/client', () => ({
  apiClient: {
    get: mocks.apiGet,
  },
}))

describe('Home page', () => {
  beforeEach(() => {
    mocks.useStats.mockReturnValue({
      data: {
        total_genes: 17248,
        total_lncrna: 5484,
        total_regulations: 804630,
        total_trait_associations: 67763,
      },
      isLoading: false,
      error: null,
    })
    mocks.apiGet.mockResolvedValue({
      data: {
        version: '0.1.0',
        db_mode: 'production',
        db_name: 'lncrna_production',
      },
    })
  })

  afterEach(() => {
    mocks.useStats.mockReset()
    mocks.apiGet.mockReset()
  })

  it('renders a paper-first hero with frozen snapshot KPIs and reviewer entrypoints', () => {
    renderWithProviders(<Home />)

    expect(screen.getByText('Human LncRNA Atlas Companion')).toBeInTheDocument()
    expect(
      screen.getByText('Orthology-aware, triplex-informed candidate regulatory networks across primates'),
    ).toBeInTheDocument()
    expect(screen.getByText('Paper-facing freeze')).toBeInTheDocument()
    expect(screen.getByText('8 core histone marks + DNase-HS')).toBeInTheDocument()

    expect(screen.getByText('Primate species')).toBeInTheDocument()
    expect(screen.getByText('Candidate edges')).toBeInTheDocument()
    expect(screen.getByText('Epigenomic experiments')).toBeInTheDocument()
    expect(screen.getByText('Paper-facing peaks')).toBeInTheDocument()

    expect(screen.getByText('Start here')).toBeInTheDocument()
    expect(screen.getByText('By gene')).toBeInTheDocument()
    expect(screen.getByText('By trait')).toBeInTheDocument()
    expect(screen.getByText('Conservation & Rewiring')).toBeInTheDocument()
    expect(screen.getByText('Epigenomic Context')).toBeInTheDocument()

    expect(screen.getByText('Advanced tools')).toBeInTheDocument()
    expect(screen.getByText('Candidate Regulatory Edges')).toBeInTheDocument()
    expect(screen.getByText('Genome Browser')).toBeInTheDocument()
    expect(screen.getByText('Statistics')).toBeInTheDocument()
    expect(screen.getByText('ChIP-seq Compare')).toBeInTheDocument()
  })

  it('shows live platform provenance from the root status endpoint', async () => {
    renderWithProviders(<Home />)

    await waitFor(() => {
      expect(screen.getByText('API version')).toBeInTheDocument()
    })

    expect(screen.getByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByText('DB mode')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getByText('DB name')).toBeInTheDocument()
    expect(screen.getByText('lncrna_production')).toBeInTheDocument()
  })
})
