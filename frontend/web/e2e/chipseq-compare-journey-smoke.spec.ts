import { test, expect } from '@playwright/test'

/**
 * ChIP-seq compare user journey - mocked smoke
 *
 * Flow:
 * 1) Open gene detail
 * 2) Enter ChIP-seq tab
 * 3) Switch to compare mode and select marks
 * 4) Navigate to Statistics view and verify charts
 */

const TEST_GENE_ID = 17276

const mockGeneDetail = {
  gene_id: TEST_GENE_ID,
  core_id: 'CORE0001',
  gene_name: 'TEST_GENE',
  gene_ensembl_id: 'ENSG00000000001',
  gene_type: 'lncRNA',
  species_id: 1,
  species_name: 'Human',
  chromosome: 'chr1',
  gene_start: 1000,
  gene_end: 2000,
  strand: '+',
  regulation_count: 0,
  disease_count: 0,
  orthologs: [],
}

const mockRegulations = {
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 1,
}

const mockSummary = {
  mark_type: 'H3K27me3',
  total_peaks: 1,
  avg_signal: 5.25,
  max_signal: 6.12,
  avg_fold_enrichment: 5.25,
  promoter_peaks: 0,
  gene_body_peaks: 0,
  upstream_peaks: 0,
  downstream_peaks: 0,
  position_distribution: {},
}

const mockPeaks = {
  gene_id: TEST_GENE_ID,
  gene_name: 'TEST_GENE',
  chromosome: 'chr1',
  gene_start: 1000,
  gene_end: 2000,
  strand: '+',
  region_start: 0,
  region_end: 3000,
  total_peaks: 1,
  marks_present: ['H3K27me3', 'H3K4me3'],
  marks: {
    H3K27me3: [
      {
        peak_id: 1,
        chromosome: 'chr1',
        peak_start: 1100,
        peak_end: 1200,
        summit_position: 1150,
        overlap_type: 'promoter',
        distance_to_tss: 0,
        overlap_bp: 100,
        fold_enrichment: 5,
        qvalue: 0.01,
        mark_type: 'H3K27me3',
        mark_category: 'repressive',
        experiment_id: 1,
      },
    ],
    H3K4me3: [
      {
        peak_id: 2,
        chromosome: 'chr1',
        peak_start: 1300,
        peak_end: 1400,
        summit_position: 1350,
        overlap_type: 'promoter',
        distance_to_tss: 0,
        overlap_bp: 100,
        fold_enrichment: 6,
        qvalue: 0.02,
        mark_type: 'H3K4me3',
        mark_category: 'activating',
        experiment_id: 2,
      },
    ],
  },
}

const mockCompare = {
  gene_id: TEST_GENE_ID,
  gene_name: 'TEST_GENE',
  chromosome: 'chr1',
  region_start: 0,
  region_end: 3000,
  marks: [
    {
      mark_type: 'H3K27me3',
      mark_category: 'repressive',
      display_color: '#9B59B6',
      peaks: [
        {
          peak_id: 1,
          chromosome: 'chr1',
          peak_start: 1100,
          peak_end: 1200,
          summit_position: 1150,
          fold_enrichment: 5,
          qvalue: 0.01,
          mark_type: 'H3K27me3',
        },
      ],
      peak_count: 1,
      avg_fold_enrichment: 5,
      median_fold_enrichment: 5,
      std_fold_enrichment: 0,
      total_coverage_bp: 100,
      peak_width_percentiles: null,
    },
    {
      mark_type: 'H3K4me3',
      mark_category: 'activating',
      display_color: '#27AE60',
      peaks: [
        {
          peak_id: 2,
          chromosome: 'chr1',
          peak_start: 1300,
          peak_end: 1400,
          summit_position: 1350,
          fold_enrichment: 6,
          qvalue: 0.02,
          mark_type: 'H3K4me3',
        },
      ],
      peak_count: 1,
      avg_fold_enrichment: 6,
      median_fold_enrichment: 6,
      std_fold_enrichment: 0,
      total_coverage_bp: 100,
      peak_width_percentiles: null,
    },
  ],
  all_overlaps: [],
  overlap_statistics: {},
  overlapping_regions: [],
  bivalent_regions: [],
}

test.describe('ChIP-seq compare journey - mocked smoke', () => {
  test('enters compare mode and renders statistics chart', async ({ page }) => {
    await page.route(/\/api\/v1\/genes\/\d+$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockGeneDetail),
      })
    })

    await page.route(/\/api\/v1\/regulations(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockRegulations),
      })
    })

    await page.route(/\/api\/v1\/diseases\/gene\/\d+\/associations$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    await page.route(/\/api\/v1\/features\/chipseq\/genes\/\d+\/summary(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSummary),
      })
    })

    await page.route(/\/api\/v1\/features\/chipseq\/genes\/\d+(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockPeaks),
      })
    })

    await page.route(/\/api\/v1\/features\/chipseq\/genes\/\d+\/compare(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockCompare),
      })
    })

    await page.goto(`/genes/${TEST_GENE_ID}`)
    await page.waitForLoadState('domcontentloaded')

    const genomicFeaturesTab = page
      .getByRole('tab', { name: /Genomic Features|基因组特征/i })
      .first()
    await expect(genomicFeaturesTab).toBeVisible({ timeout: 15000 })
    await genomicFeaturesTab.click()
    await expect(genomicFeaturesTab).toHaveAttribute('aria-selected', 'true')

    const chipseqTab = page.getByRole('tab', { name: /ChIP-seq Peaks|ChIP-seq|ChIP|表观遗传/i }).first()
    await expect(chipseqTab).toBeVisible({ timeout: 15000 })
    await chipseqTab.click()

    await expect(page.getByTestId('chipseq-container')).toBeVisible({ timeout: 15000 })

    const compareButton = page.getByTestId('compare-marks-button')
    await expect(compareButton).toBeVisible({ timeout: 15000 })
    await compareButton.click()
    await expect(page.getByTestId('exit-compare-button')).toBeVisible({ timeout: 15000 })

    const markSelector = page.getByTestId('mark-selector')
    await markSelector.first().click()
    const markOption = page.locator('.ant-select-dropdown').getByText('H3K4me3', { exact: false })
    await markOption.first().click()

    const statsTab = page.getByRole('tab', { name: /Statistics|统计/i })
    if ((await statsTab.count()) > 0) {
      await statsTab.first().click()
    }

    await expect(page.getByTestId('radar-compare-chart')).toBeVisible({ timeout: 15000 })
  })
})
