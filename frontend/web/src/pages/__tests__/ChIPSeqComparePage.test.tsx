import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../ChIPSeqComparePage.export", () => ({
  exportBatchCompareCsv: vi.fn(),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown> | string) => {
      if (typeof options === "string") {
        return options;
      }
      if (
        options &&
        typeof options === "object" &&
        "defaultValue" in options &&
        typeof options.defaultValue === "string"
      ) {
        return options.defaultValue;
      }
      return key;
    },
    i18n: { language: "en" },
  }),
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      loading: vi.fn(() => vi.fn()),
    },
  };
});

vi.mock("@/api/genes", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/genes")>("@/api/genes");
  return {
    ...actual,
    genesApi: {
      ...actual.genesApi,
      getOptions: vi.fn(),
      batchResolve: vi.fn(),
    },
  };
});

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

vi.mock("@/components/BatchGeneHeatmap/BatchHeatmapMatrix", () => ({
  default: ({
    data,
    metric,
  }: {
    data: Array<{ gene_name: string }>;
    metric?: string;
  }) => (
    <div data-testid="batch-heatmap-matrix-mock">
      {metric ?? "unknown"}:{data.map((item) => item.gene_name).join(",")}
    </div>
  ),
}));

import { genesApi } from "@/api/genes";
import { chipseqApi } from "@/api/chipseq";
import { exportBatchCompareCsv } from "../ChIPSeqComparePage.export";
import ChIPSeqComparePage from "../ChIPSeqComparePage";

const mockBatchResolve = vi.mocked(genesApi.batchResolve);
const mockGetOptions = vi.mocked(genesApi.getOptions);
const mockGetBatchHeatmapMatrix = vi.mocked(chipseqApi.getBatchHeatmapMatrix);
const mockExportBatchCompareCsv = vi.mocked(exportBatchCompareCsv);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 0,
        retry: false,
        retryDelay: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    );
  };
};

