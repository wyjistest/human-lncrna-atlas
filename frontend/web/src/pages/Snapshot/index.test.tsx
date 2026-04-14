import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Snapshot from './index'

const mocks = vi.hoisted(() => ({
  rootStatus: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        title: 'Submission Snapshot',
        subtitle: 'Frozen paper-facing counts and provenance for the current companion release.',
        'sections.snapshot': 'Frozen paper-facing metrics',
        'sections.baseline': 'Main-text baseline',
        'sections.provenance': 'Snapshot provenance',
        'cards.species': 'Primate species',
        'cards.candidateEdges': 'Candidate edges',
        'cards.experiments': 'Epigenomic experiments',
        'cards.peaks': 'Paper-facing peaks',
        'baseline.title': 'Baseline guide',
        'baseline.description':
          'Main-text baseline remains 8 core histone marks + DNase-HS, while CTCF and H4K20me1 remain extended human tracks.',
        'status.apiVersion': 'API version',
        'status.dbMode': 'DB mode',
        'status.dbName': 'DB name',
        'status.unavailable': 'Unavailable',
      }
      return translations[key] ?? key
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useRootStatus', () => ({
  useRootStatus: mocks.rootStatus,
}))

describe('Snapshot page', () => {
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
    mocks.rootStatus.mockReset()
  })

  it('renders frozen metrics, baseline guidance and provenance', () => {
    renderWithProviders(<Snapshot />)

    expect(screen.getByText('Submission Snapshot')).toBeInTheDocument()
    expect(
      screen.getByText('Frozen paper-facing counts and provenance for the current companion release.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Frozen paper-facing metrics')).toHaveLength(2)
    expect(screen.getByText('Primate species')).toBeInTheDocument()
    expect(screen.getByText('Candidate edges')).toBeInTheDocument()
    expect(screen.getByText('Epigenomic experiments')).toBeInTheDocument()
    expect(screen.getByText('Paper-facing peaks')).toBeInTheDocument()
    expect(screen.getAllByText('Main-text baseline')).toHaveLength(2)
    expect(screen.getByText('Baseline guide')).toBeInTheDocument()
    expect(screen.getByText(/8 core histone marks \+ DNase-HS/i)).toBeInTheDocument()
    expect(screen.getByText('Snapshot provenance')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getByText('lncrna_production')).toBeInTheDocument()
  })
})
