import { screen } from '@testing-library/react'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import MaterializedViews from './index'

vi.mock('@/hooks/useMaterializedViewsStatus', () => ({
  useMaterializedViewsStatus: () => ({
    data: {
      status: 'success',
      refresh_lock_available: true,
      views: [
        {
          name: 'mv_lncrna_chipseq_overlaps',
          exists: true,
          populated: true,
          rows_estimate: 1,
          total_size: '16 kB',
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

    expect(screen.getByText('Materialized Views')).toBeInTheDocument()
    expect(screen.getByText('Refresh Views')).toBeInTheDocument()
    expect(screen.getByText('MV Refresh Lock')).toBeInTheDocument()
  })
})

