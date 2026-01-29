import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Genes from './index'

const mocks = vi.hoisted(() => ({
  useGenes: vi.fn(),
  usePrefetchGenes: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useGenes', () => ({
  useGenes: mocks.useGenes,
  usePrefetchGenes: mocks.usePrefetchGenes,
}))

describe('Genes page', () => {
  beforeEach(() => {
    mocks.useGenes.mockReturnValue({
      data: {
        items: [
          {
            gene_id: 1,
            core_id: 'CORE001',
            gene_name: 'MALAT1',
            gene_ensembl_id: 'ENSG00000001',
            gene_type: 'lncRNA',
            species_id: 1,
            species_name: 'Human',
            chromosome: 'chr1',
            gene_start: 100,
            gene_end: 200,
            regulation_count: 0,
          },
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
    })
    mocks.usePrefetchGenes.mockReturnValue(vi.fn())
  })

  afterEach(() => {
    mocks.useGenes.mockReset()
    mocks.usePrefetchGenes.mockReset()
    window.history.replaceState({}, '', '/')
  })

  it('renders stable page and table anchors', () => {
    renderWithProviders(<Genes />)

    expect(screen.getByTestId('genes-page')).toBeInTheDocument()
    expect(screen.getByTestId('genes-table')).toBeInTheDocument()
  })

  it('initializes filters from URL params', () => {
    window.history.pushState(
      {},
      '',
      '/genes?species_id=2&page=3&page_size=50&gene_type=lncRNA&has_regulation=true&min_regulation_count=5&chromosome=chr1&search=MALAT1'
    )

    renderWithProviders(<Genes />)

    expect(mocks.useGenes).toHaveBeenCalled()
    const [params, options] = mocks.useGenes.mock.calls[0]
    expect(options).toMatchObject({ enabled: true })
    expect(params).toMatchObject({
      page: 3,
      page_size: 50,
      search: 'MALAT1',
      gene_type: 'lncRNA',
      species_id: 2,
      chromosome: 'chr1',
      has_regulation: true,
      min_regulation_count: 5,
    })
  })
})
