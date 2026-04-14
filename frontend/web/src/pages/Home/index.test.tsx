import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Home from './index'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  rootStatus: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  }
})

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
        'hero.currentStatusLink': 'Live platform status',
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
        'cards.statistics.title': 'Live Platform Status',
        'cards.compare.title': 'ChIP-seq Compare',
      }
      return translations[key] ?? key
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useRootStatus', () => ({
  useRootStatus: mocks.rootStatus,
}))

describe('Home page', () => {
  beforeEach(() => {
    mocks.rootStatus.mockReturnValue({
      data: {
        version: '0.1.0',
        db_mode: 'production',
        db_name: 'lncrna_production',
      },
      isLoading: false,
      error: null,
    })
  })

  afterEach(() => {
    mocks.navigate.mockReset()
    mocks.rootStatus.mockReset()
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
    expect(screen.getByText('Live Platform Status')).toBeInTheDocument()
    expect(screen.getByText('ChIP-seq Compare')).toBeInTheDocument()
  })

  it('routes hero actions to snapshot and live status pages', () => {
    renderWithProviders(<Home />)

    fireEvent.click(screen.getByRole('button', { name: 'Submission snapshot' }))
    fireEvent.click(screen.getByRole('button', { name: 'Live platform status' }))

    expect(mocks.navigate).toHaveBeenNthCalledWith(1, '/snapshot')
    expect(mocks.navigate).toHaveBeenNthCalledWith(2, '/stats')
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
