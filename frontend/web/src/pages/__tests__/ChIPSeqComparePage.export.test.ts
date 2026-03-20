import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("file-saver", () => ({
  saveAs: vi.fn(),
}));

import { saveAs } from "file-saver";
import type { BatchHeatmapMatrixResponse } from "@/types/chipseq";
import type { CompareGene } from "../ChIPSeqComparePage.utils";
import {
  buildBatchCompareCsv,
  exportBatchCompareCsv,
} from "../ChIPSeqComparePage.export";

const mockSaveAs = vi.mocked(saveAs);

function createSubmittedRequest(overrides?: Partial<{
  genes: CompareGene[];
  marks: Array<
    | "H3K27me3"
    | "H3K4me3"
    | "H3K27ac"
    | "H3K4me1"
    | "H3K36me3"
    | "H3K9me3"
  >;
  cellTypes: string[];
  metric:
    | "median_fold_enrichment"
    | "peak_count"
    | "total_coverage_bp"
    | "avg_signal";
}> = {}) {
  return {
    genes: overrides?.genes ?? [
      {
        gene_id: 17276,
        gene_name: "MALAT1",
        gene_ensembl_id: "ENSG00000251562",
      },
      {
        gene_id: 17277,
        gene_name: "=NEAT1",
        gene_ensembl_id: "ENSG00000245532",
      },
    ],
    marks: overrides?.marks ?? ["H3K27me3", "H3K4me3"],
    cellTypes: overrides?.cellTypes ?? ["K562", "HepG2"],
    metric: overrides?.metric ?? "median_fold_enrichment",
  };
}

function createResponse(
  overrides?: Partial<BatchHeatmapMatrixResponse>,
): BatchHeatmapMatrixResponse {
  return {
    genes: [
      {
        gene_id: 17276,
        gene_name: "MALAT1",
        gene_ensembl_id: "ENSG00000251562",
        chromosome: "chr11",
        region_start: 65263689,
        region_end: 65286843,
        cell_types: ["K562", "HepG2"],
        marks: ["H3K27me3", "H3K4me3"],
        metric: "median_fold_enrichment",
        matrix: [
          [1.2, null],
          [0.7, 2.3],
        ],
        total_combinations: 4,
        valid_combinations: 3,
      },
    ],
    total_genes: 2,
    successful_genes: 1,
    failed_genes: [17277],
    query_time_ms: 87,
    ...overrides,
  };
}

describe("ChIPSeqComparePage export helper", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-20T12:34:56Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("builds flattened csv rows for successful matrices and failed genes in submitted order", () => {
    const csv = buildBatchCompareCsv({
      submittedRequest: createSubmittedRequest(),
      response: createResponse(),
    });

    const lines = csv.split("\n");

    expect(lines[0]).toBe(
      "gene_status,failure_reason,gene_id,gene_name,gene_ensembl_id,chromosome,region_start,region_end,cell_type,mark,metric,value,has_data",
    );
    expect(lines[1]).toContain("success");
    expect(lines[1]).toContain("17276");
    expect(lines[1]).toContain("K562");
    expect(lines[1]).toContain("H3K27me3");
    expect(lines[1]).toContain("1.2");
    expect(lines[2]).toContain("success");
    expect(lines[2]).toContain(",H3K4me3,median_fold_enrichment,,false");
    expect(lines[5]).toContain("failed");
    expect(lines[5]).toContain("not_returned_by_batch_query");
    expect(lines[5]).toContain(",'=NEAT1,");
  });

  it("exports a bom-prefixed csv file with metric-specific filename", async () => {
    exportBatchCompareCsv({
      submittedRequest: createSubmittedRequest(),
      response: createResponse(),
    });

    expect(mockSaveAs).toHaveBeenCalledTimes(1);

    const [blob, filename] = mockSaveAs.mock.calls[0] ?? [];
    expect(blob).toBeInstanceOf(Blob);
    expect(filename).toBe(
      "chipseq-compare_median_fold_enrichment_20260320_123456.csv",
    );
    expect(blob).toBeInstanceOf(Blob);
    expect((blob as Blob).type).toBe("text/csv;charset=utf-8;");
  });
});
