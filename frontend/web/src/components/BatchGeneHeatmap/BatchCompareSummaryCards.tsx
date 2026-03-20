import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  PercentageOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Card, Space, Statistic, Typography } from "antd";
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { BatchHeatmapSummary } from "@/hooks/useBatchGeneHeatmap";

const { Text } = Typography;

interface BatchCompareSummaryCardsProps {
  summary: BatchHeatmapSummary;
}

interface SummaryCardItem {
  key: string;
  title: string;
  hint: string;
  value: number | string;
  suffix?: string;
  valueStyle: CSSProperties;
  icon: ReactNode;
}

export default function BatchCompareSummaryCards({
  summary,
}: BatchCompareSummaryCardsProps) {
  const { t } = useTranslation("globalCompare");

  const items: SummaryCardItem[] = [
    {
      key: "gene-coverage",
      title: t("results.stats.geneCoverage", "Gene coverage"),
      hint: t("results.stats.geneCoverageHint", "Loaded / requested"),
      value: `${summary.successfulGenes}/${summary.totalGenes}`,
      icon: <CheckCircleOutlined />,
      valueStyle: { color: "#1677ff" },
    },
    {
      key: "failed-genes",
      title: t("results.stats.failedGenes", "Failed genes"),
      hint: t(
        "results.stats.failedGenesHint",
        "Could not render for current selection",
      ),
      value: summary.failedGenes,
      icon: <WarningOutlined />,
      valueStyle: { color: summary.failedGenes > 0 ? "#d4380d" : "#389e0d" },
    },
    {
      key: "matrix-coverage",
      title: t("results.stats.matrixCoverage", "Matrix coverage"),
      hint: t("results.stats.matrixCoverageHint", {
        valid: summary.validCombinations,
        total: summary.totalCombinations,
        defaultValue: `${summary.validCombinations}/${summary.totalCombinations} valid combinations`,
      }),
      value: summary.coveragePercent.toFixed(1),
      suffix: "%",
      icon: <PercentageOutlined />,
      valueStyle: { color: "#08979c" },
    },
    {
      key: "query-time",
      title: t("results.stats.queryTime", "Query time"),
      hint: t("results.stats.queryTimeHint", "Server-side batch query"),
      value: summary.queryTimeMs ?? 0,
      suffix: "ms",
      icon: <ClockCircleOutlined />,
      valueStyle: { color: "#722ed1" },
    },
  ];

  return (
    <div
      data-testid="chipseq-compare-summary-cards"
      style={{
        display: "grid",
        gap: 16,
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
      }}
    >
      {items.map((item) => (
        <Card key={item.key} size="small" data-testid={`chipseq-compare-card-${item.key}`}>
          <div style={{ minHeight: 108 }}>
            <Statistic
              title={
                <Space size={6}>
                  {item.icon}
                  {item.title}
                </Space>
              }
              value={item.value}
              suffix={item.suffix}
              styles={{ content: item.valueStyle }}
            />
            <Text type="secondary">{item.hint}</Text>
          </div>
        </Card>
      ))}
    </div>
  );
}
