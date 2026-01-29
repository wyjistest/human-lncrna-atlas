import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Diseases from './index'

const mocks = vi.hoisted(() => ({
  useDiseases: vi.fn(),
  useDiseaseGenes: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useDiseases', () => ({
  useDiseases: mocks.useDiseases,
  useDiseaseGenes: mocks.useDiseaseGenes,
}))

describe('Diseases page', () => {
  beforeEach(() => {
    mocks.useDiseases.mockReturnValue({
      data: {
        items: [
          {
            trait_id: 1,
            trait_name: 'Type 2 Diabetes',
            trait_doid: 'DOID:9352',
            ontology_id: 1,
            ontology_cl_id: 'CL:0000000',
            ontology_name: 'cell',
            species_name: 'Human',
            gene_count: 10,
            lncrna_count: 2,
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
        total_pages: 1,
      },
      isLoading: false,
      error: null,
    })
    mocks.useDiseaseGenes.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 1000, total_pages: 1 },
      isLoading: false,
      error: null,
    })
  })

  afterEach(() => {
    mocks.useDiseases.mockReset()
    mocks.useDiseaseGenes.mockReset()
    window.history.replaceState({}, '', '/')
  })

  it('renders stable page and table anchors', () => {
    renderWithProviders(<Diseases />)

    expect(screen.getByTestId('diseases-page')).toBeInTheDocument()
    expect(screen.getByTestId('diseases-table')).toBeInTheDocument()
  })

  it('initializes pagination and search from URL params', () => {
    window.history.pushState({}, '', '/diseases?page=2&page_size=50&search=diabetes')

    renderWithProviders(<Diseases />)

    expect(mocks.useDiseases).toHaveBeenCalled()
    const [params] = mocks.useDiseases.mock.calls[0]
    expect(params).toMatchObject({
      page: 2,
      page_size: 50,
      search: 'diabetes',
    })
  })
})
