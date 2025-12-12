/**
 * FilterPanel Component Tests
 *
 * Tests for the advanced filter panel in ChIP-seq data view.
 * Covers filter rendering, default values, reset functionality, and user interactions.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { FilterPanel } from '../FilterPanel'
import type { ChIPSeqFilters, MarkType } from '@/types/chipseq'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

// Mock i18n
vi.mock('@/i18n', () => ({
  default: {
    language: 'en',
  },
}))

// Mock markConfigs
vi.mock('@/config/markConfigs', () => ({
  getMarkConfig: (markType: string) => ({
    displayName: `${markType} (Test)`,
    shortName: markType,
    color: '#000000',
    secondaryColor: '#ffffff',
    category: 'repressive',
    description: 'Test mark',
    icon: 'test',
    isCommon: true,
    sortOrder: 1,
    defaultFilters: {
      min_fold_enrichment: 5,
      max_qvalue: 0.01,
      flanking: 10000,
    },
  }),
}))

// Mock cellTypeConfigs
vi.mock('@/config/cellTypeConfigs', () => ({
  getCellTypeOptions: () => [
    { value: 'K562', label: 'K562 (Leukemia)' },
    { value: 'GM12878', label: 'GM12878 (B-lymphocyte)' },
    { value: 'HepG2', label: 'HepG2 (Hepatocellular carcinoma)' },
  ],
}))

// Mock lodash debounce to execute immediately in tests
vi.mock('lodash', async (importOriginal) => {
  const original = await importOriginal<typeof import('lodash')>()
  return {
    ...original,
    debounce: (fn: (...args: unknown[]) => unknown) => {
      const debouncedFn = fn as { cancel?: () => void }
      debouncedFn.cancel = vi.fn()
      return debouncedFn
    },
  }
})

describe('FilterPanel', () => {
  // Default filter values for tests
  const defaultFilters: ChIPSeqFilters = {
    page: 1,
    page_size: 20,
    flanking: 10000,
    sort_by: 'fold_enrichment',
    sort_order: 'desc',
  }

  // Mock handlers
  let mockOnFiltersChange: ReturnType<typeof vi.fn>
  let mockOnReset: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockOnFiltersChange = vi.fn()
    mockOnReset = vi.fn()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders the filter panel card with title', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Filters')).toBeInTheDocument()
    })

    it('renders Q-Value filter input', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Max Q-Value (FDR):')).toBeInTheDocument()
    })

    it('renders Min Signal Value filter input', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Min Signal Value:')).toBeInTheDocument()
    })

    it('renders Relative Position filter select', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Relative Position:')).toBeInTheDocument()
    })

    it('renders Flanking Region filter select', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Flanking Region:')).toBeInTheDocument()
    })

    it('renders Cell Type filter select', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Cell Type:')).toBeInTheDocument()
    })

    it('renders Fold Enrichment slider', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText(/Fold Enrichment:/)).toBeInTheDocument()
    })

    it('renders Reset button', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByRole('button', { name: /Reset/i })).toBeInTheDocument()
    })
  })

  describe('Default Values', () => {
    it('displays filter values from props', () => {
      const filtersWithValues: ChIPSeqFilters = {
        ...defaultFilters,
        max_qvalue: 0.05,
        min_signal: 10,
      }

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={filtersWithValues}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      // Find all spinbuttons - there should be at least 2 (Q-value and Signal)
      const spinbuttons = screen.getAllByRole('spinbutton')
      expect(spinbuttons.length).toBeGreaterThanOrEqual(2)
    })

    it('uses default flanking value from filters', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={{ ...defaultFilters, flanking: 25000 }}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      // The flanking region select should be rendered
      expect(screen.getByText('Flanking Region:')).toBeInTheDocument()
    })

    it('shows fold enrichment range from filters', () => {
      const filtersWithRange: ChIPSeqFilters = {
        ...defaultFilters,
        min_fold_enrichment: 10,
        max_fold_enrichment: 50,
      }

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={filtersWithRange}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      // The fold enrichment label should show the range
      expect(screen.getByText(/10 - 50x/)).toBeInTheDocument()
    })
  })

  describe('Reset Functionality', () => {
    it('calls onReset when Reset button is clicked', async () => {
      const user = userEvent.setup()

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      const resetButton = screen.getByRole('button', { name: /Reset/i })
      await user.click(resetButton)

      expect(mockOnReset).toHaveBeenCalledOnce()
    })

    it('does not call onFiltersChange when Reset is clicked', async () => {
      const user = userEvent.setup()

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      await user.click(screen.getByRole('button', { name: /Reset/i }))

      // onFiltersChange should not be called from reset button
      // (reset is handled by parent component)
      expect(mockOnFiltersChange).not.toHaveBeenCalled()
    })
  })

  describe('Collapsed State', () => {
    it('returns null when collapsed is true', () => {
      const { container } = render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
          collapsed={true}
        />
      )

      expect(container.firstChild).toBeNull()
    })

    it('renders normally when collapsed is false', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
          collapsed={false}
        />
      )

      expect(screen.getByText('Filters')).toBeInTheDocument()
    })

    it('renders normally when collapsed is not provided (default false)', () => {
      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Filters')).toBeInTheDocument()
    })
  })

  describe('Filter Change Handlers', () => {
    it('calls onFiltersChange with updated filters when Q-value changes', async () => {
      const user = userEvent.setup()

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      // Find the Q-value input (first spinbutton after "Max Q-Value" text)
      const spinbuttons = screen.getAllByRole('spinbutton')
      const qvalueInput = spinbuttons[0]

      await user.clear(qvalueInput)
      await user.type(qvalueInput, '0.05')

      await waitFor(() => {
        expect(mockOnFiltersChange).toHaveBeenCalled()
      })
    })

    it('calls onFiltersChange with page reset to 1 when filter changes', async () => {
      const user = userEvent.setup()

      render(
        <FilterPanel
          markType="H3K27me3"
          filters={{ ...defaultFilters, page: 5 }}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      const spinbuttons = screen.getAllByRole('spinbutton')
      const signalInput = spinbuttons[1] // Second spinbutton is signal

      await user.clear(signalInput)
      await user.type(signalInput, '10')

      await waitFor(() => {
        expect(mockOnFiltersChange).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      })
    })
  })

  describe('Different Mark Types', () => {
    it('renders correctly for H3K4me3 mark type', () => {
      render(
        <FilterPanel
          markType="H3K4me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Filters')).toBeInTheDocument()
    })

    it('renders correctly for DNase-HS mark type', () => {
      render(
        <FilterPanel
          markType="DNase-HS"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText('Filters')).toBeInTheDocument()
    })
  })

  describe('Tooltips', () => {
    it('renders info icon for Q-Value tooltip', () => {
      const { container } = render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      // Info icons are present in the document
      const infoIcons = container.querySelectorAll('[class*="anticon-info-circle"]')
      expect(infoIcons.length).toBeGreaterThan(0)
    })

    it('renders info icon for Flanking Region tooltip', () => {
      const { container } = render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      const infoIcons = container.querySelectorAll('[class*="anticon-info-circle"]')
      expect(infoIcons.length).toBeGreaterThanOrEqual(2)
    })

    it('renders info icon for Fold Enrichment tooltip', () => {
      const { container } = render(
        <FilterPanel
          markType="H3K27me3"
          filters={defaultFilters}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      const infoIcons = container.querySelectorAll('[class*="anticon-info-circle"]')
      expect(infoIcons.length).toBeGreaterThanOrEqual(3)
    })
  })

  describe('External Filter Updates', () => {
    it('syncs local fold enrichment state when filters change externally', () => {
      const { rerender } = render(
        <FilterPanel
          markType="H3K27me3"
          filters={{ ...defaultFilters, min_fold_enrichment: 10, max_fold_enrichment: 50 }}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText(/10 - 50x/)).toBeInTheDocument()

      // Rerender with new filter values (simulating reset)
      rerender(
        <FilterPanel
          markType="H3K27me3"
          filters={{ ...defaultFilters, min_fold_enrichment: 0, max_fold_enrichment: 100 }}
          onFiltersChange={mockOnFiltersChange}
          onReset={mockOnReset}
        />
      )

      expect(screen.getByText(/0 - 100x/)).toBeInTheDocument()
    })
  })
})
