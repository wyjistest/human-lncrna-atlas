import { forwardRef } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { renderWithProviders } from '@/test/testUtils'
import GenomeBrowserPage from './index'

const mocks = vi.hoisted(() => ({
  getRepeatMaskerClassTracks: vi.fn(),
  getChIPSeqMarks: vi.fn(),
  getUCSCMultizTracks: vi.fn(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        title: 'Genome Browser',
        description: 'Interactive genome browser',
        trackControls: 'Track Controls',
        'chipseq.title': 'Epigenomic Tracks',
        'chipseq.baselineTitle': 'Paper-facing baseline',
        'chipseq.baselineGuide':
          'Main-text baseline: 8 core histone marks + DNase-HS. Extended human tracks: CTCF and H4K20me1.',
        'chipseq.enableTracks': 'Enable Epigenomic Tracks',
      }
      return translations[key] ?? key
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}))

vi.mock('@/components/GenomeBrowser', () => ({
  __esModule: true,
  default: forwardRef(function MockGenomeBrowser(_, ref) {
    return <div ref={ref as never} data-testid="mock-genome-browser" />
  }),
}))

vi.mock('@/components/GenomeBrowser/GenomeBrowserToolbar', () => ({
  __esModule: true,
  default: () => <div data-testid="mock-browser-toolbar" />,
}))

vi.mock('@/components/RepeatMaskerLegend', () => ({
  RepeatMaskerLegend: () => <div data-testid="mock-repeat-legend" />,
}))

vi.mock('@/api/features', () => ({
  getRepeatMaskerClassTracks: mocks.getRepeatMaskerClassTracks,
}))

vi.mock('@/api/genome', () => ({
  genomeApi: {
    getChIPSeqMarks: mocks.getChIPSeqMarks,
    getUCSCMultizTracks: mocks.getUCSCMultizTracks,
  },
}))

describe('GenomeBrowser page', () => {
  beforeEach(() => {
    mocks.getRepeatMaskerClassTracks.mockResolvedValue({
      data: { data: { tracks: [] } },
    })
    mocks.getChIPSeqMarks.mockResolvedValue({
      data: { data: { chipseq_schema_ready: true, marks: [] } },
    })
    mocks.getUCSCMultizTracks.mockResolvedValue({
      data: { data: { tracks: [] } },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows the paper baseline and extended human track guidance inside epigenomic controls', async () => {
    const user = userEvent.setup()

    renderWithProviders(<GenomeBrowserPage />)

    await user.click(screen.getByText('Track Controls'))
    await user.click(screen.getByText('Epigenomic Tracks'))

    expect(screen.getByText('Paper-facing baseline')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Main-text baseline: 8 core histone marks + DNase-HS. Extended human tracks: CTCF and H4K20me1.',
      ),
    ).toBeInTheDocument()
  })
})
