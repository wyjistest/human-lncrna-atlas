import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { AxiosError } from 'axios'

import { OverlapHeatmapMatrix } from '../OverlapHeatmapMatrix'
import * as overlapHooks from '@/hooks/useLncRNAChIPSeqOverlap'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
    i18n: { language: 'en' },
  }),
}))

vi.mock('@/hooks/useLncRNAChIPSeqOverlap', () => ({
  useOverlapHeatmap: vi.fn(),
}))

describe('OverlapHeatmapMatrix', () => {
  it('renders structured backend error message for QUERY_TOO_BROAD', () => {
    const detail = {
      error: 'QUERY_TOO_BROAD',
      suggest_filters: ['min_binding_affinity'],
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

    vi.mocked(overlapHooks.useOverlapHeatmap).mockReturnValue({
      data: undefined,
      isLoading: false,
      error,
    })

    render(<OverlapHeatmapMatrix />)

    expect(screen.getByText(/Query for chr1 is too broad/i)).toBeInTheDocument()
    expect(screen.getByText(/Min Binding Affinity/i)).toBeInTheDocument()
  })
})
