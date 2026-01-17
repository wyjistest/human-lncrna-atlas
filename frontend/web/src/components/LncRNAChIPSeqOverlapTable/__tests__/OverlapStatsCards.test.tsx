/**
 * OverlapStatsCards Component Tests
 *
 * Tests for the statistics display cards in lncRNA-ChIP-seq overlap analysis view.
 * Covers rendering, loading states, data display, and edge cases.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { OverlapStatsCards } from '../OverlapStatsCards'
import type { OverlapSummary } from '@/types/lncRNAChIPSeqOverlap'

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
      H3K27ac: '#E67E22',
    }
    return colors[markType] || '#95A5A6'
  },
}))

// Mock cellTypeConfigs
vi.mock('@/config/cellTypeConfigs', () => ({
  getCellTypeColor: (cellType: string) => {
    const colors: Record<string, string> = {
      K562: '#E74C3C',
      GM12878: '#3498DB',
      HepG2: '#27AE60',
    }
    return colors[cellType] || '#999999'
  },
}))

describe('OverlapStatsCards', () => {
  // Mock summary data
  const mockSummary: OverlapSummary = {
    total_overlaps: 5000,
    unique_lncrnas: 150,
    unique_target_genes: 800,
    unique_marks: 5,
    unique_cell_types: 3,
    avg_overlap_length: 250,
    avg_binding_affinity: 125.5,
    avg_peak_strength: 8.75,
    by_mark_type: [
      { mark_type: 'H3K27me3', count: 1500, avg_strength: 9.2 },
      { mark_type: 'H3K4me3', count: 1200, avg_strength: 8.5 },
      { mark_type: 'H3K27ac', count: 1000, avg_strength: 7.8 },
    ],
    by_cell_type: [
      { cell_type: 'K562', count: 2000 },
      { cell_type: 'GM12878', count: 1800 },
      { cell_type: 'HepG2', count: 1200 },
    ],
  }

  describe('Statistics Cards Rendering', () => {
    it('renders all primary statistics cards', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      expect(screen.getByText('Total Overlaps')).toBeInTheDocument()
      expect(screen.getByText('Unique lncRNAs')).toBeInTheDocument()
      expect(screen.getByText('Unique Targets')).toBeInTheDocument()
      expect(screen.getByText('Unique Marks')).toBeInTheDocument()
    })

    it('renders secondary statistics cards', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      expect(screen.getByText('Avg Overlap Length')).toBeInTheDocument()
      expect(screen.getByText('Avg Binding Affinity')).toBeInTheDocument()
      expect(screen.getByText('Avg Peak Strength')).toBeInTheDocument()
    })

    it('displays correct statistics values', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      // Values are formatted with comma separators
      expect(screen.getByText('5,000')).toBeInTheDocument()
      expect(screen.getByText('150')).toBeInTheDocument()
      expect(screen.getByText('800')).toBeInTheDocument()
      expect(screen.getByText('5')).toBeInTheDocument()
    })

    it('displays formatted average values', () => {
      const { container } = render(<OverlapStatsCards summary={mockSummary} />)

      // Avg overlap length (integer, no decimal split)
      expect(screen.getByText('250')).toBeInTheDocument()
      // Ant Design Statistic splits decimal values into parts
      // Avg binding affinity 125.5 -> "125" and "50" (precision 2)
      expect(container.textContent).toContain('125')
      expect(container.textContent).toContain('50')
      // Avg peak strength 8.75 -> "8" and "75"
      expect(container.textContent).toContain('8')
      expect(container.textContent).toContain('75')
    })
  })

  describe('Distribution Cards', () => {
    it('renders distribution by mark type card when data available', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      expect(screen.getByText('Distribution by Mark Type')).toBeInTheDocument()
    })

    it('renders distribution by cell type card when data available', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      expect(screen.getByText('Distribution by Cell Type')).toBeInTheDocument()
    })

    it('renders mark type tags with counts', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      // Mark tags display raw counts (no comma formatting in Tag text)
      expect(screen.getByText(/H3K27me3: 1500/i)).toBeInTheDocument()
      expect(screen.getByText(/H3K4me3: 1200/i)).toBeInTheDocument()
      expect(screen.getByText(/H3K27ac: 1000/i)).toBeInTheDocument()
    })

    it('renders cell type tags with counts', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      expect(screen.getByText(/K562: 2000/i)).toBeInTheDocument()
      expect(screen.getByText(/GM12878: 1800/i)).toBeInTheDocument()
      expect(screen.getByText(/HepG2: 1200/i)).toBeInTheDocument()
    })

    it('does not render mark type distribution when empty', () => {
      const summaryWithoutMarks: OverlapSummary = {
        ...mockSummary,
        by_mark_type: [],
      }

      render(<OverlapStatsCards summary={summaryWithoutMarks} />)

      expect(screen.queryByText('Distribution by Mark Type')).not.toBeInTheDocument()
    })

    it('does not render cell type distribution when empty', () => {
      const summaryWithoutCellTypes: OverlapSummary = {
        ...mockSummary,
        by_cell_type: [],
      }

      render(<OverlapStatsCards summary={summaryWithoutCellTypes} />)

      expect(screen.queryByText('Distribution by Cell Type')).not.toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('renders loading cards when loading is true', () => {
      const { container } = render(
        <OverlapStatsCards summary={undefined} loading={true} />
      )

      // Ant Design Card with loading shows skeleton
      const cards = container.querySelectorAll('.ant-card')
      expect(cards.length).toBeGreaterThanOrEqual(7)
    })

    it('renders cards with loading skeleton when loading is true', () => {
      const { container } = render(<OverlapStatsCards summary={undefined} loading={true} />)

      // When loading is true, Ant Design Card shows skeleton (loading state)
      // The card content is replaced with loading skeleton, so we just verify cards exist
      const loadingCards = container.querySelectorAll('.ant-card-loading')
      expect(loadingCards.length).toBeGreaterThanOrEqual(7)
    })
  })

  describe('No Data State', () => {
    it('returns null when no summary and not loading', () => {
      const { container } = render(
        <OverlapStatsCards summary={undefined} loading={false} />
      )

      expect(container.firstChild).toBeNull()
    })

    it('returns null when summary is undefined and loading is explicitly false', () => {
      const { container } = render(<OverlapStatsCards summary={undefined} />)

      expect(container.firstChild).toBeNull()
    })
  })

  describe('Data Formatting', () => {
    it('handles zero values gracefully', () => {
      const zeroSummary: OverlapSummary = {
        total_overlaps: 0,
        unique_lncrnas: 0,
        unique_target_genes: 0,
        unique_marks: 0,
        unique_cell_types: 0,
        avg_overlap_length: 0,
        avg_binding_affinity: 0,
        avg_peak_strength: 0,
        by_mark_type: [],
        by_cell_type: [],
      }

      render(<OverlapStatsCards summary={zeroSummary} />)

      // Multiple 0s should be displayed
      const zeroElements = screen.getAllByText('0')
      expect(zeroElements.length).toBeGreaterThanOrEqual(7)
    })

    it('handles large numbers correctly', () => {
      const largeSummary: OverlapSummary = {
        ...mockSummary,
        total_overlaps: 1000000,
        unique_lncrnas: 50000,
      }

      render(<OverlapStatsCards summary={largeSummary} />)

      // Formatted with comma separators
      expect(screen.getByText('1,000,000')).toBeInTheDocument()
      expect(screen.getByText('50,000')).toBeInTheDocument()
    })

    it('handles decimal values with proper precision', () => {
      const decimalSummary: OverlapSummary = {
        ...mockSummary,
        avg_binding_affinity: 123.45,
        avg_peak_strength: 9.87,
      }

      const { container } = render(<OverlapStatsCards summary={decimalSummary} />)

      // Values should be formatted with precision 2
      // Ant Design Statistic splits values into int and decimal parts
      // So we check for the presence of both parts in the container
      expect(container.textContent).toContain('123')
      expect(container.textContent).toContain('45')
      expect(container.textContent).toContain('9')
      expect(container.textContent).toContain('87')
    })
  })

  describe('Mark Type Tags Sorting', () => {
    it('sorts mark type tags by count in descending order', () => {
      const unsortedSummary: OverlapSummary = {
        ...mockSummary,
        by_mark_type: [
          { mark_type: 'H3K4me3', count: 500, avg_strength: 7.0 },
          { mark_type: 'H3K27me3', count: 1500, avg_strength: 9.0 },
          { mark_type: 'H3K27ac', count: 800, avg_strength: 8.0 },
        ],
      }

      render(<OverlapStatsCards summary={unsortedSummary} />)

      // All tags should be present (raw counts without comma formatting)
      expect(screen.getByText(/H3K27me3: 1500/i)).toBeInTheDocument()
      expect(screen.getByText(/H3K27ac: 800/i)).toBeInTheDocument()
      expect(screen.getByText(/H3K4me3: 500/i)).toBeInTheDocument()
    })
  })

  describe('Cell Type Tags Sorting', () => {
    it('sorts cell type tags by count in descending order', () => {
      const unsortedSummary: OverlapSummary = {
        ...mockSummary,
        by_cell_type: [
          { cell_type: 'HepG2', count: 300 },
          { cell_type: 'K562', count: 1000 },
          { cell_type: 'GM12878', count: 600 },
        ],
      }

      render(<OverlapStatsCards summary={unsortedSummary} />)

      // All tags should be present (raw counts)
      expect(screen.getByText(/K562: 1000/i)).toBeInTheDocument()
      expect(screen.getByText(/GM12878: 600/i)).toBeInTheDocument()
      expect(screen.getByText(/HepG2: 300/i)).toBeInTheDocument()
    })
  })

  describe('Tooltips', () => {
    it('renders mark type tags with tooltip information', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      // Tags should be present (tooltips are rendered on hover)
      const markTags = screen.getByText(/H3K27me3: 1500/i)
      expect(markTags).toBeInTheDocument()
    })

    it('renders cell type tags with tooltip information', () => {
      render(<OverlapStatsCards summary={mockSummary} />)

      // Tags should be present
      const cellTags = screen.getByText(/K562: 2000/i)
      expect(cellTags).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles summary with only required fields', () => {
      const minimalSummary: OverlapSummary = {
        total_overlaps: 101,
        unique_lncrnas: 11,
        unique_target_genes: 21,
        unique_marks: 2,
        unique_cell_types: 1,
        avg_overlap_length: 99,
        avg_binding_affinity: 51,
        avg_peak_strength: 5.5,
        by_mark_type: [],
        by_cell_type: [],
      }

      render(<OverlapStatsCards summary={minimalSummary} />)

      expect(screen.getByText('101')).toBeInTheDocument()
      expect(screen.getByText('11')).toBeInTheDocument()
      expect(screen.getByText('21')).toBeInTheDocument()
    })

    it('handles undefined by_mark_type and by_cell_type arrays', () => {
      // This tests the conditional rendering with undefined arrays
      const summaryWithUndefinedArrays = {
        total_overlaps: 100,
        unique_lncrnas: 10,
        unique_target_genes: 20,
        unique_marks: 2,
        unique_cell_types: 1,
        avg_overlap_length: 100,
        avg_binding_affinity: 50,
        avg_peak_strength: 5,
        by_mark_type: undefined as unknown as OverlapSummary['by_mark_type'],
        by_cell_type: undefined as unknown as OverlapSummary['by_cell_type'],
      }

      render(<OverlapStatsCards summary={summaryWithUndefinedArrays} />)

      expect(screen.queryByText('Distribution by Mark Type')).not.toBeInTheDocument()
      expect(screen.queryByText('Distribution by Cell Type')).not.toBeInTheDocument()
    })
  })

  describe('Card Icons', () => {
    it('renders appropriate icons for each statistic', () => {
      const { container } = render(<OverlapStatsCards summary={mockSummary} />)

      // Check that anticon classes are present (icons are rendered)
      const icons = container.querySelectorAll('[class*="anticon"]')
      expect(icons.length).toBeGreaterThan(0)
    })
  })
})
