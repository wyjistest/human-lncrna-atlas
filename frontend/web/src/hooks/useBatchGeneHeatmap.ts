/**
 * useBatchGeneHeatmap Hook
 * 使用单次 batch API 请求获取多个基因的热图矩阵。
 */

import { QueryClient, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { chipseqApi, chipseqQueryKeys } from "@/api/chipseq";
import type {
  BatchHeatmapMatrixResponse,
  HeatmapMetricType,
  MarkType,
} from "@/types/chipseq";

export interface BatchHeatmapGeneInfo {
  gene_id: number;
  gene_name: string;
  chromosome?: string;
  start?: number;
  end?: number;
}

interface UseBatchGeneHeatmapOptions {
  /** 是否启用查询 */
  enabled?: boolean;
  /** 缓存时间 */
  staleTime?: number;
  /** 重试次数 */
  retry?: number;
}

interface BatchGeneQueryStatus {
  gene_id: number;
  gene_name: string;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
  error: Error | null;
}

export function useBatchGeneHeatmap(
  genes: BatchHeatmapGeneInfo[],
  marks: MarkType[],
  cellTypes: string[],
  metric: HeatmapMetricType,
  flanking: number = 10000,
  options?: UseBatchGeneHeatmapOptions,
) {
  const enabled = options?.enabled ?? true;
  const staleTime = options?.staleTime ?? 30 * 60 * 1000;
  const retry = options?.retry ?? 2;

  const geneIds = useMemo(() => genes.map((gene) => gene.gene_id), [genes]);

  const query = useQuery({
    queryKey: chipseqQueryKeys.batchHeatmapMatrix(
      geneIds,
      marks,
      cellTypes,
      metric,
      flanking,
    ),
    queryFn: async ({ signal }): Promise<BatchHeatmapMatrixResponse> => {
      const response = await chipseqApi.getBatchHeatmapMatrix(
        {
          gene_ids: geneIds,
          marks,
          cell_types: cellTypes,
          metric,
          flanking,
        },
        signal,
      );
      return response.data;
    },
    enabled:
      enabled && geneIds.length > 0 && marks.length > 0 && cellTypes.length > 0,
    staleTime,
    retry,
  });

  const data = query.data?.genes ?? [];
  const failedGeneIds = query.data?.failed_genes ?? [];
  const successfulGeneIds = useMemo(
    () => data.map((item) => item.gene_id),
    [data],
  );

  const failedGeneNames = useMemo(
    () =>
      genes
        .filter((gene) => failedGeneIds.includes(gene.gene_id))
        .map((gene) => gene.gene_name),
    [genes, failedGeneIds],
  );

  const successfulGeneNames = useMemo(
    () =>
      genes
        .filter((gene) => successfulGeneIds.includes(gene.gene_id))
        .map((gene) => gene.gene_name),
    [genes, successfulGeneIds],
  );

  const queryStatus = useMemo<BatchGeneQueryStatus[]>(() => {
    return genes.map((gene) => {
      if (query.isPending) {
        return {
          gene_id: gene.gene_id,
          gene_name: gene.gene_name,
          isPending: true,
          isSuccess: false,
          isError: false,
          error: null,
        };
      }

      if (query.isError) {
        return {
          gene_id: gene.gene_id,
          gene_name: gene.gene_name,
          isPending: false,
          isSuccess: false,
          isError: true,
          error: query.error as Error,
        };
      }

      const isFailed = failedGeneIds.includes(gene.gene_id);
      const isSuccessful = successfulGeneIds.includes(gene.gene_id);

      return {
        gene_id: gene.gene_id,
        gene_name: gene.gene_name,
        isPending: false,
        isSuccess: isSuccessful,
        isError: isFailed,
        error: isFailed
          ? new Error(`Failed to load heatmap matrix for gene ${gene.gene_id}`)
          : null,
      };
    });
  }, [
    genes,
    failedGeneIds,
    successfulGeneIds,
    query.error,
    query.isError,
    query.isPending,
  ]);

  return {
    ...query,
    data,
    error: query.error as Error | null,
    response: query.data ?? null,
    failedGeneIds,
    failedGeneNames,
    successfulGeneIds,
    successfulGeneNames,
    queryTimeMs: query.data?.query_time_ms ?? null,
    queryStatus,
  };
}

export async function prefetchBatchGeneHeatmap(
  queryClient: QueryClient,
  genes: BatchHeatmapGeneInfo[],
  marks: MarkType[],
  cellTypes: string[],
  metric: HeatmapMetricType,
  flanking: number = 10000,
) {
  const geneIds = genes.map((gene) => gene.gene_id);

  await queryClient.prefetchQuery({
    queryKey: chipseqQueryKeys.batchHeatmapMatrix(
      geneIds,
      marks,
      cellTypes,
      metric,
      flanking,
    ),
    queryFn: async ({ signal }) => {
      const response = await chipseqApi.getBatchHeatmapMatrix(
        {
          gene_ids: geneIds,
          marks,
          cell_types: cellTypes,
          metric,
          flanking,
        },
        signal,
      );
      return response.data;
    },
    staleTime: 30 * 60 * 1000,
  });
}

export function useBatchGeneHeatmapStatus(
  results: ReturnType<typeof useBatchGeneHeatmap>,
) {
  const { queryStatus } = results;

  return useMemo(() => {
    const loadingGenes = queryStatus
      .filter((status) => status.isPending)
      .map((status) => status.gene_name);
    const failedGenes = queryStatus
      .filter((status) => status.isError)
      .map((status) => status.gene_name);
    const successGenes = queryStatus
      .filter((status) => status.isSuccess)
      .map((status) => status.gene_name);

    return {
      loadingGenes,
      failedGenes,
      successGenes,
      loadingCount: loadingGenes.length,
      failedCount: failedGenes.length,
      successCount: successGenes.length,
      allComplete: queryStatus.every((status) => !status.isPending),
      anySuccess: successGenes.length > 0,
      anyError: failedGenes.length > 0,
    };
  }, [queryStatus]);
}

export default useBatchGeneHeatmap;
