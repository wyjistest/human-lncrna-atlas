import { fireEvent, render, screen, within } from '@testing-library/react'
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
  useLncRNAChIPSeqOverlapCompareSpecies: vi.fn(),
}))

describe('LncRNAChIPSeqOverlapTable (compare species)', () => {
  it('opens modal and renders cross-species stats table', async () => {
    const compareSpeciesHook = vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapCompareSpecies)

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlaps).mockReturnValue({
      data: { total: 0, page: 1, page_size: 20, items: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)

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
    } as any)

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapCompareSpecies).mockReturnValue({
      data: {
        lncrna_core_id: 11,
        target_core_id: null,
        species_names: { '1': 'Human', '2': 'Chimpanzee' },
        species_stats: {
          1: {
            species_id: 1,
            species_name: 'Human',
            lncrna_gene_id: 1,
            target_gene_id: null,
            statistics: {
              total_overlaps: 2,
              unique_lncrnas: 1,
              unique_target_genes: 1,
              unique_marks: 1,
              unique_cell_types: 1,
              avg_overlap_length: 10,
              avg_binding_affinity: 50,
              avg_peak_strength: 2,
              by_mark_type: [{ mark_type: 'H3K27me3', count: 2, avg_strength: 50 }],
              by_cell_type: [{ cell_type: 'K562', count: 2 }],
              default_filter_applied: false,
              effective_chromosome: null,
            },
          },
        },
      },
      isLoading: false,
      error: null,
    } as any)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <LncRNAChIPSeqOverlapTable enableIGV={false} lncrnaGeneId={1} />
      </QueryClientProvider>
    )

    fireEvent.click(screen.getByTestId('overlap-compare-species'))

    const table = await screen.findByTestId('overlap-compare-species-table')
    expect(within(table).getByText('Human')).toBeInTheDocument()
    expect(within(table).getByText('2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Chimpanzee' }))
    expect(compareSpeciesHook.mock.calls.at(-1)?.[2]).toEqual([1, 3, 4])
  }, 15000)
})
