import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'

describe('Network page visualization dependency isolation', () => {
  afterEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
  })

  it('renders the page filters before loading cytoscape-dependent graphs', async () => {
    vi.doMock('react-i18next', () => ({
      useTranslation: () => ({
        t: (key: string) => key,
        i18n: { language: 'en', changeLanguage: vi.fn() },
      }),
    }))

    vi.doMock('@/api/network', () => ({
      networkApi: {
        getAvailableCombinations: vi.fn().mockResolvedValue({
          data: {
            combinations: [],
          },
        }),
        getDiseaseNetwork: vi.fn(),
      },
    }))

    vi.doMock('@/api/diseases', () => ({
      diseasesApi: {
        getOptions: vi.fn().mockResolvedValue({
          traits: [],
        }),
      },
    }))

    vi.doMock('cytoscape', () => {
      throw new Error('cytoscape unavailable in test')
    })

    vi.doMock('cytoscape-svg', () => {
      throw new Error('cytoscape-svg unavailable in test')
    })

    const { default: Network } = await import('./index')

    renderWithProviders(<Network />)

    expect(screen.getByTestId('network-species-select')).toBeInTheDocument()
    expect(screen.getByTestId('network-disease-select')).toBeInTheDocument()
    expect(screen.getByTestId('network-ontology-select')).toBeInTheDocument()
  })
})
