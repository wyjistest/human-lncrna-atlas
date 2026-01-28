import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import type { EChartsInstance } from 'echarts-for-react'

import { exportChartToSVG } from './chart-export'
import echarts from './echarts'

vi.mock('./echarts', () => ({
  default: {
    init: vi.fn(),
  },
}))

describe('exportChartToSVG', () => {
  const originalClick = HTMLAnchorElement.prototype.click

  beforeEach(() => {
    vi.clearAllMocks()
    HTMLAnchorElement.prototype.click = vi.fn()
  })

  afterEach(() => {
    HTMLAnchorElement.prototype.click = originalClick
  })

  it('returns false when chart instance is missing', () => {
    expect(exportChartToSVG(null, 'heatmap')).toBe(false)
  })

  it('renders svg via svg renderer and triggers download', () => {
    const mockSvgInstance = {
      setOption: vi.fn(),
      getDataURL: vi.fn(() => 'data:image/svg+xml;base64,PHN2Zy8+'),
      dispose: vi.fn(),
    }

    const initSpy = echarts.init as unknown as ReturnType<typeof vi.fn>
    initSpy.mockReturnValue(mockSvgInstance)

    const chartInstance = {
      getOption: vi.fn(() => ({ series: [] })),
      getWidth: vi.fn(() => 640),
      getHeight: vi.fn(() => 480),
    } as unknown as EChartsInstance

    const result = exportChartToSVG(chartInstance, 'heatmap-matrix')

    expect(result).toBe(true)
    expect(initSpy).toHaveBeenCalled()
    expect(mockSvgInstance.getDataURL).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'svg' })
    )
  })
})
