import { describe, expect, it } from "vitest";

import {
  appendCompareGenes,
  buildCompareSignature,
  COMPARE_MAX_GENES,
  mapSelectedIdsToGenes,
  parseCompareIdentifiers,
} from "../ChIPSeqComparePage.utils";

describe("ChIPSeqComparePage utils", () => {
  it("parses pasted identifiers with dedupe", () => {
    expect(parseCompareIdentifiers("MALAT1\nNEAT1, MALAT1; 17276")).toEqual([
      "MALAT1",
      "NEAT1",
      "17276",
    ]);
  });

  it("appends genes with dedupe and preserves order", () => {
    const result = appendCompareGenes(
      [
        { gene_id: 1, gene_name: "A" },
        { gene_id: 2, gene_name: "B" },
      ],
      [
        { gene_id: 2, gene_name: "B" },
        { gene_id: 3, gene_name: "C" },
      ],
      COMPARE_MAX_GENES,
    );

    expect(result.genes.map((gene) => gene.gene_id)).toEqual([1, 2, 3]);
    expect(result.truncatedCount).toBe(0);
  });

  it("caps appended genes at the v1 max count", () => {
    const current = Array.from({ length: COMPARE_MAX_GENES }, (_, index) => ({
      gene_id: index + 1,
      gene_name: `Gene-${index + 1}`,
    }));
    const result = appendCompareGenes(current, [
      { gene_id: 99, gene_name: "Overflow" },
    ]);

    expect(result.genes).toHaveLength(COMPARE_MAX_GENES);
    expect(result.truncatedCount).toBe(1);
  });

  it("maps selected ids from available genes first and falls back to existing genes", () => {
    const mapped = mapSelectedIdsToGenes(
      [2, 1],
      [{ gene_id: 1, gene_name: "MALAT1" }],
      [{ gene_id: 2, gene_name: "NEAT1" }],
    );

    expect(mapped.map((gene) => gene.gene_name)).toEqual(["NEAT1", "MALAT1"]);
  });

  it("changes signature when request ordering changes", () => {
    const signatureA = buildCompareSignature({
      genes: [
        { gene_id: 1, gene_name: "A" },
        { gene_id: 2, gene_name: "B" },
      ],
      marks: ["H3K27me3", "H3K4me3"],
      cellTypes: ["K562", "HepG2"],
      metric: "median_fold_enrichment",
      flanking: 10000,
    });
    const signatureB = buildCompareSignature({
      genes: [
        { gene_id: 2, gene_name: "B" },
        { gene_id: 1, gene_name: "A" },
      ],
      marks: ["H3K27me3", "H3K4me3"],
      cellTypes: ["K562", "HepG2"],
      metric: "median_fold_enrichment",
      flanking: 10000,
    });

    expect(signatureA).not.toBe(signatureB);
  });
});
