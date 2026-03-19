import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

vi.mock("@/api/chipseq", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/chipseq")>("@/api/chipseq");
  return {
    ...actual,
    chipseqApi: {
      ...actual.chipseqApi,
      getBatchHeatmapMatrix: vi.fn(),
    },
  };
});

import { chipseqApi } from "@/api/chipseq";
import useBatchGeneHeatmap from "../useBatchGeneHeatmap";

const mockGetBatchHeatmapMatrix = vi.mocked(chipseqApi.getBatchHeatmapMatrix);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  return { wrapper, queryClient };
};

describe("useBatchGeneHeatmap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("maps successful and failed genes from a single batch response", async () => {
    mockGetBatchHeatmapMatrix.mockResolvedValueOnce({
      data: {
        genes: [
          {
            gene_id: 17276,
            gene_name: "MALAT1",
            gene_ensembl_id: "ENSG00000251562",
            chromosome: "chr11",
            region_start: 1,
            region_end: 2,
            cell_types: ["K562"],
            marks: ["H3K27me3"],
            metric: "median_fold_enrichment",
            matrix: [[1.2]],
            total_combinations: 1,
            valid_combinations: 1,
          },
        ],
        total_genes: 2,
        successful_genes: 1,
        failed_genes: [17277],
        query_time_ms: 42,
      },
    } as never);

    const genes = [
      { gene_id: 17276, gene_name: "MALAT1" },
      { gene_id: 17277, gene_name: "NEAT1" },
    ];

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useBatchGeneHeatmap(
          genes,
          ["H3K27me3"],
          ["K562"],
          "median_fold_enrichment",
        ),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledWith(
      {
        gene_ids: [17276, 17277],
        marks: ["H3K27me3"],
        cell_types: ["K562"],
        metric: "median_fold_enrichment",
        flanking: 10000,
      },
      expect.anything(),
    );
    expect(result.current.data).toHaveLength(1);
    expect(result.current.failedGeneIds).toEqual([17277]);
    expect(result.current.failedGeneNames).toEqual(["NEAT1"]);
    expect(result.current.successfulGeneNames).toEqual(["MALAT1"]);
    expect(result.current.queryTimeMs).toBe(42);
  });

  it("surfaces request errors as hook errors", async () => {
    mockGetBatchHeatmapMatrix.mockRejectedValueOnce(
      new Error("network failed"),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useBatchGeneHeatmap(
          [{ gene_id: 17276, gene_name: "MALAT1" }],
          ["H3K27me3"],
          ["K562"],
          "median_fold_enrichment",
          10000,
          { retry: 0 },
        ),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("network failed");
    expect(result.current.queryStatus[0]?.isError).toBe(true);
  });
});
