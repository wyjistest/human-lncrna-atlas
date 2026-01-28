import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const componentRoot = join(process.cwd(), 'src/components/ChIPSeqPeaksTable')

function readComponent(path: string) {
  return readFileSync(join(componentRoot, path), 'utf-8')
}

describe('ChIPSeqPeaksTable data-testid', () => {
  it('adds core testids in index', () => {
    const source = readComponent('index.tsx')
    expect(source).toContain('data-testid="chipseq-container"')
    expect(source).toContain('compare-marks-button')
    expect(source).toContain('exit-compare-button')
    expect(source).toContain('data-testid="export-button"')
  })

  it('adds mark selector testid', () => {
    const source = readComponent('MarkSelector.tsx')
    expect(source).toContain('data-testid="mark-selector"')
  })

  it('adds filter panel testids', () => {
    const source = readComponent('FilterPanel.tsx')
    expect(source).toContain('data-testid="filter-panel"')
    expect(source).toContain('data-testid="cell-type-filter"')
  })

  it('adds peaks table testid', () => {
    const source = readComponent('PeaksTable.tsx')
    expect(source).toContain('data-testid="peaks-table"')
  })

  it('adds stats cards container testid', () => {
    const source = readComponent('StatsCards.tsx')
    expect(source).toContain('data-testid="stats-cards-container"')
  })

  it('adds compare charts testid', () => {
    const source = readComponent('CompareCharts.tsx')
    expect(source).toContain('data-testid="radar-compare-chart"')
  })

  it('adds matrix chart and metric selector testids', () => {
    const source = readComponent('CellLineHeatmapMatrix.tsx')
    expect(source).toContain('data-testid="cell-line-matrix-chart"')
    expect(source).toContain('data-testid="metric-selector"')
  })

  it('adds bivalent domain badge testid', () => {
    const source = readComponent('BivalentDomainBadge.tsx')
    expect(source).toContain('data-testid="bivalent-domain-badge"')
  })
})
