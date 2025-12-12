/**
 * Test Utilities for Human LncRNA Atlas
 *
 * Provides reusable test helpers, render functions, and mock factories
 * for consistent testing across the application.
 *
 * @module test/testUtils
 */
/* eslint-disable react-refresh/only-export-components */
import { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { vi } from 'vitest'

/**
 * Create a fresh QueryClient for testing
 *
 * Configures QueryClient with test-friendly defaults:
 * - Disabled retries (fail fast)
 * - Disabled garbage collection
 * - Disabled refetch on window focus
 *
 * @returns Configured QueryClient instance
 *
 * @example
 * const queryClient = createTestQueryClient()
 * render(
 *   <QueryClientProvider client={queryClient}>
 *     <MyComponent />
 *   </QueryClientProvider>
 * )
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

/**
 * All providers wrapper for testing
 *
 * Wraps children with QueryClientProvider and BrowserRouter
 * for components that need these contexts.
 */
interface AllProvidersProps {
  children: React.ReactNode
  queryClient?: QueryClient
}

function AllProviders({ children, queryClient }: AllProvidersProps) {
  const client = queryClient ?? createTestQueryClient()
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  )
}

/**
 * Custom render function with all providers
 *
 * Wraps the component with QueryClientProvider and BrowserRouter
 * for testing components that depend on these contexts.
 *
 * @param ui - React element to render
 * @param options - Additional render options
 * @returns Render result with custom utilities
 *
 * @example
 * // Basic usage
 * const { getByText } = renderWithProviders(<MyComponent />)
 *
 * @example
 * // With custom query client
 * const queryClient = createTestQueryClient()
 * const { getByText } = renderWithProviders(<MyComponent />, { queryClient })
 */
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient
}

export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {}
) {
  const { queryClient, ...renderOptions } = options
  const client = queryClient ?? createTestQueryClient()

  return {
    ...render(ui, {
      wrapper: ({ children }) => (
        <AllProviders queryClient={client}>{children}</AllProviders>
      ),
      ...renderOptions,
    }),
    queryClient: client,
  }
}

/**
 * Create mock i18n translation function
 *
 * Returns a mock translation function that returns the key or
 * a mapped translation. Useful for components using useTranslation.
 *
 * @param translations - Optional key-value translations map
 * @returns Mock useTranslation hook return value
 *
 * @example
 * vi.mock('react-i18next', () => ({
 *   useTranslation: () => createMockTranslation({
 *     'loading': 'Loading...',
 *     'error': 'Error occurred'
 *   })
 * }))
 */
export function createMockTranslation(translations: Record<string, string> = {}) {
  return {
    t: (key: string, fallback?: string) => translations[key] ?? fallback ?? key,
    i18n: {
      language: 'en',
      changeLanguage: vi.fn(),
    },
  }
}

/**
 * Mock i18n module for vitest
 *
 * Complete mock of react-i18next for testing components
 * that use translations.
 *
 * @param translations - Optional translations to use
 * @returns Mock module object
 *
 * @example
 * vi.mock('react-i18next', () => mockI18n({
 *   'common:loading': 'Loading...',
 *   'genes:title': 'Genes'
 * }))
 */
export function mockI18n(translations: Record<string, string> = {}) {
  return {
    useTranslation: (namespace?: string) => ({
      t: (key: string, fallback?: string) => {
        const fullKey = namespace ? `${namespace}:${key}` : key
        return translations[fullKey] ?? translations[key] ?? fallback ?? key
      },
      i18n: {
        language: 'en',
        changeLanguage: vi.fn().mockResolvedValue(undefined),
      },
    }),
    Trans: ({ children }: { children: React.ReactNode }) => children,
    initReactI18next: {
      type: '3rdParty',
      init: vi.fn(),
    },
  }
}

/**
 * Wait for async updates to complete
 *
 * Utility to wait for React Query updates or other async operations.
 *
 * @param ms - Milliseconds to wait (default: 0)
 *
 * @example
 * await act(async () => {
 *   fireEvent.click(button)
 *   await waitForAsync(100)
 * })
 */
export function waitForAsync(ms = 0): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Mock API response helper
 *
 * Creates a mock API response object for testing API hooks.
 *
 * @param data - Response data
 * @param options - Additional response options
 * @returns Mock axios response
 *
 * @example
 * const mockResponse = createMockApiResponse({ genes: [] })
 * vi.mocked(genesApi.list).mockResolvedValue(mockResponse)
 */
export function createMockApiResponse<T>(
  data: T,
  options: {
    status?: number
    statusText?: string
  } = {}
) {
  return {
    data,
    status: options.status ?? 200,
    statusText: options.statusText ?? 'OK',
    headers: {},
    config: {} as never,
  }
}

/**
 * Test fixtures for common data types
 */
export const fixtures = {
  /** Sample gene data */
  gene: {
    id: 1,
    gene_id: 1,
    core_id: 'CORE001',
    gene_name: 'HOTAIR',
    gene_ensembl_id: 'ENSG00000228630',
    gene_type: 'lncRNA' as const,
    species_id: 1,
    species_name: 'Human',
    chromosome: 'chr12',
    start_position: 53962308,
    end_position: 53974956,
    strand: '-',
  },

  /** Sample regulation data */
  regulation: {
    id: 1,
    lncrna_gene_id: 1,
    lncrna_gene_name: 'HOTAIR',
    target_gene_id: 2,
    target_gene_name: 'BRCA1',
    binding_affinity: 125.5,
    species_id: 1,
  },

  /** Sample disease data */
  disease: {
    trait_id: 1,
    trait_name: 'Type 2 Diabetes',
    trait_category: 'Metabolic',
  },

  /** Sample ChIP-seq peak data */
  chipseqPeak: {
    id: 1,
    mark_name: 'H3K27me3',
    chromosome: 'chr1',
    start_position: 1000000,
    end_position: 1001000,
    signal_value: 15.5,
    fold_enrichment: 8.2,
    q_value: 0.001,
  },
}

// Re-export everything from @testing-library/react
export * from '@testing-library/react'
export { default as userEvent } from '@testing-library/user-event'
