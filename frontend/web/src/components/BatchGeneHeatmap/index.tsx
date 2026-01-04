/**
 * BatchGeneHeatmapViewer Component
 * Complete integration example for batch gene heatmap visualization
 * Phase 2.10 - Batch Gene Heatmap Feature
 */

import { useState, useCallback, useMemo } from 'react'
import { Card, Space, Button, Select, Alert, message } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GeneSelector from './GeneSelector'
import BatchHeatmapMatrix from './BatchHeatmapMatrix'
import useBatchGeneHeatmap, { useBatchGeneHeatmapStatus } from '@/hooks/useBatchGeneHeatmap'
import { getCommonMarks } from '@/config/markConfigs'
import type { HeatmapMetricType, MarkType } from '@/types/chipseq'
import { CELL_TYPE_CONFIGS } from '@/config/cellTypeConfigs'

interface GeneInfo {
  gene_id: number
  gene_name: string
  chromosome?: string
  start?: number
  end?: number
}

interface BatchGeneHeatmapViewerProps {
  /** Available genes to select from */
  availableGenes?: GeneInfo[]
  /** Initial selected genes */
  initialGenes?: GeneInfo[]
  /** Loading state for available genes */
  loadingGenes?: boolean
  /** Callback when genes are selected */
  onGenesChange?: (genes: GeneInfo[]) => void
}

/**
 * BatchGeneHeatmapViewer Component
 *
 * Complete integration component for batch gene heatmap visualization.
 * Allows users to:
 * 1. Select multiple genes
 * 2. Configure marks and cell types
 * 3. Choose metric
 * 4. View and interact with large-scale heatmap
 * 5. Export data
 *
 * @example
 * ```tsx
 * <BatchGeneHeatmapViewer
 *   availableGenes={genesList}
 *   initialGenes={[]}
 *   onGenesChange={handleGenesChange}
 * />
 * ```
 */
