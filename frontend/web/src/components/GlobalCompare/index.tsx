/**
 * GlobalCompareSection Component
 * Phase 2.5 - Main container for multi-mark global comparison
 *
 * This is the main container component that integrates:
 * - Mark and cell type filters
 * - Tab navigation between different chart types
 * - Data loading and error handling
 * - Summary statistics display
 *
 * Features:
 * - Multi-select filters for marks and cell types
 * - Four visualization tabs: Radar, Bar, BoxPlot, Matrix
 * - Loading states and error handling
 * - i18n support
 */

import { useState, useMemo, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Select,
  Tabs,
  Statistic,
  Space,
  Typography,
  Tag,
} from 'antd'
import {
  RadarChartOutlined,
  BarChartOutlined,
  BoxPlotOutlined,
  HeatMapOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getMarksGroupedByCategory, getAllMarkTypes, getMarkColor, getMarkConfig } from '@/config/markConfigs'
import { getCellTypeOptions, getAllCellTypes, getCellTypeLabel } from '@/config/cellTypeConfigs'
import RadarCompareChart from './RadarCompareChart'
import GlobalBarChart from './GlobalBarChart'
import BoxPlotChart from './BoxPlotChart'
import CellLineMatrixChart from './CellLineMatrixChart'
import type { GlobalCompareFilters, GlobalCompareViewMode, CellLineMatrixMetric, BoxPlotData } from '@/types/globalCompare'
import type { MarkType } from '@/types/chipseq'

const { Title, Text } = Typography

interface GlobalCompareSectionProps {
  /** Initial filters */
  initialFilters?: Partial<GlobalCompareFilters>
  /** Default tab */
  defaultTab?: GlobalCompareViewMode
  /** Show title */
  showTitle?: boolean
}

/**
 * Generate mock data for development/demo
 * This will be replaced with real API data
 */
function generateMockData(selectedMarks: MarkType[]) {
  const marks = selectedMarks.length > 0 ? selectedMarks : getAllMarkTypes().slice(0, 7)

  return {
    marks: marks.map((markType) => ({
      mark_type: markType,
      category: getMarkConfig(markType)?.category || 'other',
      total_peaks: Math.floor(Math.random() * 500000) + 50000,
      gene_count: Math.floor(Math.random() * 15000) + 5000,
      cell_type_count: Math.floor(Math.random() * 5) + 2,
      avg_signal: Math.random() * 50 + 10,
      max_signal: Math.random() * 200 + 100,
      avg_fold_enrichment: Math.random() * 10 + 2,
      median_fold_enrichment: Math.random() * 8 + 1.5,
      total_coverage_bp: Math.floor(Math.random() * 500000000) + 100000000,
      avg_peak_width: Math.floor(Math.random() * 2000) + 500,
      position_distribution: {
        promoter: Math.random() * 30 + 10,
        exon: Math.random() * 20 + 5,
        intron: Math.random() * 30 + 15,
        intergenic: Math.random() * 20 + 10,
      },
    })),
    total_marks: marks.length,
    filters_applied: {},
    timestamp: new Date().toISOString(),
  }
}

/**
 * Generate mock box plot data
 */
function generateMockBoxPlotData(selectedMarks: MarkType[]): BoxPlotData[] {
  const marks = selectedMarks.length > 0 ? selectedMarks : getAllMarkTypes().slice(0, 7)

  return marks.map((markType) => {
    const base = Math.random() * 30 + 10
    const spread = Math.random() * 20 + 5

    return {
      mark_type: markType,
      min: Math.max(0, base - spread * 2),
      q1: base - spread * 0.5,
      median: base,
      q3: base + spread * 0.5,
      max: base + spread * 2,
      outliers: Math.random() > 0.7 ? [base + spread * 3, base + spread * 3.5] : undefined,
      n: Math.floor(Math.random() * 100000) + 10000,
    }
  })
}

/**
 * Generate mock matrix data
 */
