import { describe, it, expect } from 'vitest'
import { AxiosError } from 'axios'

import { parseError } from './errorParser'

describe('parseError', () => {
  it('extracts structured error code from backend detail object', () => {
    const detail = {
      error: 'QUERY_TOO_BROAD',
      suggest_filters: ['mark_type', 'min_binding_affinity'],
      message: "Query for chr1 is too broad without materialized view 'mv_lncrna_chipseq_overlaps'.",
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

    const parsed = parseError(error)
    expect(parsed.type).toBe('validation')
    expect(parsed.statusCode).toBe(400)
    expect(parsed.message).toContain('Query for chr1 is too broad')
    expect(parsed.errorCode).toBe('QUERY_TOO_BROAD')
    expect(parsed.suggestFilters).toEqual(['mark_type', 'min_binding_affinity'])
  })
})
