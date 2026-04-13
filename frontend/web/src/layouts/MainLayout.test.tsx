import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import MainLayout from './MainLayout'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => {
      const translations: Record<string, string> = {
        home: 'Overview',
        genes: 'Genes',
        diseases: 'Traits',
        network: 'Trait-centered Networks',
        conservation: 'Conservation & Rewiring',
        overlap: 'Epigenomic Context',
        analysis: 'Evidence Hub',
        siteTitle: 'Human LncRNA Atlas Companion',
        stats: 'Statistics',
        regulations: 'Candidate Regulatory Edges',
        genomeBrowser: 'Genome Browser',
        chipseqCompare: 'ChIP-seq Compare',
        cache: 'Cache',
        materializedViews: 'Materialized Views',
        monitoring: 'Monitoring',
      }
      return translations[key] ?? fallback ?? key
    },
  }),
}))

vi.mock('@/components/LanguageSwitch', () => ({
  LanguageSwitch: () => <div data-testid="language-switch">Language</div>,
}))

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  return {
    ...actual,
    Grid: {
      ...actual.Grid,
      useBreakpoint: () => ({ md: true }),
    },
  }
})

function renderLayout(initialEntry = '/') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Outlet />} />
          <Route path="genes" element={<Outlet />} />
          <Route path="diseases" element={<Outlet />} />
          <Route path="network" element={<Outlet />} />
          <Route path="conservation" element={<Outlet />} />
          <Route path="lncrna-chipseq-overlap" element={<Outlet />} />
          <Route path="analysis" element={<Outlet />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('MainLayout', () => {
  it('shows the reviewer-facing public navigation without admin or toolbox clutter', () => {
    renderLayout()

    expect(screen.getByText('Human LncRNA Atlas Companion')).toBeInTheDocument()
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Genes')).toBeInTheDocument()
    expect(screen.getByText('Traits')).toBeInTheDocument()
    expect(screen.getByText('Trait-centered Networks')).toBeInTheDocument()
    expect(screen.getByText('Conservation & Rewiring')).toBeInTheDocument()
    expect(screen.getByText('Epigenomic Context')).toBeInTheDocument()
    expect(screen.getByText('Evidence Hub')).toBeInTheDocument()

    expect(screen.queryByText('Statistics')).not.toBeInTheDocument()
    expect(screen.queryByText('Candidate Regulatory Edges')).not.toBeInTheDocument()
    expect(screen.queryByText('Genome Browser')).not.toBeInTheDocument()
    expect(screen.queryByText('ChIP-seq Compare')).not.toBeInTheDocument()
    expect(screen.queryByText('Cache')).not.toBeInTheDocument()
    expect(screen.queryByText('Materialized Views')).not.toBeInTheDocument()
    expect(screen.queryByText('Monitoring')).not.toBeInTheDocument()
  })
})