describe("ChIPSeqComparePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetOptions.mockResolvedValue({ genes: [] });
  });

  afterEach(() => {
    vi.resetAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("renders the empty state and keeps compare disabled before a gene set is submitted", () => {
    render(<ChIPSeqComparePage />, { wrapper: createWrapper() });

    expect(screen.getByTestId("chipseq-compare-page")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run compare" })).toBeDisabled();
    expect(screen.getByText(/Choose a human gene set and run compare/i)).toBeVisible();
    expect(screen.queryByTestId("chipseq-compare-summary-cards")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("chipseq-compare-export-button"),
    ).not.toBeInTheDocument();
    expect(mockGetBatchHeatmapMatrix).not.toHaveBeenCalled();
  });

  it("resolves pasted identifiers, shows missing genes, and renders batch compare results", async () => {
    mockBatchResolve.mockResolvedValueOnce({
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
    } as never);
    mockGetBatchHeatmapMatrix.mockResolvedValueOnce({
      data: {
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
      },
    } as never);

    const user = userEvent.setup();
    render(<ChIPSeqComparePage />, { wrapper: createWrapper() });

    await user.type(
      screen.getByTestId("chipseq-compare-paste-input"),
      "MALAT1 UNKNOWN1 NEAT1",
    );
    await user.click(screen.getByTestId("chipseq-compare-resolve-button"));

    await waitFor(() => {
      expect(screen.getByTestId("chipseq-compare-missing-alert")).toHaveTextContent(
        "UNKNOWN1",
      );
    });

    const runButton = screen.getByRole("button", { name: "Run compare" });
    await waitFor(() => {
      expect(runButton).not.toBeDisabled();
    });

    await user.click(runButton);

    await waitFor(() => {
      expect(screen.getByTestId("chipseq-compare-summary-alert")).toHaveTextContent(
        "1/2 genes loaded in 87 ms.",
      );
    });

    expect(screen.getByTestId("chipseq-compare-summary-cards")).toBeVisible();
    expect(screen.getByTestId("chipseq-compare-card-gene-coverage")).toHaveTextContent(
      "1/2",
    );
    expect(screen.getByTestId("chipseq-compare-card-failed-genes")).toHaveTextContent(
      "1",
    );
    expect(
      screen.getByTestId("chipseq-compare-card-matrix-coverage"),
    ).toHaveTextContent("100.0%");
    expect(screen.getByTestId("chipseq-compare-card-query-time")).toHaveTextContent(
      "87ms",
    );
    expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledTimes(1);
    expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledWith(
      {
        gene_ids: [17276, 17277],
        marks: [
          "H3K27me3",
          "H3K9me3",
          "H3K4me3",
          "H3K4me1",
          "H3K27ac",
          "H3K36me3",
        ],
        cell_types: ["K562", "GM12878", "HepG2", "H1-hESC"],
        metric: "median_fold_enrichment",
        flanking: 10000,
      },
      expect.anything(),
    );
    expect(screen.getByText("Some genes could not be rendered")).toBeVisible();
    expect(screen.getByText("NEAT1")).toBeVisible();
    expect(screen.getByTestId("batch-heatmap-matrix-mock")).toHaveTextContent(
      "median_fold_enrichment:MALAT1",
    );
    expect(
      screen.getByTestId("chipseq-compare-export-button"),
    ).toBeEnabled();
  });

  it("marks the page dirty after configuration changes and only refetches after update compare", async () => {
    mockBatchResolve
      .mockResolvedValueOnce({
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
        ],
        missing: [],
      } as never)
      .mockResolvedValueOnce({
        items: [
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
        missing: [],
      } as never);

    mockGetBatchHeatmapMatrix
      .mockResolvedValueOnce({
        data: {
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
              matrix: [[1.2]],
              total_combinations: 24,
              valid_combinations: 24,
            },
          ],
          total_genes: 1,
          successful_genes: 1,
          failed_genes: [],
          query_time_ms: 40,
        },
      } as never)
      .mockResolvedValueOnce({
        data: {
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
              matrix: [[1.2]],
              total_combinations: 24,
              valid_combinations: 24,
            },
            {
              gene_id: 17277,
              gene_name: "NEAT1",
              gene_ensembl_id: "ENSG00000245532",
              chromosome: "chr11",
              region_start: 65412774,
              region_end: 65455540,
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
              matrix: [[0.9]],
              total_combinations: 24,
              valid_combinations: 24,
            },
          ],
          total_genes: 2,
          successful_genes: 2,
          failed_genes: [],
          query_time_ms: 55,
        },
      } as never);

    const user = userEvent.setup();
    render(<ChIPSeqComparePage />, { wrapper: createWrapper() });

    await user.type(screen.getByTestId("chipseq-compare-paste-input"), "MALAT1");
    await user.click(screen.getByTestId("chipseq-compare-resolve-button"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Run compare" })).not.toBeDisabled();
    });

    await user.click(screen.getByRole("button", { name: "Run compare" }));

    await waitFor(() => {
      expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByTestId("chipseq-compare-paste-input"), "NEAT1");
    await user.click(screen.getByTestId("chipseq-compare-resolve-button"));

    await waitFor(() => {
      expect(screen.getByTestId("chipseq-compare-dirty-alert")).toBeVisible();
    });

    expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("chipseq-compare-export-button"));

    expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledTimes(1);
    expect(mockExportBatchCompareCsv).toHaveBeenCalledTimes(1);
    expect(mockExportBatchCompareCsv).toHaveBeenCalledWith(
      expect.objectContaining({
        submittedRequest: expect.objectContaining({
          genes: [expect.objectContaining({ gene_id: 17276 })],
          metric: "median_fold_enrichment",
        }),
        response: expect.objectContaining({
          total_genes: 1,
          successful_genes: 1,
        }),
      }),
    );

    await user.click(screen.getByRole("button", { name: "Update compare" }));

    await waitFor(() => {
      expect(mockGetBatchHeatmapMatrix).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("chipseq-compare-summary-alert")).toHaveTextContent(
        "2/2 genes loaded in 55 ms.",
      );
    });

    expect(screen.getByTestId("chipseq-compare-card-gene-coverage")).toHaveTextContent(
      "2/2",
    );
    expect(mockGetBatchHeatmapMatrix).toHaveBeenLastCalledWith(
      {
        gene_ids: [17276, 17277],
        marks: [
          "H3K27me3",
          "H3K9me3",
          "H3K4me3",
          "H3K4me1",
          "H3K27ac",
          "H3K36me3",
        ],
        cell_types: ["K562", "GM12878", "HepG2", "H1-hESC"],
        metric: "median_fold_enrichment",
        flanking: 10000,
      },
      expect.anything(),
    );
  });

  it("shows an error alert when the batch compare request fails", async () => {
    mockBatchResolve.mockResolvedValueOnce({
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
      ],
      missing: [],
    } as never);
    mockGetBatchHeatmapMatrix.mockRejectedValue(new Error("network failed"));

    const user = userEvent.setup();
    render(<ChIPSeqComparePage />, { wrapper: createWrapper() });

    await user.type(screen.getByTestId("chipseq-compare-paste-input"), "MALAT1");
    await user.click(screen.getByTestId("chipseq-compare-resolve-button"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Run compare" })).not.toBeDisabled();
    });

    await user.click(screen.getByRole("button", { name: "Run compare" }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load compare results"),
      ).toBeVisible();
      expect(screen.getByText("network failed")).toBeVisible();
    });
  });

  it("keeps summary cards visible when no successful matrices are returned", async () => {
    mockBatchResolve.mockResolvedValueOnce({
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
      ],
      missing: [],
    } as never);
    mockGetBatchHeatmapMatrix.mockResolvedValueOnce({
      data: {
        genes: [],
        total_genes: 1,
        successful_genes: 0,
        failed_genes: [17276],
        query_time_ms: 22,
      },
    } as never);

    const user = userEvent.setup();
    render(<ChIPSeqComparePage />, { wrapper: createWrapper() });

    await user.type(screen.getByTestId("chipseq-compare-paste-input"), "MALAT1");
    await user.click(screen.getByTestId("chipseq-compare-resolve-button"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Run compare" })).not.toBeDisabled();
    });

    await user.click(screen.getByRole("button", { name: "Run compare" }));

    await waitFor(() => {
      expect(screen.getByTestId("chipseq-compare-summary-cards")).toBeVisible();
      expect(screen.getByTestId("chipseq-compare-results")).toHaveTextContent(
        "No gene returned a valid heatmap matrix for the current selection.",
      );
    });

    expect(screen.getByTestId("chipseq-compare-card-gene-coverage")).toHaveTextContent(
      "0/1",
    );
    expect(screen.getByTestId("chipseq-compare-card-failed-genes")).toHaveTextContent(
      "1",
    );
    expect(screen.getByTestId("chipseq-compare-card-matrix-coverage")).toHaveTextContent(
      "0.0%",
    );
    expect(screen.getByTestId("chipseq-compare-card-query-time")).toHaveTextContent(
      "22ms",
    );
    expect(screen.getByText("Some genes could not be rendered")).toBeVisible();
    expect(screen.getByText("MALAT1")).toBeVisible();
    expect(
      screen.getByTestId("chipseq-compare-export-button"),
    ).toBeDisabled();
  });
});
