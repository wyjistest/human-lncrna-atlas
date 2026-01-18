import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import CacheManagement from './index'

vi.mock('@/hooks/useAdminCacheStats', () => ({
  useAdminCacheStats: () => ({
    data: {
      backend: 'memory',
      enabled: true,
      hits: 1,
      misses: 0,
      total_requests: 1,
      hit_rate: '100.0%',
      hit_rate_pct: 100,
      namespaces: { tracked: 0, limit: 10, top: [] },
      keys: { tracked: 0, limit: 10, top: [] },
      memory: { size: 0, max_size: 1000, evictions: 0 },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isFetching: false,
  }),
}))

describe('Admin Cache page', () => {
  it('renders cache management actions and breakdown', () => {
    renderWithProviders(<CacheManagement />)

    expect(screen.getByText('Cache Management')).toBeInTheDocument()
    expect(screen.getAllByText('Invalidate Namespace').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Clear Cache').length).toBeGreaterThan(0)
    expect(screen.getByText('Cache Namespaces')).toBeInTheDocument()
    expect(screen.getByText('Cache Hot Keys')).toBeInTheDocument()
  })
})