function generateMockMatrixData(
  selectedMarks: MarkType[],
  selectedCellTypes: string[],
  metric: CellLineMatrixMetric
) {
  const marks = selectedMarks.length > 0 ? selectedMarks : getAllMarkTypes().slice(0, 7)
  const cellTypes = selectedCellTypes.length > 0 ? selectedCellTypes : getAllCellTypes()

  const matrix: Array<Array<number | null>> = []
  const data: Array<{
    cell_type: string
    mark_type: MarkType
    value: number | null
    peak_count: number
    gene_count: number
    avg_signal: number | null
    total_coverage_bp: number
  }> = []

  cellTypes.forEach((cellType) => {
    const row: Array<number | null> = []
    marks.forEach((markType) => {
      // 30% chance of no data
      const hasData = Math.random() > 0.3
      let value: number | null = null

      if (hasData) {
        switch (metric) {
          case 'peak_count':
            value = Math.floor(Math.random() * 50000) + 5000
            break
          case 'gene_count':
            value = Math.floor(Math.random() * 10000) + 2000
            break
          case 'avg_signal':
            value = Math.random() * 40 + 5
            break
          case 'avg_fold_enrichment':
            value = Math.random() * 10 + 2
            break
          case 'total_coverage_bp':
            value = Math.floor(Math.random() * 100000000) + 10000000
            break
        }
      }

      row.push(value)
      data.push({
        cell_type: cellType,
        mark_type: markType,
        value,
        peak_count: hasData ? Math.floor(Math.random() * 50000) + 5000 : 0,
        gene_count: hasData ? Math.floor(Math.random() * 10000) + 2000 : 0,
        avg_signal: hasData ? Math.random() * 40 + 5 : null,
        total_coverage_bp: hasData ? Math.floor(Math.random() * 100000000) + 10000000 : 0,
      })
    })
    matrix.push(row)
  })

  return {
    x_labels: marks,
    y_labels: cellTypes,
    metric,
    data,
    matrix,
    total_combinations: marks.length * cellTypes.length,
    valid_combinations: data.filter((d) => d.value !== null).length,
  }
}

/**
 * GlobalCompareSection Component
 *
 * Main container for global mark comparison visualization.
 *
 * @example
 * ```tsx
 * <GlobalCompareSection
 *   defaultTab="radar"
 *   showTitle={true}
 * />
 * ```
 */
