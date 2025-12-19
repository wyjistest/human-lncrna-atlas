/**
 * Clustered Heatmap Component
 *
 * Combines a heatmap with row and column dendrograms showing hierarchical clustering.
 * Layout: [Row Dendrogram] [Heatmap]
 *                          [Col Dendrogram]
 *
 * @module components/visualization/ClusteredHeatmap
 */

import { useMemo } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { DendrogramSVG, type DendrogramData } from './DendrogramSVG'
import type { HeatmapParams } from '@/types/echarts'

/**
 * Props for ClusteredHeatmap component
 */
export interface ClusteredHeatmapProps {
  /** Heatmap data matrix (rows x cols) */
  data: number[][]
  /** Row labels (length = rows) */
  rowLabels: string[]
  /** Column labels (length = cols) */
  colLabels: string[]
  /** Optional dendrogram data for hierarchical clustering */
  dendrogramData?: {
    /** Row dendrogram */
    row?: DendrogramData
    /** Column dendrogram */
    col?: DendrogramData
  }
  /** Callback when a cell is clicked */
  onCellClick?: (row: number, col: number, value: number) => void
  /** Heatmap width (excluding dendrograms) */
  heatmapWidth?: number
  /** Heatmap height (excluding dendrograms) */
  heatmapHeight?: number
  /** Dendrogram width/height */
  dendrogramSize?: number
  /** Color scale min value (default: auto) */
  colorMin?: number
  /** Color scale max value (default: auto) */
  colorMax?: number
  /** Show values in cells */
  showValues?: boolean
}

/**
 * ClusteredHeatmap Component
 *
 * Renders a heatmap with optional row and column dendrograms.
 * Dendrograms show hierarchical clustering structure.
 *
 * @example
 * <ClusteredHeatmap
 *   data={[[1, 2, 3], [4, 5, 6]]}
 *   rowLabels={['Gene1', 'Gene2']}
 *   colLabels={['Sample1', 'Sample2', 'Sample3']}
 *   dendrogramData={{
 *     row: rowDendrogram,
 *     col: colDendrogram
 *   }}
 *   onCellClick={(row, col, value) => console.log(row, col, value)}
 * />
 */
export function ClusteredHeatmap({
  data,
  rowLabels,
  colLabels,
  dendrogramData,
  onCellClick,
  heatmapWidth = 600,
  heatmapHeight = 400,
  dendrogramSize = 80,
  colorMin,
  colorMax,
  showValues = false,
}: ClusteredHeatmapProps) {
  // Calculate auto min/max if not provided
  const [dataMin, dataMax] = useMemo(() => {
    if (colorMin !== undefined && colorMax !== undefined) {
      return [colorMin, colorMax]
    }
    const flatData = data.flat()
    return [Math.min(...flatData), Math.max(...flatData)]
  }, [data, colorMin, colorMax])

  // Transform data to ECharts format
  const heatmapData = useMemo(() => {
    return data.flatMap((row, rowIdx) =>
      row.map((value, colIdx) => [colIdx, rowIdx, value])
    )
  }, [data])

  // ECharts heatmap option
  const heatmapOption: EChartsOption = useMemo(() => {
    return {
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const [colIdx, rowIdx, value] = p.value
          return `
            <strong>${escapeHtml(rowLabels[rowIdx])} × ${escapeHtml(colLabels[colIdx])}</strong><br/>
            Value: <strong>${(value ?? 0).toFixed(2)}</strong>
          `
        },
      },
      grid: {
        left: 100,
        right: 20,
        top: 80,
        bottom: 20,
      },
      xAxis: {
        type: 'category',
        data: colLabels,
        splitArea: {
          show: true,
        },
        axisLabel: {
          rotate: 45,
          interval: 0,
        },
      },
      yAxis: {
        type: 'category',
        data: rowLabels,
        splitArea: {
          show: true,
        },
      },
      visualMap: {
        min: dataMin,
        max: dataMax,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        top: 10,
        inRange: {
          color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
        },
      },
      series: [
        {
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: showValues,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              return (p.value[2] ?? 0).toFixed(1)
            },
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    }
  }, [heatmapData, rowLabels, colLabels, dataMin, dataMax, showValues])

  // Handle cell click
  const handleChartClick = (params: unknown) => {
    const p = params as HeatmapParams & { componentType?: string }
    if (p.componentType === 'series' && onCellClick) {
      const [colIdx, rowIdx, value] = p.value
      onCellClick(rowIdx, colIdx, value ?? 0)
    }
  }

  const hasRowDendrogram = dendrogramData?.row
  const hasColDendrogram = dendrogramData?.col

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: hasRowDendrogram
          ? `${dendrogramSize}px ${heatmapWidth}px`
          : `${heatmapWidth}px`,
        gridTemplateRows: hasColDendrogram
          ? `${heatmapHeight}px ${dendrogramSize}px`
          : `${heatmapHeight}px`,
        gap: 0,
      }}
      data-testid="clustered-heatmap"
    >
      {/* Row Dendrogram (left) */}
      {hasRowDendrogram && (
        <div
          style={{
            gridColumn: 1,
            gridRow: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <DendrogramSVG
            data={dendrogramData.row!}
            orientation="left"
            width={dendrogramSize}
            height={heatmapHeight}
            color="#666"
            lineWidth={1.5}
          />
        </div>
      )}

      {/* Heatmap */}
      <div
        style={{
          gridColumn: hasRowDendrogram ? 2 : 1,
          gridRow: 1,
        }}
      >
        <ReactECharts
          option={heatmapOption}
          style={{ width: heatmapWidth, height: heatmapHeight }}
          onEvents={{
            click: handleChartClick,
          }}
        />
      </div>

      {/* Column Dendrogram (bottom) */}
      {hasColDendrogram && (
        <div
          style={{
            gridColumn: hasRowDendrogram ? 2 : 1,
            gridRow: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <DendrogramSVG
            data={dendrogramData.col!}
            orientation="top"
            width={heatmapWidth}
            height={dendrogramSize}
            color="#666"
            lineWidth={1.5}
          />
        </div>
      )}
    </div>
  )
}

export default ClusteredHeatmap
