import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Stats from './index'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/hooks/useStats', () => ({
  useStats: () => ({
    data: {
      total_genes: 1,
      total_lncrna: 1,
      total_regulations: 1,
      total_trait_associations: 1,
    },
    isLoading: false,
    error: null,
  }),
}))

vi.mock('@/hooks/useDetailedStats', () => ({
  useDetailedStats: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
}))

describe('Stats page', () => {
  it('renders stable page and report anchors', () => {
    renderWithProviders(<Stats />)

    expect(screen.getByTestId('stats-page')).toBeInTheDocument()
    expect(screen.getByTestId('stats-report')).toBeInTheDocument()
  })
})

