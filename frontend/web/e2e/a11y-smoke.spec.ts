import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { assertNoSeriousA11yViolations } from './helpers/a11y'

/**
 * A11y smoke（axe-core）：
 * - 覆盖关键用户页面（不含 Admin）
 * - 仅阻断 serious/critical violations（保守策略，降低误报/flake）
 * - 全部使用 network interception，保持 CI 快速且不依赖后端/DB
 */

const DEFAULT_EXCLUDES = [
  // AntD/Portal 相关 overlay 容器（避免扫描到隐藏或临时节点导致误报）
  '.ant-notification',
  '.ant-message',
  '.ant-tooltip',
  '.ant-popover',
  '.ant-dropdown',
  '.ant-select-dropdown',
  '.ant-picker-dropdown',
  '.ant-modal-root',
  '.ant-drawer',
  // placeholder 文本对比度在自动化中噪声较高（真实可用性更多依赖 label/aria-label）
  '.ant-select-placeholder',
  // AntD Table 内部测量行（aria-hidden + focusable 的组合在 axe 下容易误报）
  '.ant-table-measure-row',
]

async function prepareForDeterministicScan(page: Page) {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        transition: none !important;
        animation: none !important;
        scroll-behavior: auto !important;
      }
    `,
  })
}

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

function buildMockStatsOverviewResponse() {
  return {
    total_genes: 17248,
    total_lncrna: 1,
    total_regulations: 1,
    total_trait_associations: 1,
  }
}

function buildMockStatsDetailedResponse() {
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

function buildMockConservationOverviewResponse() {
  return {
    distribution: [
      { conservation_count: 2, lncrna_count: 0, regulation_count: 1, percentage: 0 },
      { conservation_count: 3, lncrna_count: 0, regulation_count: 0, percentage: 0 },
      { conservation_count: 4, lncrna_count: 0, regulation_count: 0, percentage: 0 },
    ],
    top_combinations: [],
  }
}

function buildMockConservationMatrixResponse() {
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

function buildMockConservationRegulationsResponse() {
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

function buildOverlapQueryTooBroadResponse() {
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

test.describe('A11y smoke (axe)', () => {
  test('Genes page', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.route(/\/api\/v1\/genes(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockGenesResponse()),
      })
    })

    await page.goto('/genes')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('genes-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Regulations page', async ({ page }) => {
    await prepareForDeterministicScan(page)

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

    await page.goto('/regulations')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('regulations-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Stats page', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.route('**/api/v1/stats/overview*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockStatsOverviewResponse()),
      })
    })

    await page.route('**/api/v1/stats/detailed*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockStatsDetailedResponse()),
      })
    })

    await page.goto('/stats')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('stats-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Diseases page', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.route(/\/api\/v1\/diseases(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockDiseasesResponse()),
      })
    })

    await page.goto('/diseases')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('diseases-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Analysis page', async ({ page }) => {
    await prepareForDeterministicScan(page)

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

    await page.goto('/analysis')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('analysis-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Conservation page', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.route('**/api/v1/conservation/overview*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockConservationOverviewResponse()),
      })
    })

    await page.route('**/api/v1/conservation/matrix*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockConservationMatrixResponse()),
      })
    })

    await page.route('**/api/v1/conservation/regulations*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildMockConservationRegulationsResponse()),
      })
    })

    await page.goto('/conservation')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('conservation-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Visualization hub page', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.goto('/visualization')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('visualization-page')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })

  test('Overlap page (QUERY_TOO_BROAD view)', async ({ page }) => {
    await prepareForDeterministicScan(page)

    await page.route('**/api/v1/lncrna-chipseq-overlap*', async (route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname.endsWith('/api/v1/lncrna-chipseq-overlap')) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify(buildOverlapQueryTooBroadResponse()),
        })
        return
      }
      await route.fallback()
    })

    // 避免 IGV 初始化导致测试依赖后端数据。
    await page.route('**/api/v1/igv/**', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'IGV not needed for this test' }),
      })
    })

    await page.goto('/lncrna-chipseq-overlap')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.locator('[data-testid="overlap-filter-mark-type"]')).toBeVisible({ timeout: 15000 })

    await assertNoSeriousA11yViolations(page, { exclude: DEFAULT_EXCLUDES })
  })
})
