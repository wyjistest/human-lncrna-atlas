import { fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { AxiosError } from 'axios'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { LncRNAChIPSeqOverlapTable } from '../index'
import * as overlapHooks from '@/hooks/useLncRNAChIPSeqOverlap'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
    i18n: { language: 'en' },
  }),
}))

vi.mock('@/hooks/useLncRNAChIPSeqOverlap', () => ({
  useLncRNAChIPSeqOverlaps: vi.fn(),
  useLncRNAChIPSeqOverlapsCursor: vi.fn(),
  useLncRNAChIPSeqOverlapSummary: vi.fn(),
  useLncRNAChIPSeqOverlapCompareSpecies: vi.fn(),
}))

describe('LncRNAChIPSeqOverlapTable', () => {
  it('renders structured backend error message for QUERY_TOO_BROAD', () => {
    const detail = {
      error: 'QUERY_TOO_BROAD',
      suggest_filters: ['mark_type', 'cell_type', 'min_binding_affinity'],
      message:
        "Query for chr1 is too broad without materialized view 'mv_lncrna_chipseq_overlaps'. Please add additional filters.",
      chromosome: 'chr1',
      using_materialized_view: false,
    }

    const error = new AxiosError(
      'Request failed with status code 400',
      'ERR_BAD_REQUEST',
      undefined,
      undefined,
      {
        status: 400,
        data: { detail },
        statusText: 'Bad Request',
        headers: {},
        config: {},
      } as any
    )

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlaps).mockReturnValue({
      data: undefined,
      isLoading: false,
      error,
      refetch: vi.fn(),
    })
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapsCursor).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapSummary).mockReturnValue({
      data: undefined,
      isLoading: false,
    })
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapCompareSpecies).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <LncRNAChIPSeqOverlapTable enableIGV={false} />
      </QueryClientProvider>
    )

    const alert = screen.getByRole('alert')
    expect(within(alert).getByText(/Query for chr1 is too broad/i)).toBeInTheDocument()
    expect(within(alert).getByText(/^Mark Type$/i)).toBeInTheDocument()
    expect(within(alert).getByText(/^Cell Type$/i)).toBeInTheDocument()
    expect(within(alert).getByText(/^Min Binding Affinity$/i)).toBeInTheDocument()
  })

  it('highlights the corresponding filter control when clicking a suggested filter tag', async () => {
    const detail = {
      error: 'QUERY_TOO_BROAD',
      suggest_filters: ['mark_type', 'cell_type', 'min_binding_affinity'],
      message:
        "Query for chr1 is too broad without materialized view 'mv_lncrna_chipseq_overlaps'. Please add additional filters.",
      chromosome: 'chr1',
      using_materialized_view: false,
    }

    const error = new AxiosError(
      'Request failed with status code 400',
      'ERR_BAD_REQUEST',
      undefined,
      undefined,
      {
        status: 400,
        data: { detail },
        statusText: 'Bad Request',
        headers: {},
        config: {},
      } as any
    )

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlaps).mockReturnValue({
      data: undefined,
      isLoading: false,
      error,
      refetch: vi.fn(),
    })
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapsCursor).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
      error: null,
      refetch: vi.fn(),
    } as any)
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapSummary).mockReturnValue({
      data: undefined,
      isLoading: false,
    })
    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapCompareSpecies).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <LncRNAChIPSeqOverlapTable enableIGV={false} />
      </QueryClientProvider>
    )

    const markTypeTag = screen.getByTestId('overlap-suggest-filter-mark-type')
    fireEvent.click(markTypeTag)

    await waitFor(() => {
      expect(screen.getByTestId('overlap-filter-mark-type').style.boxShadow).toContain('0 0 0 2px')
    })
  })
})
