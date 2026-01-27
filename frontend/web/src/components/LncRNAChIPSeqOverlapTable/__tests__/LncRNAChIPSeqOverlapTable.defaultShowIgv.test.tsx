import { render, screen } from '@testing-library/react'
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

// Keep this test focused on the default visibility logic; avoid pulling IGV runtime in jsdom.
vi.mock('@/components/GenomeBrowser', () => ({
  default: () => <div data-testid="mock-genome-browser" />,
}))

vi.mock('@/components/GenomeBrowser/GenomeBrowserToolbar', () => ({
  default: () => <div data-testid="mock-genome-browser-toolbar" />,
}))

vi.mock('@/api/features', () => ({
  getRepeatMaskerClassTracks: vi.fn(async () => ({ data: { data: { tracks: [] } } })),
}))

vi.mock('@/api/genome', () => ({
  genomeApi: {
    getChIPSeqMarks: vi.fn(async () => ({ data: { data: { marks: [] } } })),
  },
}))

describe('LncRNAChIPSeqOverlapTable (IGV default visibility)', () => {
  it('does not render IGV section when defaultShowIGV=false', () => {
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

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapCompareSpecies).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any)

    vi.mocked(overlapHooks.useLncRNAChIPSeqOverlapsCursor).mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
      error: null,
      refetch: vi.fn(),
    } as any)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    // Cast to any so the test can be written before the prop is formally added.
    const Table: any = LncRNAChIPSeqOverlapTable
    render(
      <QueryClientProvider client={queryClient}>
        <Table enableIGV={true} defaultShowIGV={false} />
      </QueryClientProvider>
    )

    expect(screen.queryByText('Genome Browser')).not.toBeInTheDocument()
  })
})

