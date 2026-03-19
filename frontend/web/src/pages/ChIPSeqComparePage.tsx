import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Empty,
  Input,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { ExperimentOutlined, HomeOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { genesApi } from "@/api/genes";
import BatchHeatmapMatrix from "@/components/BatchGeneHeatmap/BatchHeatmapMatrix";
import { CELL_TYPE_CONFIGS, getAllCellTypes } from "@/config/cellTypeConfigs";
import {
  getAllMarkTypes,
  getCommonMarks,
  MARK_CONFIGS,
} from "@/config/markConfigs";
import useBatchGeneHeatmap from "@/hooks/useBatchGeneHeatmap";
import type { HeatmapMetricType, MarkType } from "@/types/chipseq";
import {
  appendCompareGenes,
  buildCompareSignature,
  COMPARE_MAX_GENES,
  COMPARE_MAX_IDENTIFIERS,
  mapGeneListItemsToCompareGenes,
  mapGeneOptionsToCompareGenes,
  mapSelectedIdsToGenes,
  parseCompareIdentifiers,
  type CompareGene,
} from "./ChIPSeqComparePage.utils";

const { Paragraph, Text } = Typography;
const { TextArea } = Input;

const DEFAULT_MARKS = getCommonMarks().slice(0, 6);
const DEFAULT_CELL_TYPES = getAllCellTypes().slice(0, 4);
const DEFAULT_FLANKING = 10000;

interface SubmittedCompareRequest {
  genes: CompareGene[];
  marks: MarkType[];
  cellTypes: string[];
  metric: HeatmapMetricType;
  flanking: number;
}

const FLANKING_OPTIONS = [
  { label: "5 kb", value: 5000 },
  { label: "10 kb", value: 10000 },
  { label: "20 kb", value: 20000 },
  { label: "50 kb", value: 50000 },
  { label: "100 kb", value: 100000 },
];

const METRIC_OPTIONS: Array<{ value: HeatmapMetricType; label: string }> = [
  { value: "median_fold_enrichment", label: "Fold Enrichment" },
  { value: "peak_count", label: "Peak Count" },
  { value: "total_coverage_bp", label: "Coverage" },
  { value: "avg_signal", label: "Avg Signal" },
];

export default function ChIPSeqComparePage() {
  const { t } = useTranslation("globalCompare");
  const { t: tCommon, i18n } = useTranslation("common");
  const isZh = i18n.language === "zh-CN";

  const [selectedGenes, setSelectedGenes] = useState<CompareGene[]>([]);
  const [selectedMarks, setSelectedMarks] = useState<MarkType[]>(DEFAULT_MARKS);
  const [selectedCellTypes, setSelectedCellTypes] =
    useState<string[]>(DEFAULT_CELL_TYPES);
  const [metric, setMetric] = useState<HeatmapMetricType>(
    "median_fold_enrichment",
  );
  const [flanking, setFlanking] = useState(DEFAULT_FLANKING);
  const [pasteInput, setPasteInput] = useState("");
  const [missingIdentifiers, setMissingIdentifiers] = useState<string[]>([]);
  const [geneOptionsReady, setGeneOptionsReady] = useState(false);
  const [submittedRequest, setSubmittedRequest] =
    useState<SubmittedCompareRequest | null>(null);

  const geneOptionsQuery = useQuery({
    queryKey: ["gene-options", "chipseq-compare", 1],
    queryFn: ({ signal }) => genesApi.getOptions({ species_id: 1 }, signal),
    enabled: geneOptionsReady,
    staleTime: 10 * 60 * 1000,
  });

  const availableGenes = useMemo(
    () => mapGeneOptionsToCompareGenes(geneOptionsQuery.data?.genes ?? []),
    [geneOptionsQuery.data],
  );

  const geneSelectOptions = useMemo(
    () =>
      availableGenes.map((gene) => ({
        value: gene.gene_id,
        label: `${gene.gene_name}${gene.gene_ensembl_id ? ` · ${gene.gene_ensembl_id}` : ""}`,
        searchValue: `${gene.gene_name} ${gene.gene_ensembl_id ?? ""} ${gene.gene_id}`,
      })),
    [availableGenes],
  );

  const markOptions = useMemo(
    () =>
      getAllMarkTypes().map((mark) => ({
        value: mark,
        label: MARK_CONFIGS[mark].displayName,
      })),
    [],
  );

  const cellTypeOptions = useMemo(
    () =>
      getAllCellTypes().map((cellType) => ({
        value: cellType,
        label: isZh
          ? CELL_TYPE_CONFIGS[cellType].labelZh
          : CELL_TYPE_CONFIGS[cellType].label,
      })),
    [isZh],
  );

  const resolveGenesMutation = useMutation({
    mutationFn: (identifiers: string[]) =>
      genesApi.batchResolve({
        identifiers,
        species_id: 1,
      }),
    onSuccess: (response) => {
      const resolvedGenes = mapGeneListItemsToCompareGenes(response.items);

      setSelectedGenes((currentGenes) => {
        const merged = appendCompareGenes(
          currentGenes,
          resolvedGenes,
          COMPARE_MAX_GENES,
        );
        if (merged.truncatedCount > 0) {
          message.warning(
            t("input.maxGenesReached", {
              max: COMPARE_MAX_GENES,
              defaultValue: `Only the first ${COMPARE_MAX_GENES} genes are kept in v1.`,
            }),
          );
        }
        return merged.genes;
      });

      setMissingIdentifiers(response.missing);
      setPasteInput("");
    },
    onError: () => {
      message.error(tCommon("error.loadFailed", "加载失败"));
    },
  });

  const handleResolveGenes = useCallback(() => {
    const identifiers = parseCompareIdentifiers(pasteInput);
    if (identifiers.length === 0) {
      message.warning(
        t(
          "input.emptyIdentifiers",
          "Paste at least one gene_id, gene_name, or Ensembl ID.",
        ),
      );
      return;
    }
    if (identifiers.length > COMPARE_MAX_IDENTIFIERS) {
      message.error(
        t("input.tooManyIdentifiers", {
          max: COMPARE_MAX_IDENTIFIERS,
          defaultValue: `At most ${COMPARE_MAX_IDENTIFIERS} identifiers can be resolved at once.`,
        }),
      );
      return;
    }

    resolveGenesMutation.mutate(identifiers);
  }, [pasteInput, resolveGenesMutation, t]);

  const selectedGeneIds = useMemo(
    () => selectedGenes.map((gene) => gene.gene_id),
    [selectedGenes],
  );

  const handleSelectedGeneIdsChange = useCallback(
    (nextIds: number[]) => {
      setSelectedGenes(
        mapSelectedIdsToGenes(nextIds, availableGenes, selectedGenes),
      );
    },
    [availableGenes, selectedGenes],
  );

  const handleRunCompare = useCallback(() => {
    if (
      selectedGenes.length === 0 ||
      selectedMarks.length === 0 ||
      selectedCellTypes.length === 0
    ) {
      return;
    }

    setSubmittedRequest({
      genes: [...selectedGenes],
      marks: [...selectedMarks],
      cellTypes: [...selectedCellTypes],
      metric,
      flanking,
    });
  }, [flanking, metric, selectedCellTypes, selectedGenes, selectedMarks]);

  const compareQuery = useBatchGeneHeatmap(
    submittedRequest?.genes ?? [],
    submittedRequest?.marks ?? [],
    submittedRequest?.cellTypes ?? [],
    submittedRequest?.metric ?? metric,
    submittedRequest?.flanking ?? flanking,
    {
      enabled: submittedRequest !== null,
    },
  );

  const currentSignature = useMemo(
    () =>
      buildCompareSignature({
        genes: selectedGenes,
        marks: selectedMarks,
        cellTypes: selectedCellTypes,
        metric,
        flanking,
      }),
    [flanking, metric, selectedCellTypes, selectedGenes, selectedMarks],
  );

  const submittedSignature = useMemo(
    () =>
      submittedRequest
        ? buildCompareSignature({
            genes: submittedRequest.genes,
            marks: submittedRequest.marks,
            cellTypes: submittedRequest.cellTypes,
            metric: submittedRequest.metric,
            flanking: submittedRequest.flanking,
          })
        : null,
    [submittedRequest],
  );

  const hasPendingChanges =
    submittedSignature !== null && submittedSignature !== currentSignature;
  const compareDisabled =
    selectedGenes.length === 0 ||
    selectedMarks.length === 0 ||
    selectedCellTypes.length === 0 ||
    resolveGenesMutation.isPending;

  return (
    <div data-testid="chipseq-compare-page" style={{ padding: "0 0 24px 0" }}>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/">
                <HomeOutlined />
              </Link>
            ),
          },
          {
            title: (
              <>
                <ExperimentOutlined style={{ marginRight: 4 }} />
                {t("title", "ChIP-seq Gene Set Compare")}
              </>
            ),
          },
        ]}
      />

      <Paragraph type="secondary" style={{ marginBottom: 24 }}>
        {t(
          "subtitle",
          "Compare a curated human gene set with real ChIP-seq heatmaps. Search genes, paste identifiers, and run a batched matrix query.",
        )}
      </Paragraph>

      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Card
          title={t("input.title", "Gene Set Input")}
          extra={<Tag color="blue">{tCommon("species.human", "Human")}</Tag>}
          data-testid="chipseq-compare-input-card"
        >
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div>
              <Text strong>
                {t("input.searchTitle", "Search and select genes")}
              </Text>
              <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                {t(
                  "input.searchDescription",
                  "Load human gene options on demand and keep up to 10 genes in compare order.",
                )}
              </Paragraph>
              <Select
                data-testid="chipseq-compare-search-select"
                mode="multiple"
                showSearch
                value={selectedGeneIds}
                options={geneSelectOptions}
                maxCount={COMPARE_MAX_GENES}
                optionFilterProp="searchValue"
                placeholder={t(
                  "input.searchPlaceholder",
                  "Search gene symbol, Ensembl ID, or gene ID",
                )}
                onOpenChange={(open) => {
                  if (open) setGeneOptionsReady(true);
                }}
                onFocus={() => setGeneOptionsReady(true)}
                onChange={(values) =>
                  handleSelectedGeneIdsChange(values as number[])
                }
                notFoundContent={
                  geneOptionsQuery.isFetching ? <Spin size="small" /> : null
                }
                style={{ width: "100%" }}
              />
            </div>

            <div>
              <Text strong>{t("input.pasteTitle", "Paste identifiers")}</Text>
              <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                {t(
                  "input.pasteDescription",
                  "Supports gene_id, gene_name, and Ensembl ID. Split with spaces, commas, semicolons, or new lines.",
                )}
              </Paragraph>
              <TextArea
                data-testid="chipseq-compare-paste-input"
                rows={4}
                value={pasteInput}
                onChange={(event) => setPasteInput(event.target.value)}
                placeholder={t(
                  "input.pastePlaceholder",
                  "Example: MALAT1 NEAT1 ENSG00000251562 17276",
                )}
              />
              <Space style={{ marginTop: 12 }} wrap>
                <Button
                  type="default"
                  loading={resolveGenesMutation.isPending}
                  onClick={handleResolveGenes}
                  data-testid="chipseq-compare-resolve-button"
                >
                  {t("input.resolveButton", "Resolve genes")}
                </Button>
                <Text type="secondary">
                  {t("input.selectionCount", {
                    count: selectedGenes.length,
                    max: COMPARE_MAX_GENES,
                    defaultValue: `${selectedGenes.length}/${COMPARE_MAX_GENES} genes selected`,
                  })}
                </Text>
              </Space>
            </div>

            {missingIdentifiers.length > 0 && (
              <Alert
                type="warning"
                showIcon
                data-testid="chipseq-compare-missing-alert"
                message={t(
                  "input.missingTitle",
                  "Some identifiers were not resolved",
                )}
                description={missingIdentifiers.join(", ")}
              />
            )}
          </Space>
        </Card>

        <Card
          title={t("config.title", "Compare Configuration")}
          data-testid="chipseq-compare-config-card"
        >
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div>
              <Text strong>{t("config.marks", "Marks")}</Text>
              <Select
                mode="multiple"
                value={selectedMarks}
                onChange={(value) => setSelectedMarks(value as MarkType[])}
                options={markOptions}
                maxCount={8}
                style={{ width: "100%", marginTop: 8 }}
                placeholder={t(
                  "config.marksPlaceholder",
                  "Select marks to compare",
                )}
              />
            </div>

            <div>
              <Text strong>{t("config.cellTypes", "Cell types")}</Text>
              <Select
                mode="multiple"
                value={selectedCellTypes}
                onChange={(value) => setSelectedCellTypes(value)}
                options={cellTypeOptions}
                maxCount={10}
                style={{ width: "100%", marginTop: 8 }}
                placeholder={t(
                  "config.cellTypesPlaceholder",
                  "Select cell types to compare",
                )}
              />
            </div>

            <Space wrap size="large">
              <div>
                <Text strong>{t("config.metric", "Metric")}</Text>
                <Select
                  value={metric}
                  options={METRIC_OPTIONS}
                  style={{ width: 200, marginTop: 8 }}
                  onChange={(value) => setMetric(value)}
                />
              </div>
              <div>
                <Text strong>{t("config.flanking", "Flanking region")}</Text>
                <Select
                  value={flanking}
                  options={FLANKING_OPTIONS}
                  style={{ width: 140, marginTop: 8 }}
                  onChange={(value) => setFlanking(value)}
                />
              </div>
            </Space>

            <Space wrap>
              <Button
                type="primary"
                onClick={handleRunCompare}
                disabled={compareDisabled}
                loading={compareQuery.isLoading}
                data-testid="chipseq-compare-run-button"
              >
                {submittedRequest
                  ? t("actions.updateCompare", "Update compare")
                  : t("actions.runCompare", "Run compare")}
              </Button>
              <Button
                onClick={() => {
                  setSelectedGenes([]);
                  setMissingIdentifiers([]);
                  setPasteInput("");
                }}
                disabled={selectedGenes.length === 0}
              >
                {tCommon("action.clear", "清除")}
              </Button>
            </Space>
          </Space>
        </Card>

        {hasPendingChanges && (
          <Alert
            type="info"
            showIcon
            data-testid="chipseq-compare-dirty-alert"
            message={t(
              "results.pendingChanges",
              "Configuration changed. Run compare again to refresh the heatmap.",
            )}
          />
        )}

        {!submittedRequest ? (
          <Card data-testid="chipseq-compare-results">
            <Empty
              description={t(
                "results.empty",
                "Choose a human gene set and run compare to render the batched heatmap.",
              )}
            />
          </Card>
        ) : (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            {compareQuery.isLoading && (
              <Alert
                type="info"
                showIcon
                message={t("results.loadingTitle", "Running batched compare")}
                description={t("results.loadingDescription", {
                  count: submittedRequest.genes.length,
                  defaultValue: `Fetching heatmap matrices for ${submittedRequest.genes.length} genes.`,
                })}
              />
            )}

            {compareQuery.error && (
              <Alert
                type="error"
                showIcon
                message={t(
                  "results.errorTitle",
                  "Failed to load compare results",
                )}
                description={compareQuery.error.message}
              />
            )}

            {!compareQuery.isLoading &&
              !compareQuery.error &&
              compareQuery.response && (
                <Alert
                  type={
                    compareQuery.failedGeneIds.length > 0
                      ? "warning"
                      : "success"
                  }
                  showIcon
                  data-testid="chipseq-compare-summary-alert"
                  message={t("results.summaryTitle", "Compare summary")}
                  description={t("results.summaryDescription", {
                    success: compareQuery.response.successful_genes,
                    total: compareQuery.response.total_genes,
                    time: compareQuery.queryTimeMs ?? 0,
                    defaultValue: `${compareQuery.response.successful_genes}/${compareQuery.response.total_genes} genes loaded in ${compareQuery.queryTimeMs ?? 0} ms.`,
                  })}
                />
              )}

            {!compareQuery.isLoading &&
              !compareQuery.error &&
              compareQuery.failedGeneNames.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message={t(
                    "results.failedGenesTitle",
                    "Some genes could not be rendered",
                  )}
                  description={compareQuery.failedGeneNames.join(", ")}
                />
              )}

            {!compareQuery.isLoading &&
              !compareQuery.error &&
              compareQuery.data.length > 0 && (
                <div data-testid="chipseq-compare-results">
                  <BatchHeatmapMatrix
                    data={compareQuery.data}
                    metric={submittedRequest.metric}
                    loading={compareQuery.isLoading}
                    error={compareQuery.error}
                    showMetricSelector={false}
                  />
                </div>
              )}

            {!compareQuery.isLoading &&
              !compareQuery.error &&
              compareQuery.response &&
              compareQuery.data.length === 0 && (
                <Card data-testid="chipseq-compare-results">
                  <Empty
                    description={t(
                      "results.noSuccessfulGenes",
                      "No gene returned a valid heatmap matrix for the current selection.",
                    )}
                  />
                </Card>
              )}
          </Space>
        )}
      </Space>
    </div>
  );
}
