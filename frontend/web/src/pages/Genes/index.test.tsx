import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Genes from './index'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useGenes', () => ({
  useGenes: () => ({
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
  }),
  usePrefetchGenes: () => vi.fn(),
}))

describe('Genes page', () => {
  it('renders stable page and table anchors', () => {
    renderWithProviders(<Genes />)

    expect(screen.getByTestId('genes-page')).toBeInTheDocument()
    expect(screen.getByTestId('genes-table')).toBeInTheDocument()
  })
})
