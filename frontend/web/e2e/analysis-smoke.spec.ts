import { test, expect } from '@playwright/test'

/**
 * Smoke: Analysis page should render with mocked /api/v1/analysis/summary and /api/v1/export/high-affinity.
 *
 * This test is intentionally fully mocked to keep CI fast and independent of
 * backend/DB state.
 */

const PAGE_URL = '/analysis'
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

function buildMockAnalysisSummary() {
  return {
    high_affinity: {
      total_regulations: 1,
      unique_lncrnas: 1,
      unique_targets: 1,
      avg_ba: 150.5,
      max_ba: 150.5,
      top_lncrnas: [
        { name: 'MALAT1', target_count: 1, avg_ba: 150.5 },
      ],
    },
    conservation: {
      four_species: 0,
      three_species: 0,
      two_species: 0,
      total_conserved: 0,
    },
    epigenetic: {
      total_overlaps: 0,
      by_mark: {},
      by_cell_type: {},
      bivalent_domains: 0,
      active_marks: 0,
      repressive_marks: 0,
    },
    disease: {
      total_diseases: 0,
      total_lncrnas: 0,
      total_genes: 0,
      avg_connections: 0,
    },
  }
}

function buildMockHighAffinityResponse() {
  return {
    data: [
      {
        lncrna_gene_id: 1,
        lncrna_name: 'MALAT1',
        target_gene_id: 100,
        target_name: 'TP53',
        binding_affinity: 150.5,
        species_id: 1,
        species_name: 'Human',
        chr: 'chr11',
        start_in_genome: 100,
        end_in_genome: 200,
      },
    ],
    total: 1,
    query_params: { min_ba: 100, limit: 1000 },
  }
}

test.describe('Analysis - mocked smoke', () => {
  test('renders analysis tabs and high-affinity table with mocked API', async ({ page }) => {
    await page.route('**/api/v1/analysis/summary*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockAnalysisSummary()),
      })
    })

    await page.route('**/api/v1/export/high-affinity*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockHighAffinityResponse()),
      })
    })

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByTestId('analysis-page')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('analysis-tabs')).toBeVisible({ timeout: 15000 })

    await expect(page.getByText('MALAT1')).toBeVisible({ timeout: 15000 })
  })
})

