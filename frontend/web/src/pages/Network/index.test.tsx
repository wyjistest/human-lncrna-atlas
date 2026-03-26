import { screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import Network from './index'

const mocks = vi.hoisted(() => ({
  getAvailableCombinations: vi.fn(),
  getDiseaseNetwork: vi.fn(),
  getOptions: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === 'batchExport.buttonWithCount') return `Export ${options?.count ?? ''}`.trim()
      return key
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('cytoscape', () => ({
  default: { use: vi.fn() },
}))

vi.mock('cytoscape-svg', () => ({
  default: vi.fn(),
}))

vi.mock('@/api/network', () => ({
  networkApi: {
    getAvailableCombinations: mocks.getAvailableCombinations,
    getDiseaseNetwork: mocks.getDiseaseNetwork,
  },
}))

vi.mock('@/api/diseases', () => ({
  diseasesApi: {
    getOptions: mocks.getOptions,
  },
}))

vi.mock('./components/NetworkCard', () => ({
  NetworkCard: () => <div data-testid="network-card">Network Card</div>,
}))

vi.mock('./utils/batchExport.tsx', () => ({
  handleBatchExport: vi.fn(),
}))

describe('Network page', () => {
  beforeEach(() => {
    mocks.getAvailableCombinations.mockResolvedValue({
      data: {
        combinations: [
          { trait_id: 40, ontology_id: 46, ontology_name: 'cell', species_id: 1 },
          { trait_id: 40, ontology_id: 46, ontology_name: 'cell', species_id: 3 },
        ],
      },
    })
    mocks.getOptions.mockResolvedValue({
      traits: [{ trait_id: 40, trait_name: 'Diabetes' }],
    })
    mocks.getDiseaseNetwork.mockResolvedValue({
      data: {
        nodes: [],
        edges: [],
        stats: {},
      },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
  })

  it('initializes filters from URL params and auto-runs query when parameters are complete', async () => {
    window.history.pushState({}, '', '/network?species_ids=1,3&trait_id=40&ontology_id=46&min_ba=25')

    renderWithProviders(<Network />)

    await waitFor(() => {
      expect(mocks.getDiseaseNetwork).toHaveBeenCalledTimes(2)
    })

    expect(mocks.getDiseaseNetwork).toHaveBeenNthCalledWith(
      1,
      { species_id: 1, trait_id: 40, ontology_id: 46, min_ba: 25 },
      expect.anything(),
    )
    expect(mocks.getDiseaseNetwork).toHaveBeenNthCalledWith(
      2,
      { species_id: 3, trait_id: 40, ontology_id: 46, min_ba: 25 },
      expect.anything(),
    )

    expect(screen.getByTestId('network-species-select')).toBeInTheDocument()
    expect(screen.getByTestId('network-disease-select')).toBeInTheDocument()
    expect(screen.getByTestId('network-ontology-select')).toBeInTheDocument()
  })
})
