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

    expect(screen.getByTestId('admin-cache-page')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-refresh')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-reset-stats')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-invalidate-namespace')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-clear-cache')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-namespaces')).toBeInTheDocument()
    expect(screen.getByTestId('admin-cache-hot-keys')).toBeInTheDocument()
  })
})
