import { describe, expect, it } from "vitest";

import { chipseqQueryKeys } from "@/api/chipseq";

describe("chipseqQueryKeys", () => {
  it("includes flanking in compare keys and does not mutate marks", () => {
    const marks = ["H3K4me3", "H3K27me3"] as const;

    const keyA = chipseqQueryKeys.compare(123, [...marks], 10000);
    const keyB = chipseqQueryKeys.compare(123, [...marks], 20000);

    expect(keyA).not.toEqual(keyB);
    expect(marks).toEqual(["H3K4me3", "H3K27me3"]);
  });

  it("includes flanking in compareCellLines keys and does not mutate cellTypes", () => {
    const cellTypes = ["K562", "GM12878"] as const;

    const key = chipseqQueryKeys.compareCellLines(
      123,
      "H3K27me3",
      [...cellTypes],
      5000,
    );

    expect(key).toEqual([
      "chipseq",
      "gene",
      123,
      "compare-cell-lines",
      "H3K27me3",
      "GM12878,K562",
      5000,
    ]);
    expect(cellTypes).toEqual(["K562", "GM12878"]);
  });

  it("includes flanking in heatmapMatrix keys and is order-insensitive for marks/cellTypes", () => {
    const marksA = ["H3K4me3", "H3K27me3"] as const;
    const marksB = ["H3K27me3", "H3K4me3"] as const;
    const cellTypesA = ["K562", "GM12878"] as const;
    const cellTypesB = ["GM12878", "K562"] as const;

    const keyA = chipseqQueryKeys.heatmapMatrix(
      123,
      [...marksA],
      [...cellTypesA],
      "median_fold_enrichment",
      10000,
    );
    const keyB = chipseqQueryKeys.heatmapMatrix(
      123,
      [...marksB],
      [...cellTypesB],
      "median_fold_enrichment",
      10000,
    );

    expect(keyA).toEqual(keyB);
    expect(marksA).toEqual(["H3K4me3", "H3K27me3"]);
    expect(cellTypesA).toEqual(["K562", "GM12878"]);
  });

  it("keeps batch heatmap keys order-sensitive without mutating inputs", () => {
    const geneIds = [17276, 17277] as const;
    const marks = ["H3K4me3", "H3K27me3"] as const;
    const cellTypes = ["K562", "GM12878"] as const;

    const keyA = chipseqQueryKeys.batchHeatmapMatrix(
      [...geneIds],
      [...marks],
      [...cellTypes],
      "median_fold_enrichment",
      10000,
    );
    const keyB = chipseqQueryKeys.batchHeatmapMatrix(
      [...geneIds].reverse(),
      [...marks].reverse(),
      [...cellTypes].reverse(),
      "median_fold_enrichment",
      10000,
    );

    expect(keyA).not.toEqual(keyB);
    expect(geneIds).toEqual([17276, 17277]);
    expect(marks).toEqual(["H3K4me3", "H3K27me3"]);
    expect(cellTypes).toEqual(["K562", "GM12878"]);
  });
});
