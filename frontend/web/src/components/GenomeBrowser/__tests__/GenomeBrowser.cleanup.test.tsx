import { render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('igv', () => ({
  default: {
    createBrowser: vi.fn(),
    removeBrowser: vi.fn(),
  },
}))

import GenomeBrowser from '../index'
import igv from 'igv'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/api/genome', () => ({
  genomeApi: {
    getIGVConfig: vi.fn(),
    getIGVConfigForGene: vi.fn(),
  },
}))

import { genomeApi } from '@/api/genome'

const mockIgv = igv as unknown as {
  createBrowser: ReturnType<typeof vi.fn>
  removeBrowser: ReturnType<typeof vi.fn>
}

describe('GenomeBrowser cleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('unsubscribes locuschange handler on unmount', async () => {
    const mockBrowser = {
      on: vi.fn(),
      un: vi.fn(),
      search: vi.fn(async () => {}),
      currentLoci: vi.fn(() => ['all']),
      loadTrack: vi.fn(async () => {}),
      removeTrackByName: vi.fn(),
      removeTrack: vi.fn(),
      trackViews: [],
    }

    vi.mocked(genomeApi.getIGVConfig).mockResolvedValueOnce({
      data: {
        data: {
          genome: 'hg19',
          reference: null,
          locus: 'all',
          tracks: [],
        },
      },
    } as any)

    vi.mocked(mockIgv.createBrowser).mockResolvedValueOnce(mockBrowser as any)

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    })

    const { unmount } = render(
      <QueryClientProvider client={queryClient}>
        <GenomeBrowser speciesId={1} />
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(mockIgv.createBrowser).toHaveBeenCalled()
      expect(mockBrowser.on).toHaveBeenCalledWith('locuschange', expect.any(Function))
    })

    const handler = vi.mocked(mockBrowser.on).mock.calls.find((c) => c[0] === 'locuschange')?.[1]
    expect(handler).toBeTypeOf('function')

    unmount()

    await waitFor(() => {
      expect(mockBrowser.un).toHaveBeenCalledWith('locuschange', handler)
      expect(mockIgv.removeBrowser).toHaveBeenCalled()
    })
  })
})