export function GlobalCompareSection({
  initialFilters,
  defaultTab = 'radar',
  showTitle = true,
}: GlobalCompareSectionProps) {
  const { t, i18n } = useTranslation('globalCompare')

  // State for filters
  const [selectedMarks, setSelectedMarks] = useState<MarkType[]>(
    initialFilters?.selectedMarks || []
  )
  const [selectedCellTypes, setSelectedCellTypes] = useState<string[]>(
    initialFilters?.selectedCellTypes || []
  )
  const [activeTab, setActiveTab] = useState<GlobalCompareViewMode>(defaultTab)
  const [matrixMetric, setMatrixMetric] = useState<CellLineMatrixMetric>(
    initialFilters?.matrixMetric || 'peak_count'
  )

  // Get mark options grouped by category
  const markOptions = useMemo(() => {
    const grouped = getMarksGroupedByCategory()
    return grouped.map((group) => ({
      label: group.categoryName,
      options: group.marks.map((mark) => ({
        value: mark.value,
        label: (
          <Space>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: mark.color,
              }}
            />
            {mark.label}
          </Space>
        ),
      })),
    }))
  }, [])

  // Get cell type options
  const cellTypeOptions = useMemo(
    () => getCellTypeOptions(i18n.language),
    [i18n.language]
  )

  // Mock data query (replace with real API)
  // Using mock data until backend is ready
  const mockCompareData = useMemo(
    () => generateMockData(selectedMarks),
    [selectedMarks]
  )

  const mockBoxPlotData = useMemo(
    () => generateMockBoxPlotData(selectedMarks),
    [selectedMarks]
  )

  const mockMatrixData = useMemo(
    () => generateMockMatrixData(selectedMarks, selectedCellTypes, matrixMetric),
    [selectedMarks, selectedCellTypes, matrixMetric]
  )

  // Real API query (commented out until backend is ready)
  /*
  const {
    data: compareData,
    isLoading: isLoadingCompare,
    error: compareError,
  } = useQuery({
    queryKey: globalCompareQueryKeys.compare(selectedMarks, selectedCellTypes),
    queryFn: () =>
      globalCompareApi.getGlobalCompare({
        marks: selectedMarks.length > 0 ? selectedMarks : undefined,
        cell_types: selectedCellTypes.length > 0 ? selectedCellTypes : undefined,
      }),
    select: (response) => response.data,
  })
  */

  // Handle mark selection
  const handleMarksChange = useCallback((values: MarkType[]) => {
    setSelectedMarks(values)
  }, [])

  // Handle cell type selection
  const handleCellTypesChange = useCallback((values: string[]) => {
    setSelectedCellTypes(values)
  }, [])

  // Tab items configuration
  const tabItems = useMemo(
    () => [
      {
        key: 'radar' as GlobalCompareViewMode,
        label: (
          <span>
            <RadarChartOutlined />
            {t('tabs.radar', 'Radar Chart')}
          </span>
        ),
        children: (
          <RadarCompareChart
            data={mockCompareData.marks}
            height={480}
            shape="polygon"
          />
        ),
      },
      {
        key: 'bar' as GlobalCompareViewMode,
        label: (
          <span>
            <BarChartOutlined />
            {t('tabs.bar', 'Bar Chart')}
          </span>
        ),
        children: (
          <GlobalBarChart
            data={mockCompareData.marks}
            height={420}
            showMetricSelector
          />
        ),
      },
      {
        key: 'boxplot' as GlobalCompareViewMode,
        label: (
          <span>
            <BoxPlotOutlined />
            {t('tabs.boxplot', 'Box Plot')}
          </span>
        ),
        children: (
          <BoxPlotChart
            data={mockBoxPlotData}
            height={420}
            yAxisLabel={t('charts.boxplot.yAxis', 'Signal Value')}
          />
        ),
      },
      {
        key: 'matrix' as GlobalCompareViewMode,
        label: (
          <span>
            <HeatMapOutlined />
            {t('tabs.matrix', 'Cell Matrix')}
          </span>
        ),
        children: (
          <CellLineMatrixChart
            data={mockMatrixData}
            metric={matrixMetric}
            onMetricChange={setMatrixMetric}
            showMetricSelector
          />
        ),
      },
    ],
    [mockCompareData, mockBoxPlotData, mockMatrixData, matrixMetric, t]
  )

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Title */}
      {showTitle && (
        <Title level={3}>
          {t('title', 'ChIP-seq Global Mark Comparison')}
        </Title>
      )}

      {/* Filters Card */}
      <Card size="small" title={<><FilterOutlined /> {t('filters.title', 'Filters')}</>}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Text type="secondary">{t('filters.marks', 'Select Marks')}</Text>
              <Select
                mode="multiple"
                placeholder={t('filters.marksPlaceholder', 'All marks (click to filter)')}
                value={selectedMarks}
                onChange={handleMarksChange}
                options={markOptions}
                style={{ width: '100%' }}
                maxTagCount={4}
                maxTagPlaceholder={(omittedValues) =>
                  `+${omittedValues.length} ${t('filters.more', 'more')}`
                }
                allowClear
                showSearch
                filterOption={(input, option) =>
                  String(option?.label || '')
                    .toLowerCase()
                    .includes(input.toLowerCase())
                }
              />
            </Space>
          </Col>
          <Col xs={24} md={12}>
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Text type="secondary">{t('filters.cellTypes', 'Select Cell Types')}</Text>
              <Select
                mode="multiple"
                placeholder={t('filters.cellTypesPlaceholder', 'All cell types (click to filter)')}
                value={selectedCellTypes}
                onChange={handleCellTypesChange}
                options={cellTypeOptions}
                style={{ width: '100%' }}
                maxTagCount={3}
                maxTagPlaceholder={(omittedValues) =>
                  `+${omittedValues.length} ${t('filters.more', 'more')}`
                }
                allowClear
              />
            </Space>
          </Col>
        </Row>

        {/* Active Filters Display */}
        {(selectedMarks.length > 0 || selectedCellTypes.length > 0) && (
          <Row style={{ marginTop: 12 }}>
            <Col span={24}>
              <Space wrap size={[4, 4]}>
                <Text type="secondary">{t('filters.active', 'Active filters')}:</Text>
                {selectedMarks.map((mark) => (
                  <Tag
                    key={mark}
                    color={getMarkColor(mark)}
                    closable
                    onClose={() => setSelectedMarks((prev) => prev.filter((m) => m !== mark))}
                  >
                    {getMarkConfig(mark)?.shortName || mark}
                  </Tag>
                ))}
                {selectedCellTypes.map((cellType) => (
                  <Tag
                    key={cellType}
                    closable
                    onClose={() =>
                      setSelectedCellTypes((prev) => prev.filter((c) => c !== cellType))
                    }
                  >
                    {getCellTypeLabel(cellType, i18n.language)}
                  </Tag>
                ))}
              </Space>
            </Col>
          </Row>
        )}
      </Card>

      {/* Summary Statistics */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('stats.totalMarks', 'Marks')}
              value={mockCompareData.marks.length}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('stats.totalPeaks', 'Total Peaks')}
              value={mockCompareData.marks.reduce((sum, m) => sum + m.total_peaks, 0)}
              formatter={(value) => {
                const num = Number(value)
                if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
                if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
                return num.toLocaleString()
              }}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('stats.totalGenes', 'Total Genes')}
              value={Math.max(...mockCompareData.marks.map((m) => m.gene_count))}
              formatter={(value) => {
                const num = Number(value)
                if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
                return num.toLocaleString()
              }}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title={t('stats.cellTypes', 'Cell Types')}
              value={Math.max(...mockCompareData.marks.map((m) => m.cell_type_count))}
              valueStyle={{ color: '#eb2f96' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts Tabs */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as GlobalCompareViewMode)}
          items={tabItems}
          size="large"
        />
      </Card>
    </Space>
  )
}

export default GlobalCompareSection
