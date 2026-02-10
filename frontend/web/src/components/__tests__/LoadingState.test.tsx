import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { LoadingState } from '../LoadingState'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => {
      const translations: Record<string, string> = {
        'status.loading': 'Loading...',
        'loading.elapsed': 'Elapsed',
        'loading.estimated': 'Est.',
      }
      return translations[key] || fallback || key
    },
  }),
}))

describe('LoadingState', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders with default loading text', () => {
    render(<LoadingState />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders custom message', () => {
    render(<LoadingState message="Fetching genome data..." />)
    expect(screen.getByText('Fetching genome data...')).toBeInTheDocument()
  })

  it('renders custom tip', () => {
    render(<LoadingState tip="This may take a while" />)
    expect(screen.getByText('This may take a while')).toBeInTheDocument()
  })

  it('renders both message and tip', () => {
    render(
      <LoadingState
        message="Loading genes"
        tip="Please wait"
      />
    )
    expect(screen.getByText('Loading genes')).toBeInTheDocument()
    expect(screen.getByText('Please wait')).toBeInTheDocument()
  })

  it('renders spinner element', () => {
    render(<LoadingState />)
    // Ant Design Spin creates an element with spin class
    const spinContainer = document.querySelector('.ant-spin')
    expect(spinContainer).toBeInTheDocument()
  })

  it('applies custom minHeight', () => {
    const { container } = render(<LoadingState minHeight={200} />)
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.style.minHeight).toBe('200px')
  })

  it('applies string minHeight', () => {
    const { container } = render(<LoadingState minHeight="50vh" />)
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.style.minHeight).toBe('50vh')
  })

  describe('Progress indicator', () => {
    it('shows progress bar when showProgress and estimatedTime provided', () => {
      render(<LoadingState showProgress estimatedTime={30} />)
      // Progress bar should be present
      const progressBar = document.querySelector('.ant-progress')
      expect(progressBar).toBeInTheDocument()
    })

    it('updates elapsed time every second', async () => {
      render(<LoadingState showProgress estimatedTime={30} />)

      // Initially shows 0s
      expect(screen.getByText(/Elapsed: 0s/)).toBeInTheDocument()

      // Advance timer by 5 seconds
      await act(async () => {
        vi.advanceTimersByTime(5000)
      })

      expect(screen.getByText(/Elapsed: 5s/)).toBeInTheDocument()
    })

    it('shows elapsed time without progress bar after 3 seconds', async () => {
      render(<LoadingState showProgress />)

      // Initially no elapsed time shown
      expect(screen.queryByText(/Elapsed:/)).not.toBeInTheDocument()

      // Advance timer by 4 seconds
      await act(async () => {
        vi.advanceTimersByTime(4000)
      })

      expect(screen.getByText(/Elapsed: 4s/)).toBeInTheDocument()
    })

    it('formats time correctly for minutes', async () => {
      render(<LoadingState showProgress estimatedTime={120} />)

      // Advance timer by 65 seconds
      await act(async () => {
        vi.advanceTimersByTime(65000)
      })

      expect(screen.getByText(/Elapsed: 1m 5s/)).toBeInTheDocument()
    })

    it('caps progress at 95%', async () => {
      render(<LoadingState showProgress estimatedTime={10} />)

      // Advance timer by 20 seconds (200% of estimated)
      await act(async () => {
        vi.advanceTimersByTime(20000)
      })

      // Progress should be capped at 95%
      const progressInner = document.querySelector('.ant-progress-bg') as HTMLElement
      // The width style should be at most 95%
      if (progressInner) {
        const width = parseFloat(progressInner.style.width)
        expect(width).toBeLessThanOrEqual(95)
      }
    })
  })

  describe('Size variants', () => {
    it('renders with small size', () => {
      render(<LoadingState size="small" />)
      const spin = document.querySelector('.ant-spin-sm')
      expect(spin).toBeInTheDocument()
    })

    it('renders with large size (default)', () => {
      render(<LoadingState />)
      const spin = document.querySelector('.ant-spin-lg')
      expect(spin).toBeInTheDocument()
    })
  })
})
