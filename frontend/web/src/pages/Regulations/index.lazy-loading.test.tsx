import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'

describe('Regulations page visualization dependency isolation', () => {
  afterEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
  })

  it('renders the page before opening visualization even when cytoscape is unavailable', async () => {
    vi.doMock('react-i18next', () => ({
      useTranslation: () => ({
        t: (key: string) => key,
        i18n: { language: 'en', changeLanguage: vi.fn() },
      }),
    }))

    vi.doMock('./components/AdvancedFilters', () => ({
      AdvancedFilters: () => null,
    }))

    vi.doMock('./components/SelectionToolbar', () => ({
      SelectionToolbar: () => null,
    }))

    vi.doMock('@/hooks/useRegulations', () => ({
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

    vi.doMock('cytoscape', () => {
      throw new Error('cytoscape unavailable in test')
    })

    const { default: Regulations } = await import('./index')

    renderWithProviders(<Regulations />)

    expect(screen.getByTestId('regulations-page')).toBeInTheDocument()
    expect(screen.getByTestId('regulations-table')).toBeInTheDocument()
  })
})
