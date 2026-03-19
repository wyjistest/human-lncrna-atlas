import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import MaterializedViews from './index'

vi.mock('@/hooks/useMaterializedViewsStatus', () => ({
  useMaterializedViewsStatus: () => ({
    data: {
      status: 'success',
      supported: true,
      database_backend: 'postgresql',
      checked_at: '2026-03-19T04:00:00Z',
      refresh_lock_available: true,
      views: [
        {
          name: 'mv_lncrna_chipseq_overlaps',
          exists: true,
          populated: true,
          rows_estimate: 1,
          total_size: '16 kB',
          total_size_bytes: 16384,
          heap_size: '8 kB',
          heap_size_bytes: 8192,
          index_size: '8 kB',
          index_size_bytes: 8192,
          last_analyze_at: '2026-03-19T03:55:00Z',
          last_autoanalyze_at: '2026-03-19T03:57:00Z',
          last_stats_at: '2026-03-19T03:57:00Z',
          last_stats_source: 'autoanalyze',
          stats_age_seconds: 180,
          health_status: 'healthy',
          severity: 'info',
          recommended_action: null,
          affects_features: ['Overlap compare'],
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isFetching: false,
  }),
}))

describe('Admin Materialized Views page', () => {
  it('renders status and refresh controls', () => {
    renderWithProviders(<MaterializedViews />)

    expect(screen.getByTestId('admin-materialized-views-page')).toBeInTheDocument()
    expect(screen.getByTestId('admin-materialized-views-refresh-lock')).toBeInTheDocument()
    expect(screen.getByTestId('admin-materialized-views-refresh-status')).toBeInTheDocument()
    expect(screen.getByTestId('admin-materialized-views-refresh-views')).toBeInTheDocument()
    expect(screen.getByTestId('admin-materialized-views-runtime')).toBeInTheDocument()
    expect(screen.getByTestId('admin-materialized-views-backend')).toHaveTextContent('postgresql')
    expect(screen.getByTestId('admin-materialized-views-status')).toBeInTheDocument()
    expect(screen.getByText('mv_lncrna_chipseq_overlaps')).toBeInTheDocument()
    expect(screen.getByText('Heap: 8 kB')).toBeInTheDocument()
    expect(screen.getByText('Source: autoanalyze')).toBeInTheDocument()
    expect(screen.getByText('healthy')).toBeInTheDocument()
    expect(screen.getByText('No action needed.')).toBeInTheDocument()
  })
})
