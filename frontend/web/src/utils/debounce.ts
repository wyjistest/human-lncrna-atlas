export type DebouncedFn<TArgs extends unknown[]> = ((...args: TArgs) => void) & {
  cancel: () => void
}

/**
 * A tiny debounce implementation (lodash-free).
 *
 * Notes:
 * - Only the latest call within the wait window is executed.
 * - `cancel()` clears any pending invocation.
 */
export function debounce<TArgs extends unknown[]>(
  fn: (...args: TArgs) => void,
  waitMs: number
): DebouncedFn<TArgs> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined

  const debounced = ((...args: TArgs) => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId)
    }

    timeoutId = setTimeout(() => {
      timeoutId = undefined
      fn(...args)
    }, waitMs)
  }) as DebouncedFn<TArgs>

  debounced.cancel = () => {
    if (timeoutId === undefined) return
    clearTimeout(timeoutId)
    timeoutId = undefined
  }

  return debounced
}

