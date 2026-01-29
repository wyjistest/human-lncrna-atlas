import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Regulations from './index'

const mocks = vi.hoisted(() => ({
  useRegulations: vi.fn(),
  usePrefetchRegulations: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('./components/AdvancedFilters', () => ({
  AdvancedFilters: () => null,
}))

vi.mock('./components/SelectionToolbar', () => ({
  SelectionToolbar: () => null,
}))

vi.mock('./components/BatchVisualizationModal', () => ({
  BatchVisualizationModal: () => null,
}))

vi.mock('@/hooks/useRegulations', () => ({
  useRegulations: mocks.useRegulations,
  usePrefetchRegulations: mocks.usePrefetchRegulations,
}))

describe('Regulations page', () => {
  beforeEach(() => {
    mocks.useRegulations.mockReturnValue({
      data: {
        items: [
          {
            regulation_id: 1,
            lncrna_gene_id: 1,
            lncrna_gene_name: 'MALAT1',
            target_gene_id: 100,
            target_gene_name: 'TP53',
            species_id: 1,
            species_name: 'Human',
            target_chromosome: 'chr1',
            target_start: 100,
            target_end: 200,
            binding_affinity: 150,
            num_peaks: 1,
          },
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
    })
    mocks.usePrefetchRegulations.mockReturnValue(vi.fn())
  })

  afterEach(() => {
    mocks.useRegulations.mockReset()
    mocks.usePrefetchRegulations.mockReset()
    window.history.replaceState({}, '', '/')
  })

  it('renders stable page and table anchors', () => {
    renderWithProviders(<Regulations />)

    expect(screen.getByTestId('regulations-page')).toBeInTheDocument()
    expect(screen.getByTestId('regulations-table')).toBeInTheDocument()
  })

  it('initializes filters from URL params', () => {
    window.history.pushState(
      {},
      '',
      '/regulations?page=3&page_size=50&min_ba=100&max_ba=200&species_ids=1,2&chromosomes=chr1,chr2&lncrna_gene_name=MALAT1&target_gene_name=TP53'
    )

    renderWithProviders(<Regulations />)

    expect(mocks.useRegulations).toHaveBeenCalled()
    const [params] = mocks.useRegulations.mock.calls[0]
    expect(params).toMatchObject({
      page: 3,
      page_size: 50,
      min_ba: 100,
      max_ba: 200,
      species_ids: '1,2',
      chromosomes: 'chr1,chr2',
      lncrna_gene_name: 'MALAT1',
      target_gene_name: 'TP53',
    })
  })
})
