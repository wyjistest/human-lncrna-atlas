import { test, expect } from '@playwright/test'

/**
 * Smoke: Genes page should render with mocked /api/v1/genes.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/genes'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildMockGenesResponse() {
  return {
    items: [
      {
        gene_id: 1,
        core_id: 'CORE001',
        gene_name: 'MALAT1',
        gene_ensembl_id: 'ENSG00000001',
        gene_type: 'lncRNA',
        species_id: 1,
        species_name: 'Human',
        chromosome: 'chr1',
        gene_start: 100,
        gene_end: 200,
        regulation_count: 0,
      },
    ],
    total: 1,
    page: 1,
    page_size: 100,
    total_pages: 1,
  }
}

test.describe('Genes - mocked smoke', () => {
  test('renders genes list with mocked API', async ({ page }) => {
    await page.route(/\/api\/v1\/genes(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockGenesResponse()),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('genes-page')).toBeVisible({ timeout: 15000 })

    const table = page.getByTestId('genes-table')
    await expect(table).toBeVisible({ timeout: 15000 })
    await expect(table.getByText('MALAT1')).toBeVisible({ timeout: 15000 })
  })
})

