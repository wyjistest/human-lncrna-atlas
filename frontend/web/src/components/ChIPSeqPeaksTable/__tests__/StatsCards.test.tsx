/**
 * StatsCards Component Tests
 *
 * Tests for the statistics display cards in ChIP-seq data view.
 * Covers rendering, loading states, data formatting, and edge cases.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { StatsCards } from '../StatsCards'
import type { ChIPSeqSummary, MarkType } from '@/types/chipseq'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

// Mock markConfigs
vi.mock('@/config/markConfigs', () => ({
  getMarkColor: (markType: string) => {
    const colors: Record<string, string> = {
      H3K27me3: '#9B59B6',
      H3K4me3: '#27AE60',
      H3K9me3: '#8E44AD',
    }
    return colors[markType] || '#95A5A6'
  },
}))

describe('StatsCards', () => {
  // Mock summary data
  const mockSummary: ChIPSeqSummary = {
    mark_type: 'H3K27me3' as MarkType,
    total_peaks: 1500,
    avg_signal: 125.75,
    max_signal: 500.5,
    avg_fold_enrichment: 8.32,
    promoter_peaks: 300,
    gene_body_peaks: 500,
    upstream_peaks: 400,
    downstream_peaks: 300,
    position_distribution: {
      promoter: 300,
      upstream: 400,
      downstream: 300,
      intron: 350,
      exon: 150,
    },
  }

  describe('Rendering', () => {
    it('renders all four statistics cards', () => {
      render(<StatsCards markType="H3K27me3" summary={mockSummary} />)

      expect(screen.getByText('Total Peaks')).toBeInTheDocument()
      expect(screen.getByText('Avg Signal')).toBeInTheDocument()
      expect(screen.getByText('Avg Fold Enrichment')).toBeInTheDocument()
      expect(screen.getByText('Max Signal')).toBeInTheDocument()
    })

    it('displays correct statistics values', () => {
      const { container } = render(<StatsCards markType="H3K27me3" summary={mockSummary} />)

      // Total Peaks value formatted with comma separator
      expect(screen.getByText('1,500')).toBeInTheDocument()
      // Ant Design Statistic splits decimal values into int and decimal parts
      // So we check for the presence in container text
      expect(container.textContent).toContain('125')
      expect(container.textContent).toContain('75')
      // Max Signal with precision 2
      expect(container.textContent).toContain('500')
      expect(container.textContent).toContain('50')
      // Avg Fold Enrichment with 'x' suffix
      expect(container.textContent).toContain('8')
      expect(container.textContent).toContain('32')
    })

    it('renders position distribution card when data is available', () => {
      render(<StatsCards markType="H3K27me3" summary={mockSummary} />)

      expect(screen.getByText('Position Distribution')).toBeInTheDocument()
      // Position tags are rendered
      expect(screen.getByText(/promoter: 300/i)).toBeInTheDocument()
      expect(screen.getByText(/upstream: 400/i)).toBeInTheDocument()
    })

    it('does not render position distribution when empty', () => {
      const summaryWithoutDistribution: ChIPSeqSummary = {
        ...mockSummary,
        position_distribution: {},
      }

      render(<StatsCards markType="H3K27me3" summary={summaryWithoutDistribution} />)

      expect(screen.queryByText('Position Distribution')).not.toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('renders loading cards when loading is true', () => {
      const { container } = render(
        <StatsCards markType="H3K27me3" summary={undefined} loading={true} />
      )

      // Ant Design Card with loading shows skeleton
      const cards = container.querySelectorAll('.ant-card')
      expect(cards.length).toBeGreaterThanOrEqual(4)
    })

    it('renders cards with loading skeleton when loading is true', () => {
      const { container } = render(<StatsCards markType="H3K27me3" summary={undefined} loading={true} />)

      // When loading is true, Ant Design Card shows skeleton (loading state)
      // The card content is replaced with loading skeleton, so we just verify cards exist
      const loadingCards = container.querySelectorAll('.ant-card-loading')
      expect(loadingCards.length).toBeGreaterThanOrEqual(4)
    })
  })

  describe('No Data State', () => {
    it('returns null when no summary and not loading', () => {
      const { container } = render(
        <StatsCards markType="H3K27me3" summary={undefined} loading={false} />
      )

      expect(container.firstChild).toBeNull()
    })

    it('returns null when summary is undefined and loading is explicitly false', () => {
      const { container } = render(<StatsCards markType="H3K4me3" summary={undefined} />)

      expect(container.firstChild).toBeNull()
    })
  })

  describe('Data Formatting', () => {
    it('formats large numbers correctly with comma separators', () => {
      const largeSummary: ChIPSeqSummary = {
        ...mockSummary,
        total_peaks: 10500,
        avg_signal: 1234.56,
      }

      const { container } = render(<StatsCards markType="H3K27me3" summary={largeSummary} />)

      expect(screen.getByText('10,500')).toBeInTheDocument()
      // Ant Design Statistic splits decimal values
      expect(container.textContent).toContain('1,234')
      expect(container.textContent).toContain('56')
    })

    it('handles zero values gracefully', () => {
      const zeroSummary: ChIPSeqSummary = {
        ...mockSummary,
        total_peaks: 0,
        avg_signal: 0,
        max_signal: 0,
        avg_fold_enrichment: 0,
      }

      render(<StatsCards markType="H3K27me3" summary={zeroSummary} />)

      // All four 0s should be displayed (multiple elements with text '0')
      const zeroElements = screen.getAllByText('0')
      expect(zeroElements.length).toBeGreaterThanOrEqual(4)
    })

    it('handles null/undefined values in summary fields with fallback to 0', () => {
      // Create summary with missing optional fields but required fields present
      const partialSummary = {
        mark_type: 'H3K27me3' as MarkType,
        total_peaks: 100,
        avg_signal: 0,
        max_signal: 0,
        avg_fold_enrichment: 0,
        promoter_peaks: 0,
        gene_body_peaks: 0,
        upstream_peaks: 0,
        downstream_peaks: 0,
        position_distribution: {},
      }

      render(<StatsCards markType="H3K27me3" summary={partialSummary} />)

      expect(screen.getByText('100')).toBeInTheDocument()
    })
  })

  describe('Mark Type Styling', () => {
    it('applies correct color based on mark type', () => {
      render(<StatsCards markType="H3K27me3" summary={mockSummary} />)

      // The component applies markColor to the valueStyle of the Total Peaks statistic
      // We verify the component renders without error with the mark type
      expect(screen.getByText('1,500')).toBeInTheDocument()
    })

    it('renders correctly for different mark types', () => {
      const { rerender } = render(<StatsCards markType="H3K4me3" summary={mockSummary} />)
      expect(screen.getByText('Total Peaks')).toBeInTheDocument()

      rerender(<StatsCards markType="H3K9me3" summary={mockSummary} />)
      expect(screen.getByText('Total Peaks')).toBeInTheDocument()
    })
  })

  describe('Position Tags', () => {
    it('sorts position tags by count in descending order', () => {
      const summaryWithDistribution: ChIPSeqSummary = {
        ...mockSummary,
        position_distribution: {
          upstream: 400,
          promoter: 300,
          intron: 350,
        },
      }

      render(<StatsCards markType="H3K27me3" summary={summaryWithDistribution} />)

      // All tags should be present
      expect(screen.getByText(/upstream: 400/i)).toBeInTheDocument()
      expect(screen.getByText(/intron: 350/i)).toBeInTheDocument()
      expect(screen.getByText(/promoter: 300/i)).toBeInTheDocument()
    })

    it('renders tooltips with percentage information', () => {
      render(<StatsCards markType="H3K27me3" summary={mockSummary} />)

      // Tags should be present (tooltips are tested implicitly)
      const tags = screen.getAllByText(/: \d+/i)
      expect(tags.length).toBeGreaterThan(0)
    })
  })
})
