import { test, expect } from "@playwright/test";

const PAGE_URL = "/chipseq-compare";

test.describe("ChIP-seq Compare workbench smoke", () => {
  test("resolves pasted genes and renders batch heatmap results", async ({
    page,
  }) => {
    const singleGeneHeatmapCalls: string[] = [];
    const batchHeatmapPayloads: unknown[] = [];

    await page.route(
      /\/api\/v1\/features\/chipseq\/genes\/\d+\/heatmap-matrix/,
      async (route) => {
        singleGeneHeatmapCalls.push(route.request().url());
        await route.abort();
      },
    );

    await page.route("**/api/v1/genes/batch", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              gene_id: 17276,
              core_id: "CORE_1",
              gene_name: "MALAT1",
              gene_ensembl_id: "ENSG00000251562",
              gene_type: "lncRNA",
              species_name: "Human",
              chromosome: "chr11",
              gene_start: 65273689,
              gene_end: 65276843,
              regulation_count: 10,
            },
            {
              gene_id: 17277,
              core_id: "CORE_2",
              gene_name: "NEAT1",
              gene_ensembl_id: "ENSG00000245532",
              gene_type: "lncRNA",
              species_name: "Human",
              chromosome: "chr11",
              gene_start: 65422774,
              gene_end: 65445540,
              regulation_count: 12,
            },
          ],
          missing: ["UNKNOWN1"],
        }),
      });
    });

    await page.route(
      "**/api/v1/features/chipseq/genes/batch-heatmap-matrix",
      async (route) => {
        batchHeatmapPayloads.push(route.request().postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            genes: [
              {
                gene_id: 17276,
                gene_name: "MALAT1",
                gene_ensembl_id: "ENSG00000251562",
                chromosome: "chr11",
                region_start: 65263689,
                region_end: 65286843,
                cell_types: ["K562", "GM12878", "HepG2", "H1-hESC"],
                marks: [
                  "H3K27me3",
                  "H3K9me3",
                  "H3K4me3",
                  "H3K4me1",
                  "H3K27ac",
                  "H3K36me3",
                ],
                metric: "median_fold_enrichment",
                matrix: [
                  [1.2, 0.8, 3.4, 2.1, 1.5, 0.6],
                  [1.1, 0.7, 3.0, 1.9, 1.2, 0.5],
                  [1.5, 0.6, 2.8, 1.6, 1.8, 0.7],
                  [0.9, 0.4, 2.1, 1.3, 1.0, 0.4],
                ],
                total_combinations: 24,
                valid_combinations: 24,
              },
            ],
            total_genes: 2,
            successful_genes: 1,
            failed_genes: [17277],
            query_time_ms: 87,
          }),
        });
      },
    );

    await page.goto(PAGE_URL);
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByTestId("chipseq-compare-page")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId("chipseq-compare-input-card")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId("chipseq-compare-config-card")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId("chipseq-compare-unavailable")).toHaveCount(
      0,
    );

    await page
      .getByTestId("chipseq-compare-paste-input")
      .fill("MALAT1 UNKNOWN1 NEAT1");
    await page.getByTestId("chipseq-compare-resolve-button").click();

    await expect(
      page.getByTestId("chipseq-compare-missing-alert"),
    ).toContainText("UNKNOWN1");

    await page.getByTestId("chipseq-compare-run-button").click();

    await expect(
      page.getByTestId("chipseq-compare-summary-alert"),
    ).toContainText("1/2");
    await expect(
      page.getByTestId("chipseq-compare-summary-cards"),
    ).toBeVisible();
    await expect(
      page.getByTestId("chipseq-compare-card-gene-coverage"),
    ).toContainText("1/2");
    await expect(
      page.getByTestId("chipseq-compare-card-matrix-coverage"),
    ).toContainText("100.0%");
    await expect(page.getByText("NEAT1")).toBeVisible();
    await expect(page.getByTestId("chipseq-compare-results")).toBeVisible();
    await expect(
      page.getByTestId("chipseq-compare-export-button"),
    ).toBeEnabled();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("chipseq-compare-export-button").click(),
    ]);

    expect(download.suggestedFilename()).toMatch(
      /^chipseq-compare_median_fold_enrichment_.*\.csv$/,
    );

    expect(batchHeatmapPayloads).toHaveLength(1);
    expect(singleGeneHeatmapCalls).toEqual([]);
  });
});
