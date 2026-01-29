import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Stats from './index'

const mocks = vi.hoisted(() => ({
  useDetailedStats: vi.fn(),
}))

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
  useDetailedStats: mocks.useDetailedStats,
}))

describe('Stats page', () => {
  beforeEach(() => {
    mocks.useDetailedStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    })
  })

  afterEach(() => {
    mocks.useDetailedStats.mockReset()
    window.history.replaceState({}, '', '/')
  })

  it('renders stable page and report anchors', () => {
    renderWithProviders(<Stats />)

    expect(screen.getByTestId('stats-page')).toBeInTheDocument()
    expect(screen.getByTestId('stats-report')).toBeInTheDocument()
  })

  it('initializes detailed stats options from URL params', () => {
    window.history.pushState({}, '', '/stats?buckets=50&top_limit=20')

    renderWithProviders(<Stats />)

    expect(mocks.useDetailedStats).toHaveBeenCalled()
    expect(mocks.useDetailedStats).toHaveBeenCalledWith({
      buckets: 50,
      topLimit: 20,
    })
  })
})
