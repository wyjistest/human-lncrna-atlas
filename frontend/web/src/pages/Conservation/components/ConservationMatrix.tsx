/**
 * ConservationMatrix Component
 * ECharts heatmap visualization for cross-species conservation analysis
 */

import { useEffect, useRef, useMemo } from 'react'
import { escapeHtml } from '@/utils/escapeHtml'
import { Card, Empty, Spin } from 'antd'
import { useTranslation } from 'react-i18next'
import echarts from '@/utils/echarts'
import type { ECOption } from '@/utils/echarts'
import type { ConservationMatrixData } from '@/types/conservationPage'
import type { HeatmapParams } from '@/types/echarts'

interface ConservationMatrixProps {
  /** Matrix data from API */
  data: ConservationMatrixData | null
  /** Loading state */
  loading?: boolean
  /** Card title */
  title?: string
  /** Chart height */
  height?: number
  /** Callback when clicking a cell */
  onCellClick?: (speciesX: number, speciesY: number, value: number) => void
}

/**
 * Color palette for heatmap (color-blind safe)
 * Uses Tol Sequential color scheme
 */
const HEATMAP_COLORS = [
  '#FFFFE5',
  '#F7FCB9',
  '#D9F0A3',
  '#ADDD8E',
  '#78C679',
  '#41AB5D',
  '#238443',
  '#006837',
  '#004529'
]

/**
 * Conservation matrix heatmap component
 */
export function ConservationMatrix({
  data,
  loading = false,
  title,
  height = 400,
  onCellClick
}: ConservationMatrixProps) {
  const { t } = useTranslation('conservation')
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<ReturnType<typeof echarts.init> | null>(null)

  // Transform matrix data to ECharts format
  const chartData = useMemo(() => {
    if (!data || !data.matrix || data.matrix.length === 0) return null

    const heatmapData: Array<[number, number, number]> = []

    // Convert 2D matrix to [x, y, value] format
    for (let i = 0; i < data.matrix.length; i++) {
      for (let j = 0; j < data.matrix[i].length; j++) {
        heatmapData.push([j, i, data.matrix[i][j]])
      }
    }

    return {
      speciesIds: data.species,
      speciesNames: data.species_names,
      heatmapData,
      maxValue: data.max_value,
      minValue: data.min_value
    }
  }, [data])

  // Initialize and update chart
  useEffect(() => {
    if (!chartRef.current || !chartData) return

    // Initialize chart if not exists
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)
    }

    const { speciesIds, speciesNames, heatmapData, maxValue, minValue } = chartData

    const option: ECOption = {
      title: {
        text: title || t('matrix.title', 'Conservation Matrix'),
        left: 'center',
        textStyle: {
          fontSize: 16,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as HeatmapParams
          const value = p.value
          const xName = speciesNames[value[0]]
          const yName = speciesNames[value[1]]
          const count = value[2] ?? 0
          return `
            <strong>${escapeHtml(xName)} - ${escapeHtml(yName)}</strong><br/>
            ${t('matrix.sharedRegulations', 'Shared Regulations')}: <strong>${count.toLocaleString()}</strong>
          `
        }
      },
      grid: {
        top: 60,
        left: 100,
        right: 100,
        bottom: 80,
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: speciesNames,
        splitArea: {
          show: true
        },
        axisLabel: {
          interval: 0,
          rotate: 45,
          fontSize: 12
        },
        axisTick: {
          alignWithLabel: true
        }
      },
      yAxis: {
        type: 'category',
        data: speciesNames,
        splitArea: {
          show: true
        },
        axisLabel: {
          interval: 0,
          fontSize: 12
        }
      },
      visualMap: {
        min: minValue,
        max: maxValue,
        calculable: true,
        orient: 'vertical',
        right: 10,
        top: 'center',
        inRange: {
          color: HEATMAP_COLORS
        },
        text: [
          t('matrix.high', 'High'),
          t('matrix.low', 'Low')
        ],
        textStyle: {
          fontSize: 11
        }
      },
      series: [
        {
          name: t('matrix.sharedRegulations', 'Shared Regulations'),
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true,
            formatter: (params: unknown) => {
              const p = params as HeatmapParams
              const value = p.value[2] ?? 0
              // Format large numbers with K suffix
              if (value >= 1000) {
                return `${(value / 1000).toFixed(1)}K`
              }
              return value.toLocaleString()
            },
            fontSize: 11,
            color: '#000'
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2
          }
        }
      ]
    }

    chartInstance.current.setOption(option, true)

    // Add click event listener
    // IMPORTANT: remove previous handler to avoid duplicate callbacks & memory leaks
    chartInstance.current.off('click')
    if (onCellClick) {
      const handleClick = (params: unknown) => {
        const p = params as HeatmapParams & { componentType?: string; seriesType?: string }
        if (p.componentType === 'series' && p.seriesType === 'heatmap') {
          const [x, y, value] = p.value
          const speciesX = speciesIds[x]
          const speciesY = speciesIds[y]
          if (speciesX !== undefined && speciesY !== undefined) {
            onCellClick(speciesX, speciesY, value ?? 0)
          }
        }
      }
      chartInstance.current.on('click', handleClick)
    }
  }, [chartData, title, t, onCellClick])

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize()
    }

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose()
        chartInstance.current = null
      }
    }
  }, [])

  // Show loading state
  if (loading) {
    return (
      <Card>
        <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin size="large" />
        </div>
      </Card>
    )
  }

  // Show empty state
  if (!chartData) {
    return (
      <Card title={title || t('matrix.title', 'Conservation Matrix')}>
        <Empty description={t('matrix.noData', 'No data available. Please select species.')} />
      </Card>
    )
  }

  return (
    <Card
      title={null}
      styles={{ body: { padding: 16 } }}
    >
      <div ref={chartRef} style={{ width: '100%', height }} />
    </Card>
  )
}

export default ConservationMatrix
