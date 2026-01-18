import type { GenomeBrowserROIConfig } from '@/components/GenomeBrowser'

export const DEFAULT_OVERLAP_ROI_COLOR = 'rgba(114,46,209,0.25)'

export interface OverlapIgvNavigationInput {
  chromosome: string
  overlap_start: number | string
  overlap_end: number | string
  overlap_id?: string
}

export interface OverlapIgvNavigationResult {
  locus: string
  overlapStart: number
  overlapEnd: number
  roiConfigs: GenomeBrowserROIConfig[]
}

export interface OverlapIgvNavigationOptions {
  paddingBp?: number
  roiColor?: string
}

export function normalizeBp(value: number | string): number {
  if (typeof value === 'number') return value
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
}

export function buildOverlapIgvNavigation(
  record: OverlapIgvNavigationInput,
  options: OverlapIgvNavigationOptions = {},
): OverlapIgvNavigationResult {
  const paddingBp = options.paddingBp ?? 50_000
  const roiColor = options.roiColor ?? DEFAULT_OVERLAP_ROI_COLOR

  const overlapStart = normalizeBp(record.overlap_start)
  const overlapEnd = normalizeBp(record.overlap_end)

  const start = Math.max(0, overlapStart - paddingBp)
  const end = overlapEnd + paddingBp
  const locus = `${record.chromosome}:${start}-${end}`

  const roiConfigs: GenomeBrowserROIConfig[] = [
    {
      color: roiColor,
      features: [
        {
          chr: record.chromosome,
          start: overlapStart,
          end: overlapEnd,
          name: record.overlap_id ? `Overlap ${record.overlap_id}` : undefined,
        },
      ],
    },
  ]

  return { locus, overlapStart, overlapEnd, roiConfigs }
}
