import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { chipseqApi } from "@/api/chipseq";
import { apiClient } from "@/api/client";

describe("chipseqApi.getBatchHeatmapMatrix", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("posts batch payload to the real batch heatmap endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        genes: [],
        total_genes: 2,
        successful_genes: 0,
        failed_genes: [1, 2],
      },
    });

    const payload = {
      gene_ids: [17276, 17277],
      marks: ["H3K27me3", "H3K4me3"] as const,
      cell_types: ["K562", "HepG2"],
      metric: "median_fold_enrichment" as const,
      flanking: 10000,
    };

    await chipseqApi.getBatchHeatmapMatrix(payload);

    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/features/chipseq/genes/batch-heatmap-matrix",
      payload,
      { signal: undefined },
    );
  });
});
