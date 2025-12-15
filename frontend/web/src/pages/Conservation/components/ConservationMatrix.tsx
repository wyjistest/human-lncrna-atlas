/**
 * ConservationMatrix Component
 * ECharts heatmap visualization for cross-species conservation analysis
 */

import { useEffect, useRef, useMemo } from 'react'
import { Card, Empty, Spin } from 'antd'
import { useTranslation } from 'react-i18next'
import * as echarts from 'echarts'
import type { EChartsOption, HeatmapSeriesOption } from 'echarts'
import type { ConservationMatrixData } from '@/types/conservationPage'

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
  const chartInstance = useRef<echarts.ECharts | null>(null)

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

    const { speciesNames, heatmapData, maxValue, minValue } = chartData

    const option: EChartsOption = {
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
        formatter: (params: any) => {
          const { value } = params
          const xName = speciesNames[value[0]]
          const yName = speciesNames[value[1]]
          const count = value[2]
          return `
            <strong>${xName} - ${yName}</strong><br/>
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
            formatter: (params: any) => {
              const value = params.value[2]
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
        } as HeatmapSeriesOption
      ]
    }

    chartInstance.current.setOption(option, true)

    // Add click event listener
    if (onCellClick) {
      chartInstance.current.on('click', (params: any) => {
        if (params.componentType === 'series' && params.seriesType === 'heatmap') {
          const [x, y, value] = params.value as [number, number, number]
          onCellClick(x, y, value)
        }
      })
    }

    // Cleanup on unmount
    return () => {
      // Don't destroy here, just clear option to avoid memory issues
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
      bodyStyle={{ padding: 16 }}
    >
      <div ref={chartRef} style={{ width: '100%', height }} />
    </Card>
  )
}

export default ConservationMatrix
