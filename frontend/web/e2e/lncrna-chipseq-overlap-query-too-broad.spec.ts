import { test, expect } from '@playwright/test'

/**
 * Regression: QUERY_TOO_BROAD should provide actionable guidance.
 *
 * Coverage:
 * - UI renders backend-provided suggest_filters as clickable tags
 * - Clicking a suggestion highlights the corresponding filter control
 *
 * This test uses network interception to stay independent of backend data.
 */

const PAGE_URL = '/lncrna-chipseq-overlap'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildQueryTooBroadResponse() {
  return {
    detail: {
      error: 'QUERY_TOO_BROAD',
      suggest_filters: ['mark_type', 'cell_type', 'min_binding_affinity'],
      message:
        "Query for chr1 is too broad without materialized view 'mv_lncrna_chipseq_overlaps'. Please add additional filters.",
      chromosome: 'chr1',
      using_materialized_view: false,
    },
  }
}

test.describe('lncRNA-ChIP-seq Overlap - QUERY_TOO_BROAD Guidance', () => {
  test('clicking suggested filter highlights filter panel control', async ({ page }) => {
    await page.route('**/api/v1/lncrna-chipseq-overlap*', async (route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname.endsWith('/api/v1/lncrna-chipseq-overlap')) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify(buildQueryTooBroadResponse()),
        })
        return
      }
      await route.fallback()
    })

    // Keep IGV initialization from making the test depend on backend data.
    await page.route('**/api/v1/igv/**', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'IGV not needed for this test' }),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    const suggestedMarkType = page.locator('[data-testid="overlap-suggest-filter-mark-type"]')
    await expect(suggestedMarkType).toBeVisible({ timeout: 15000 })

    const markTypeControl = page.locator('[data-testid="overlap-filter-mark-type"]')
    await expect(markTypeControl).toBeVisible({ timeout: 15000 })
    await expect(markTypeControl).toHaveCSS('box-shadow', 'none')

    await suggestedMarkType.click()
    await expect(markTypeControl).toHaveCSS('box-shadow', /2px/)
  })
})
