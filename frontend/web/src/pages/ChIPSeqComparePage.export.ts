import { saveAs } from "file-saver";
import { createTimestampedFilename } from "@/utils/exportUtils";
import { escapeCSV } from "@/utils/csv";
import type { BatchHeatmapMatrixResponse, HeatmapMetricType, MarkType } from "@/types/chipseq";
import type { CompareGene } from "./ChIPSeqComparePage.utils";

interface SubmittedCompareExportRequest {
  genes: CompareGene[];
  marks: MarkType[];
  cellTypes: string[];
  metric: HeatmapMetricType;
}

interface BatchCompareCsvParams {
  submittedRequest: SubmittedCompareExportRequest;
  response: BatchHeatmapMatrixResponse;
}

const CSV_HEADERS = [
  "gene_status",
  "failure_reason",
  "gene_id",
  "gene_name",
  "gene_ensembl_id",
  "chromosome",
  "region_start",
  "region_end",
  "cell_type",
  "mark",
  "metric",
  "value",
  "has_data",
] as const;

type CsvHeader = (typeof CSV_HEADERS)[number];

type CsvRow = Record<CsvHeader, string | number>;

function toCsvLine(row: CsvRow): string {
  return CSV_HEADERS.map((header) => escapeCSV(row[header])).join(",");
}

function createSuccessRows(params: BatchCompareCsvParams): CsvRow[] {
  const responseGeneMap = new Map(
    params.response.genes.map((gene) => [gene.gene_id, gene] as const),
  );

  return params.submittedRequest.genes.flatMap((submittedGene) => {
    const responseGene = responseGeneMap.get(submittedGene.gene_id);
    if (!responseGene) {
      return [];
    }

    return params.submittedRequest.cellTypes.flatMap((cellType) => {
      const cellTypeIndex = responseGene.cell_types.indexOf(cellType);

      return params.submittedRequest.marks.map((mark) => {
        const markIndex = responseGene.marks.indexOf(mark);
        const value =
          cellTypeIndex >= 0 && markIndex >= 0
            ? responseGene.matrix[cellTypeIndex]?.[markIndex]
            : null;
        const hasData = value !== null && value !== undefined;

        return {
          gene_status: "success",
          failure_reason: "",
          gene_id: submittedGene.gene_id,
          gene_name: responseGene.gene_name ?? submittedGene.gene_name,
          gene_ensembl_id:
            responseGene.gene_ensembl_id ?? submittedGene.gene_ensembl_id ?? "",
          chromosome: responseGene.chromosome ?? "",
          region_start: responseGene.region_start ?? "",
          region_end: responseGene.region_end ?? "",
          cell_type: cellType,
          mark,
          metric: params.submittedRequest.metric,
          value: hasData ? value : "",
          has_data: hasData ? "true" : "false",
        };
      });
    });
  });
}

function createFailedRows(params: BatchCompareCsvParams): CsvRow[] {
  const successfulGeneIds = new Set(
    params.response.genes.map((gene) => gene.gene_id),
  );
  const failedGeneIds = new Set(params.response.failed_genes);

  return params.submittedRequest.genes
    .filter(
      (gene) => failedGeneIds.has(gene.gene_id) || !successfulGeneIds.has(gene.gene_id),
    )
    .map((gene) => ({
      gene_status: "failed",
      failure_reason: "not_returned_by_batch_query",
      gene_id: gene.gene_id,
      gene_name: gene.gene_name,
      gene_ensembl_id: gene.gene_ensembl_id ?? "",
      chromosome: "",
      region_start: "",
      region_end: "",
      cell_type: "",
      mark: "",
      metric: params.submittedRequest.metric,
      value: "",
      has_data: "",
    }));
}

export function buildBatchCompareCsv(params: BatchCompareCsvParams): string {
  const rows = [
    ...createSuccessRows(params),
    ...createFailedRows(params),
  ];

  return [CSV_HEADERS.join(","), ...rows.map(toCsvLine)].join("\n");
}

export function exportBatchCompareCsv(params: BatchCompareCsvParams): string {
  const filename = `${createTimestampedFilename(
    `chipseq-compare_${params.submittedRequest.metric}`,
  )}.csv`;
  const csv = buildBatchCompareCsv(params);
  const blob = new Blob(["\uFEFF" + csv], {
    type: "text/csv;charset=utf-8;",
  });

  saveAs(blob, filename);
  return filename;
}
