import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { AdvancedFilters } from './AdvancedFilters'

const mocks = vi.hoisted(() => ({
  onFilterChange: vi.fn(),
  onReset: vi.fn(),
  useBARange: vi.fn(),
  useRegulationLncRNAOptions: vi.fn(),
  useRegulationTargetOptions: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' },
  }),
}))

vi.mock('@/hooks/useDetailedStats', () => ({
  useBARange: mocks.useBARange,
}))

vi.mock('@/hooks/useRegulations', () => ({
  useRegulationLncRNAOptions: mocks.useRegulationLncRNAOptions,
  useRegulationTargetOptions: mocks.useRegulationTargetOptions,
}))

vi.mock('antd', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require('react')

  const Form = ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children)
  Form.Item = ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children)

  const Space = ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children)
  Space.Compact = ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children)

  return {
    Form,
    Row: ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children),
    Col: ({ children }: { children: React.ReactNode }) => React.createElement('div', {}, children),
    Space,
    InputNumber: (props: { 'aria-label'?: string }) =>
      React.createElement('input', { type: 'number', 'aria-label': props['aria-label'] }),
    Button: (props: { onClick?: () => void; children?: React.ReactNode }) =>
      React.createElement('button', { type: 'button', onClick: props.onClick }, props.children),
    Select: (props: { 'aria-label'?: string; onChange?: (value: number | null) => void }) => {
      const ariaLabel = props['aria-label'] ?? 'select'
      const nextValue = ariaLabel === 'filters.targetName' ? 100 : 1
      return React.createElement(
        'button',
        { type: 'button', 'aria-label': ariaLabel, onClick: () => props.onChange?.(nextValue) },
        'select'
      )
    },
    Collapse: (props: { items?: Array<{ key: string; label: React.ReactNode; children: React.ReactNode }>; onChange?: (key: string[]) => void }) => {
      const item = props.items?.[0]
      return React.createElement(
        'div',
        {},
        React.createElement(
          'button',
          { type: 'button', onClick: () => props.onChange?.(['filters']) },
          item?.label
        ),
        item?.children
      )
    },
  }
})

describe('Regulations AdvancedFilters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.useBARange.mockReturnValue({
      data: { min_ba: 0, max_ba: 200 },
      isLoading: false,
    })
    mocks.useRegulationLncRNAOptions.mockReturnValue({ data: { lncrnas: [] }, isLoading: false })
    mocks.useRegulationTargetOptions.mockReturnValue({ data: { targets: [] }, isLoading: false })
  })

  it('does not enable options hooks until advanced filters panel opens', () => {
    render(<AdvancedFilters filters={{}} onFilterChange={mocks.onFilterChange} onReset={mocks.onReset} />)

    expect(mocks.useRegulationLncRNAOptions).toHaveBeenCalledWith(undefined, { enabled: false })
    expect(mocks.useRegulationTargetOptions).toHaveBeenCalledWith(undefined, { enabled: false })

    fireEvent.click(screen.getByRole('button', { name: /Advanced Filters/ }))

    expect(mocks.useRegulationLncRNAOptions).toHaveBeenCalledWith(undefined, { enabled: true })
    expect(mocks.useRegulationTargetOptions).toHaveBeenCalledWith(undefined, { enabled: true })
  })

  it('clears legacy lncrna_gene_name when selecting lncrna_gene_id', () => {
    render(
      <AdvancedFilters
        filters={{ lncrna_gene_name: 'MALAT1' }}
        onFilterChange={mocks.onFilterChange}
        onReset={mocks.onReset}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'filters.lncrnaName' }))

    expect(mocks.onFilterChange).toHaveBeenCalledWith('lncrna_gene_name', undefined)
    expect(mocks.onFilterChange).toHaveBeenCalledWith('lncrna_gene_id', 1)
  })

  it('clears legacy target_gene_name when selecting target_gene_id', () => {
    render(
      <AdvancedFilters
        filters={{ target_gene_name: 'TP53' }}
        onFilterChange={mocks.onFilterChange}
        onReset={mocks.onReset}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'filters.targetName' }))

    expect(mocks.onFilterChange).toHaveBeenCalledWith('target_gene_name', undefined)
    expect(mocks.onFilterChange).toHaveBeenCalledWith('target_gene_id', 100)
  })
})
