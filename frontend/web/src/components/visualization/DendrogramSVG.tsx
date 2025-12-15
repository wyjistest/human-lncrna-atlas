/**
 * Dendrogram SVG Component
 *
 * Renders hierarchical clustering tree using SVG paths.
 * Supports four orientations: left, top, right, bottom.
 *
 * @module components/visualization/DendrogramSVG
 */

import { useMemo } from 'react'

/**
 * Dendrogram data structure from scipy.cluster.hierarchy.dendrogram
 */
export interface DendrogramData {
  /** X coordinates of dendrogram lines (shape: [n, 4]) */
  icoord: number[][]
  /** Y coordinates (distance/height) of dendrogram lines (shape: [n, 4]) */
  dcoord: number[][]
  /** Leaf node indices in dendrogram order */
  leaves: number[]
}

export interface DendrogramSVGProps {
  /** Dendrogram data from clustering algorithm */
  data: DendrogramData
  /** Orientation of the dendrogram */
  orientation: 'left' | 'top' | 'right' | 'bottom'
  /** SVG width */
  width: number
  /** SVG height */
  height: number
  /** Line color */
  color?: string
  /** Line width */
  lineWidth?: number
  /** Margin for padding */
  margin?: { top: number; right: number; bottom: number; left: number }
}

/**
 * DendrogramSVG Component
 *
 * Renders a dendrogram (hierarchical clustering tree) using SVG.
 * Automatically scales coordinates to fit the container.
 *
 * @example
 * <DendrogramSVG
 *   data={{
 *     icoord: [[5, 5, 15, 15], [25, 25, 35, 35]],
 *     dcoord: [[0, 10, 10, 0], [0, 20, 20, 0]],
 *     leaves: [0, 1, 2, 3]
 *   }}
 *   orientation="left"
 *   width={100}
 *   height={400}
 * />
 */
export function DendrogramSVG({
  data,
  orientation,
  width,
  height,
  color = '#666',
  lineWidth = 1.5,
  margin = { top: 5, right: 5, bottom: 5, left: 5 },
}: DendrogramSVGProps) {
  // Calculate SVG paths
  const paths = useMemo(() => {
    if (!data || !data.icoord || !data.dcoord) {
      return []
    }

    const { icoord, dcoord } = data

    // Find coordinate ranges for scaling
    const icoordFlat = icoord.flat()
    const dcoordFlat = dcoord.flat()

    const iMin = Math.min(...icoordFlat)
    const iMax = Math.max(...icoordFlat)
    const dMin = Math.min(...dcoordFlat)
    const dMax = Math.max(...dcoordFlat)

    // Calculate usable dimensions
    const usableWidth = width - margin.left - margin.right
    const usableHeight = height - margin.top - margin.bottom

    // Scale functions
    const scaleI = (val: number) => {
      if (iMax === iMin) return usableWidth / 2
      return ((val - iMin) / (iMax - iMin)) * usableWidth
    }

    const scaleD = (val: number) => {
      if (dMax === dMin) return usableHeight / 2
      return ((val - dMin) / (dMax - dMin)) * usableHeight
    }

    // Transform coordinates based on orientation
    const transformCoords = (i: number, d: number): [number, number] => {
      const scaledI = scaleI(i)
      const scaledD = scaleD(d)

      switch (orientation) {
        case 'left':
          // Dendrogram on left, labels on right
          return [margin.left + (usableWidth - scaledD), margin.top + scaledI]
        case 'top':
          // Dendrogram on top, labels on bottom
          return [margin.left + scaledI, margin.top + (usableHeight - scaledD)]
        case 'right':
          // Dendrogram on right, labels on left
          return [margin.left + scaledD, margin.top + scaledI]
        case 'bottom':
          // Dendrogram on bottom, labels on top
          return [margin.left + scaledI, margin.top + scaledD]
        default:
          return [margin.left + scaledD, margin.top + scaledI]
      }
    }

    // Generate SVG paths
    return icoord.map((icoordLine, idx) => {
      const dcoordLine = dcoord[idx]

      // Each line has 4 points forming a U-shape or inverted-U
      const [i0, i1, i2, i3] = icoordLine
      const [d0, d1, d2, d3] = dcoordLine

      const [x0, y0] = transformCoords(i0, d0)
      const [x1, y1] = transformCoords(i1, d1)
      const [x2, y2] = transformCoords(i2, d2)
      const [x3, y3] = transformCoords(i3, d3)

      // Create path: M(x0,y0) L(x1,y1) L(x2,y2) L(x3,y3)
      const pathD = `M ${x0},${y0} L ${x1},${y1} L ${x2},${y2} L ${x3},${y3}`

      return (
        <path
          key={idx}
          d={pathD}
          stroke={color}
          strokeWidth={lineWidth}
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )
    })
  }, [data, orientation, width, height, color, lineWidth, margin])

  return (
    <svg
      width={width}
      height={height}
      style={{ display: 'block' }}
      data-testid="dendrogram-svg"
    >
      <g>{paths}</g>
    </svg>
  )
}

export default DendrogramSVG
