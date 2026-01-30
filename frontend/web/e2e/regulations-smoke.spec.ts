import { test, expect } from '@playwright/test'

/**
 * Smoke: Regulations page should render with mocked /api/v1/regulations and /api/v1/stats/ba-range.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/regulations'

function buildMockRegulationsResponse() {
  return {
    items: [
      {
        regulation_id: 1,
        lncrna_gene_id: 1,
        lncrna_gene_name: 'MALAT1',
        target_gene_id: 100,
        target_gene_name: 'TP53',
        species_id: 1,
        species_name: 'Human',
        target_chromosome: 'chr1',
        target_start: 100,
        target_end: 200,
        binding_affinity: 150,
        num_peaks: 1,
      },
    ],
    total: 1,
    page: 1,
    page_size: 100,
    total_pages: 1,
  }
}

function buildMockBARangeResponse() {
  return {
    min_ba: 0,
    max_ba: 200,
    avg_ba: 120,
    total_count: 1,
  }
}

test.describe('Regulations - mocked smoke', () => {
  test('renders regulations table with mocked API', async ({ page }) => {
    await page.route(/\/api\/v1\/regulations(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockRegulationsResponse()),
      })
    })

    await page.route(/\/api\/v1\/stats\/ba-range(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockBARangeResponse()),
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('regulations-page')).toBeVisible({ timeout: 15000 })

    const table = page.getByTestId('regulations-table')
    await expect(table).toBeVisible({ timeout: 15000 })
    await expect(table.getByText('MALAT1')).toBeVisible({ timeout: 15000 })
  })

  test('can use gene_id selectors (mocked)', async ({ page }) => {
    await page.route(/\/api\/v1\/regulations(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockRegulationsResponse()),
      })
    })

    await page.route(/\/api\/v1\/stats\/ba-range(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockBARangeResponse()),
      })
    })

    await page.route(/\/api\/v1\/regulations\/lncrna-options(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          lncrnas: [
            {
              gene_id: 1,
              gene_ensembl_id: 'ENSG00000001',
              gene_name: 'MALAT1',
              species_id: 1,
              species_name: 'Human',
              regulation_count: 42,
            },
          ],
        }),
      })
    })

    await page.route(/\/api\/v1\/regulations\/target-options(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          targets: [
            {
              gene_id: 100,
              gene_ensembl_id: 'ENSG00000100',
              gene_name: 'TP53',
              species_id: 1,
              species_name: 'Human',
              lncrna_count: 12,
            },
          ],
        }),
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('regulations-page')).toBeVisible({ timeout: 15000 })

    // Expand advanced filters
    await page.getByText(/Advanced Filters|高级筛选/).click()

    await expect(page.getByTestId('regulations-lncrna-selector')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('regulations-target-selector')).toBeVisible({ timeout: 15000 })

    // Select lncRNA option -> URL should include gene_id filter (main contract)
    const lncrnaCombobox = page.getByTestId('regulations-lncrna-selector').getByRole('combobox')
    // antd Select option nodes can be unstable to click under virtualization; prefer keyboard selection
    await lncrnaCombobox.click({ force: true })
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/lncrna_gene_id=1/)
  })
})
