import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Regulations from './index'

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
  useRegulations: () => ({
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
  }),
  usePrefetchRegulations: () => vi.fn(),
}))

describe('Regulations page', () => {
  it('renders stable page and table anchors', () => {
    renderWithProviders(<Regulations />)

    expect(screen.getByTestId('regulations-page')).toBeInTheDocument()
    expect(screen.getByTestId('regulations-table')).toBeInTheDocument()
  })
})

