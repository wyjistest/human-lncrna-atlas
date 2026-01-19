import { test, expect } from '@playwright/test'

/**
 * Smoke: Conservation page should render with mocked conservation endpoints.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/conservation'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildMockOverviewResponse() {
  return {
    distribution: [
      { conservation_count: 2, lncrna_count: 0, regulation_count: 1, percentage: 0 },
      { conservation_count: 3, lncrna_count: 0, regulation_count: 0, percentage: 0 },
      { conservation_count: 4, lncrna_count: 0, regulation_count: 0, percentage: 0 },
    ],
    top_combinations: [],
  }
}

function buildMockMatrixResponse() {
  return {
    species: [
      { id: 1, name: 'Human' },
      { id: 2, name: 'Chimpanzee' },
      { id: 3, name: 'Macaque' },
      { id: 4, name: 'Marmoset' },
    ],
    regulation_matrix: [
      [10, 1, 0, 0],
      [1, 10, 0, 0],
      [0, 0, 10, 0],
      [0, 0, 0, 10],
    ],
  }
}

function buildMockRegulationsResponse() {
  return {
    items: [
      {
        core_id: 1,
        lncrna_gene_name: 'MALAT1',
        lncrna_ensembl_id: 'ENSG00000251562',
        target_gene_name: 'TP53',
        target_ensembl_id: 'ENSG00000141510',
        conservation_label: '1100',
        species_count: 2,
        species_ids: [1, 2],
        avg_binding_affinity: 85.5,
        species_binding_affinities: [
          { species_id: 1, species_name: 'Human', binding_affinity: 90.0 },
          { species_id: 2, species_name: 'Chimpanzee', binding_affinity: 81.0 },
        ],
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
  }
}

test.describe('Conservation - mocked smoke', () => {
  test('renders conservation matrix and regulations table with mocked API', async ({ page }) => {
    await page.route('**/api/v1/conservation/overview*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockOverviewResponse()),
      })
    })

    await page.route('**/api/v1/conservation/matrix*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockMatrixResponse()),
      })
    })

    await page.route('**/api/v1/conservation/regulations*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockRegulationsResponse()),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('conservation-page')).toBeVisible({ timeout: 15000 })

    await expect(page.getByTestId('conservation-matrix')).toBeVisible({ timeout: 15000 })

    const table = page.getByTestId('conservation-table')
    await expect(table).toBeVisible({ timeout: 15000 })
    await expect(table.getByText('MALAT1')).toBeVisible({ timeout: 15000 })
  })
})