export function BatchGeneHeatmapViewer({
  availableGenes = [],
  initialGenes = [],
  loadingGenes = false,
  onGenesChange,
}: BatchGeneHeatmapViewerProps) {
  const { t } = useTranslation('genes')

  // UI state
  const [selectedGenes, setSelectedGenes] = useState<GeneInfo[]>(initialGenes)
  const [selectedMarks, setSelectedMarks] = useState<MarkType[]>(getCommonMarks().slice(0, 6))
  const [selectedCellTypes, setSelectedCellTypes] = useState<string[]>(
    Object.keys(CELL_TYPE_CONFIGS).slice(0, 8)
  )
  const [metric, setMetric] = useState<HeatmapMetricType>('median_fold_enrichment')
  const [flanking, setFlanking] = useState(10000)

  // Fetch batch heatmap data
  const batchHeatmapQuery = useBatchGeneHeatmap(
    selectedGenes,
    selectedMarks,
    selectedCellTypes,
    metric,
    flanking,
    {
      enabled: selectedGenes.length > 0 && selectedMarks.length > 0 && selectedCellTypes.length > 0,
    }
  )

  const queryStatus = useBatchGeneHeatmapStatus(batchHeatmapQuery)

  // Handle gene selection change
  const handleGenesChange = useCallback(
    (genes: GeneInfo[]) => {
      setSelectedGenes(genes)
      onGenesChange?.(genes)
    },
    [onGenesChange]
  )

  // Export handler - batch export API has been removed, show info message
  const handleExport = useCallback(() => {
    if (selectedGenes.length === 0) {
      message.warning(t('batchGeneHeatmap.selectGenesFirst', 'Please select genes first'))
      return
    }

    message.info(t('batchGeneHeatmap.exportNotAvailable', 'Batch export feature is currently being refactored'))
  }, [selectedGenes, t])

  // Mark options
  const markOptions = useMemo(
    () => [
      { label: 'H3K4me3', value: 'H3K4me3' as MarkType },
      { label: 'H3K4me1', value: 'H3K4me1' as MarkType },
      { label: 'H3K27ac', value: 'H3K27ac' as MarkType },
      { label: 'H3K27me3', value: 'H3K27me3' as MarkType },
      { label: 'H3K36me3', value: 'H3K36me3' as MarkType },
      { label: 'H3K9me3', value: 'H3K9me3' as MarkType },
      { label: 'H3K9ac', value: 'H3K9ac' as MarkType },
      { label: 'H3K79me2', value: 'H3K79me2' as MarkType },
    ],
    []
  )

  // Cell type options
  const cellTypeOptions = useMemo(
    () => Object.entries(CELL_TYPE_CONFIGS).map(([key, config]) => ({
      label: config.label,
      value: key,
    })),
    []
  )

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* Gene Selection Card */}
      <Card
        title={t('batchGeneHeatmap.selectGenes', 'Select Genes')}
        size="small"
        style={{ backgroundColor: '#fafafa' }}
      >
        <GeneSelector
          value={selectedGenes}
          onChange={handleGenesChange}
          availableGenes={availableGenes}
          loading={loadingGenes}
          maxCount={10}
          showQuickAdd
        />
      </Card>

      {/* Configuration Card */}
      {selectedGenes.length > 0 && (
        <Card
          title={t('batchGeneHeatmap.configuration', 'Configuration')}
          size="small"
          style={{ backgroundColor: '#fafafa' }}
        >
          <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
            {/* Marks Selection */}
            <div>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                {t('batchGeneHeatmap.selectMarks', 'Select Marks (X-axis)')}
              </label>
              <Select
                mode="multiple"
                value={selectedMarks}
                onChange={(value) => setSelectedMarks(value as MarkType[])}
                options={markOptions}
                style={{ width: '100%' }}
                maxCount={8}
                placeholder={t('batchGeneHeatmap.selectMarksPlaceholder', 'Choose marks to display')}
              />
            </div>

            {/* Cell Types Selection */}
            <div>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                {t('batchGeneHeatmap.selectCellTypes', 'Select Cell Types (Y-axis)')}
              </label>
              <Select
                mode="multiple"
                value={selectedCellTypes}
                onChange={(value) => setSelectedCellTypes(value)}
                options={cellTypeOptions}
                style={{ width: '100%' }}
                maxCount={12}
                placeholder={t('batchGeneHeatmap.selectCellTypesPlaceholder', 'Choose cell types')}
              />
            </div>

            {/* Flanking Region */}
            <div>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                {t('batchGeneHeatmap.flankingRegion', 'Flanking Region (bp)')}
              </label>
              <Select
                value={flanking}
                onChange={(value) => setFlanking(value)}
                options={[
                  { label: '5 kb', value: 5000 },
                  { label: '10 kb', value: 10000 },
                  { label: '20 kb', value: 20000 },
                  { label: '50 kb', value: 50000 },
                  { label: '100 kb', value: 100000 },
                ]}
                style={{ width: 120 }}
              />
            </div>
          </Space>
        </Card>
      )}

      {/* Status Alerts */}
      {selectedGenes.length > 0 && (
        <>
          {queryStatus.failedCount > 0 && (
            <Alert
              type="error"
              message={t('batchGeneHeatmap.loadError', 'Failed to load data')}
              description={`Failed genes: ${queryStatus.failedGenes.join(', ')}`}
              showIcon
              closable
            />
          )}

          {queryStatus.loadingCount > 0 && (
            <Alert
              type="info"
              message={t('batchGeneHeatmap.loading', 'Loading data')}
              description={`Fetching data for: ${queryStatus.loadingGenes.join(', ')}`}
              showIcon
            />
          )}

          {queryStatus.anySuccess && (
            <Alert
              type="success"
              message={t('batchGeneHeatmap.loadSuccess', 'Data loaded successfully')}
              description={`${queryStatus.successCount} of ${selectedGenes.length} genes loaded`}
              showIcon
              closable
            />
          )}
        </>
      )}

      {/* Heatmap Display */}
      {selectedGenes.length > 0 && (
        <Card
          title={t('batchGeneHeatmap.heatmapVisualization', 'Heatmap Visualization')}
          size="small"
          extra={
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleExport}
              disabled={batchHeatmapQuery.isLoading || batchHeatmapQuery.data.length === 0}
            >
              {t('common.export', 'Export')}
            </Button>
          }
        >
          <BatchHeatmapMatrix
            data={batchHeatmapQuery.data}
            metric={metric}
            onMetricChange={setMetric}
            loading={batchHeatmapQuery.isLoading}
            error={batchHeatmapQuery.error}
            // Pass undefined to avoid unnecessary ECharts click listener binding
            // Can be replaced with a handler to open details panel when implemented
            onCellClick={undefined}
          />
        </Card>
      )}
    </Space>
  )
}

export default BatchGeneHeatmapViewer
