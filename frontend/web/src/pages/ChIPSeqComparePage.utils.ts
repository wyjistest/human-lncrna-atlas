import type { GeneOption } from "@/api/genes";
import type { BatchHeatmapGeneInfo } from "@/hooks/useBatchGeneHeatmap";
import type { HeatmapMetricType, MarkType } from "@/types/chipseq";
import type { components } from "@/types";

type GeneListItem = components["schemas"]["GeneListItem"];

export interface CompareGene extends BatchHeatmapGeneInfo {
  gene_ensembl_id?: string | null;
}

export const COMPARE_MAX_GENES = 10;
export const COMPARE_MAX_IDENTIFIERS = 200;

export function parseCompareIdentifiers(input: string): string[] {
  return Array.from(
    new Set(
      input
        .split(/[\s,;]+/g)
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  );
}

export function mapGeneOptionsToCompareGenes(
  options: GeneOption[],
): CompareGene[] {
  return options.map((option) => ({
    gene_id: option.gene_id,
    gene_name: option.gene_name ?? String(option.gene_id),
    gene_ensembl_id: option.gene_ensembl_id,
  }));
}

export function mapGeneListItemsToCompareGenes(
  items: GeneListItem[],
): CompareGene[] {
  return items.map((item) => ({
    gene_id: item.gene_id,
    gene_name: item.gene_name ?? String(item.gene_id),
    gene_ensembl_id: item.gene_ensembl_id,
    chromosome: item.chromosome ?? undefined,
    start: item.gene_start ?? undefined,
    end: item.gene_end ?? undefined,
  }));
}

export function appendCompareGenes(
  current: CompareGene[],
  incoming: CompareGene[],
  maxCount: number = COMPARE_MAX_GENES,
) {
  const merged: CompareGene[] = [];
  const seen = new Set<number>();

  for (const gene of [...current, ...incoming]) {
    if (seen.has(gene.gene_id)) continue;
    seen.add(gene.gene_id);
    merged.push(gene);
  }

  return {
    genes: merged.slice(0, maxCount),
    truncatedCount: Math.max(merged.length - maxCount, 0),
  };
}

export function mapSelectedIdsToGenes(
  selectedIds: number[],
  availableGenes: CompareGene[],
  fallbackGenes: CompareGene[] = [],
) {
  const geneMap = new Map<number, CompareGene>();

  for (const gene of [...availableGenes, ...fallbackGenes]) {
    geneMap.set(gene.gene_id, gene);
  }

  return selectedIds
    .map((geneId) => geneMap.get(geneId))
    .filter((gene): gene is CompareGene => gene !== undefined);
}

export function buildCompareSignature(params: {
  genes: CompareGene[];
  marks: MarkType[];
  cellTypes: string[];
  metric: HeatmapMetricType;
  flanking: number;
}) {
  return JSON.stringify({
    geneIds: params.genes.map((gene) => gene.gene_id),
    marks: params.marks,
    cellTypes: params.cellTypes,
    metric: params.metric,
    flanking: params.flanking,
  });
}
