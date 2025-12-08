import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ErrorState } from '../ErrorState'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'error.loadFailed': 'Load Failed',
        'error.unknown': 'Unknown Error',
        'error.retry': 'Retry',
      }
      return translations[key] || key
    },
  }),
}))

describe('ErrorState', () => {
  it('renders error title', () => {
    render(<ErrorState error={new Error('Test error')} />)
    expect(screen.getByText('Load Failed')).toBeInTheDocument()
  })

  it('renders error message from Error instance', () => {
    render(<ErrorState error={new Error('Test error message')} />)
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('renders string error message directly for string types', () => {
    render(<ErrorState error="string error" />)
    // String errors are displayed directly (not as "Unknown Error")
    expect(screen.getByText('string error')).toBeInTheDocument()
  })

  it('renders retry button when onRetry provided', () => {
    const onRetry = vi.fn()
    render(<ErrorState error={new Error('test')} onRetry={onRetry} />)
    // Button with icon has accessible name that includes icon aria-label
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument()
  })

  it('does not render retry button when onRetry not provided', () => {
    render(<ErrorState error={new Error('test')} />)
    expect(screen.queryByRole('button', { name: /Retry/i })).not.toBeInTheDocument()
  })

  it('calls onRetry when retry button clicked', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState error={new Error('test')} onRetry={onRetry} />)

    await user.click(screen.getByRole('button', { name: /Retry/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
