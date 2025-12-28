import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('antd', () => ({
  message: {
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

import { message } from 'antd'
import { createThrottledMessage } from './throttledMessage'

describe('throttledMessage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(0))
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('deduplicates identical messages within dedupeWindow', () => {
    const queue = createThrottledMessage({ dedupeWindow: 2000 })
    queue.showError({ type: 'unknown', message: 'A' })

    vi.advanceTimersByTime(1000)
    queue.showError({ type: 'unknown', message: 'A' })

    expect(message.error).toHaveBeenCalledTimes(1)
  })

  it('keeps rate_limit throttling for full minInterval (30s)', () => {
    const queue = createThrottledMessage({})

    queue.showError({ type: 'rate_limit', message: 'Too many requests' })

    vi.advanceTimersByTime(15000)
    queue.showError({ type: 'rate_limit', message: 'Too many requests (again)' })

    expect(message.error).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(15000)
    queue.showError({ type: 'rate_limit', message: 'Too many requests (after 30s)' })
    expect(message.error).toHaveBeenCalledTimes(2)
  })

  it('suppresses overflow and emits a summary toast after windowDuration', () => {
    const queue = createThrottledMessage({ maxPerWindow: 3, windowDuration: 5000 })

    queue.showError({ type: 'unknown', message: 'u1' })
    vi.advanceTimersByTime(2001)
    queue.showError({ type: 'unknown', message: 'u2' })
    vi.advanceTimersByTime(2001)
    queue.showError({ type: 'unknown', message: 'u3' })

    // Window count is now maxed out; further messages that countAgainstLimit are suppressed.
    vi.advanceTimersByTime(498)
    queue.showError({ type: 'validation', message: 'v1' })
    queue.showError({ type: 'validation', message: 'v2' })

    expect(message.error).toHaveBeenCalledTimes(3)

    // Summary is scheduled relative to the first suppressed call.
    vi.advanceTimersByTime(5000)
    expect(message.error).toHaveBeenCalledTimes(4)
    expect(message.error).toHaveBeenLastCalledWith('2 more error(s) suppressed')
  })

  it('is silent for canceled requests', () => {
    const queue = createThrottledMessage({})
    queue.showError({ type: 'canceled', message: 'Request canceled' })
    expect(message.error).not.toHaveBeenCalled()
  })
})

