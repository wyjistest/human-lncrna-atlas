import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
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
}))

describe('LncRNAChIPSeqOverlapTable (cursor mode)', () => {
  it('renders Load more button and calls fetchNextPage', async () => {
    const fetchNextPage = vi.fn()

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlaps).mockReturnValue({
      data: { total: 0, page: 1, page_size: 20, items: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapSummary).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any)

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapsCursor).mockReturnValue({
      data: {
        pages: [
          {
            total: 3,
            page_size: 2,
            items: [
              {
                overlap_id: 'reg_1_peak_1',
                regulation_id: 1,
                lncrna_gene_id: 1,
                lncrna_name: 'lnc',
                target_gene_id: 2,
                target_gene_name: 'tgt',
                mark_type: 'H3K27me3',
                mark_category: 'repressive',
                cell_type: 'K562',
                chromosome: 'chr22',
                lncrna_binding_start: 10,
                lncrna_binding_end: 20,
                peak_start: 15,
                peak_end: 25,
                overlap_start: 15,
                overlap_end: 20,
                overlap_length: 5,
                binding_affinity: 1,
                peak_fold_enrichment: 1,
                peak_qvalue: null,
              },
            ],
            next_cursor: 'opaque',
            has_more: true,
            default_filter_applied: false,
            effective_chromosome: 'chr22',
            using_materialized_view: true,
          },
        ],
        pageParams: [undefined],
      },
      isLoading: false,
      isFetchingNextPage: false,
      fetchNextPage,
      error: null,
      refetch: vi.fn(),
    } as any)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <LncRNAChIPSeqOverlapTable enableIGV={false} />
      </QueryClientProvider>
    )

    fireEvent.click(screen.getByTestId('overlap-pagination-mode'))

    const loadMore = await screen.findByTestId('overlap-load-more')
    fireEvent.click(loadMore)

    expect(fetchNextPage).toHaveBeenCalled()
  })
})

