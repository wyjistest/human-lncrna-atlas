import { describe, it, expect, vi, afterEach } from 'vitest'
import { debounce } from './debounce'

describe('debounce', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('delays execution and uses the latest args', () => {
    vi.useFakeTimers()
    const fn = vi.fn<(value: string) => void>()
    const debounced = debounce<[string]>(fn, 50)

    debounced('a')
    debounced('b')
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(49)
    expect(fn).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('b')
  })

  it('cancel() prevents the pending invocation', () => {
    vi.useFakeTimers()
    const fn = vi.fn<() => void>()
    const debounced = debounce(fn, 50)

    debounced()
    debounced.cancel()
    vi.advanceTimersByTime(60)

    expect(fn).not.toHaveBeenCalled()
  })
})

