import { test, expect } from '@playwright/test'

/**
 * Smoke: Stats page should render with mocked /api/v1/stats/overview and /api/v1/stats/detailed.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/stats'

function buildMockOverviewResponse() {
  return {
    total_genes: 17248,
    total_lncrna: 1,
    total_regulations: 1,
    total_trait_associations: 1,
  }
}

function buildMockDetailedResponse() {
  return {
    species_distribution: [
      { species_name: 'Human', count: 1 },
    ],
    ba_distribution: [
      { range_start: 0, range_end: 200, count: 1 },
    ],
    top_lncrnas: [
      {
        gene_id: 1,
        core_id: 'CORE001',
        gene_name: 'MALAT1',
        gene_ensembl_id: 'ENSG00000001',
        gene_type: 'lncRNA',
        species_name: 'Human',
        regulation_count: 1,
      },
    ],
    ba_range: {
      min_ba: 0,
      max_ba: 200,
      avg_ba: 120,
      total_count: 1,
    },
  }
}

test.describe('Stats - mocked smoke', () => {
  test('renders stats report with mocked API', async ({ page }) => {
    await page.route('**/api/v1/stats/overview*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockOverviewResponse()),
      })
    })

    await page.route('**/api/v1/stats/detailed*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockDetailedResponse()),
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('stats-page')).toBeVisible({ timeout: 15000 })

    const report = page.getByTestId('stats-report')
    await expect(report).toBeVisible({ timeout: 15000 })
    await expect(report.getByText('MALAT1')).toBeVisible({ timeout: 15000 })
  })
})
