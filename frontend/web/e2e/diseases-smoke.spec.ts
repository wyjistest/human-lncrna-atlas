import { test, expect } from '@playwright/test'

/**
 * Smoke: Diseases page should render with mocked /api/v1/diseases.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/diseases'

function buildMockDiseasesResponse() {
  return {
    items: [
      {
        trait_id: 1,
        trait_name: 'Type 2 Diabetes',
        trait_doid: 'DOID:9352',
        ontology_id: 1,
        ontology_cl_id: 'CL:0000000',
        ontology_name: 'cell',
        species_name: 'Human',
        gene_count: 10,
        lncrna_count: 2,
      },
    ],
    total: 1,
    page: 1,
    page_size: 100,
    total_pages: 1,
  }
}

test.describe('Diseases - mocked smoke', () => {
  test('renders diseases table with mocked API', async ({ page }) => {
    await page.route(/\/api\/v1\/diseases(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockDiseasesResponse()),
      })
    })

    await page.goto(PAGE_URL)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('diseases-page')).toBeVisible({ timeout: 15000 })

    const table = page.getByTestId('diseases-table')
    await expect(table).toBeVisible({ timeout: 15000 })
    await expect(table.getByText('Type 2 Diabetes')).toBeVisible({ timeout: 15000 })
  })
})
