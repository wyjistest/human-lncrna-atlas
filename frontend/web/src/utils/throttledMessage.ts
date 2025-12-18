/**
 * Throttled Message Queue with Error Type Awareness
 *
 * Prevents "toast storm" when multiple API requests fail simultaneously.
 * Features:
 * - Deduplicates identical messages within a time window
 * - Limits total notifications per window
 * - Different strategies for different error types (network, validation, server, rate_limit)
 * - Collapses overflow into summary notification
 */

import { message } from 'antd'
import type { ErrorType, ParsedError } from './errorParser'

interface MessageConfig {
  /** Deduplication window in milliseconds (default: 2000) */
  dedupeWindow: number
  /** Maximum messages shown per window (default: 3) */
  maxPerWindow: number
  /** Window reset time in milliseconds (default: 5000) */
  windowDuration: number
  /** Longer throttle window for network errors (default: 10000) */
  networkErrorWindow: number
}

const DEFAULT_CONFIG: MessageConfig = {
  dedupeWindow: 2000,
  maxPerWindow: 3,
  windowDuration: 5000,
  networkErrorWindow: 10000, // Network errors shown once per 10s
}

/**
 * Error type handling strategies
 */
interface ErrorStrategy {
  /** Whether to show as toast (false = silent) */
  showToast: boolean
  /** Minimum interval between same type notifications (ms) */
  minInterval: number
  /** Whether to count against window limit */
  countsAgainstLimit: boolean
}

const ERROR_STRATEGIES: Record<ErrorType, ErrorStrategy> = {
  // Network errors: show once per 10s, don't spam when offline
  network: { showToast: true, minInterval: 10000, countsAgainstLimit: false },
  // Timeout errors: similar to network
  timeout: { showToast: true, minInterval: 10000, countsAgainstLimit: false },
  // Rate limit: show once per 30s (user should wait anyway)
  rate_limit: { showToast: true, minInterval: 30000, countsAgainstLimit: false },
  // Validation errors: show normally, user needs to fix input
  validation: { showToast: true, minInterval: 2000, countsAgainstLimit: true },
  // Server errors: show with standard throttling
  server: { showToast: true, minInterval: 2000, countsAgainstLimit: true },
  // Unknown: fallback to standard handling
  unknown: { showToast: true, minInterval: 2000, countsAgainstLimit: true },
}

class ThrottledMessageQueue {
  private config: MessageConfig
  private recentMessages: Map<string, number> = new Map() // message -> timestamp
  private lastErrorTypeShown: Map<ErrorType, number> = new Map() // type -> timestamp
  private windowCount: number = 0
  private windowStart: number = 0
  private pendingCount: number = 0
  private summaryTimeout: ReturnType<typeof setTimeout> | null = null

  constructor(config: Partial<MessageConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Show an error with type-aware throttling/deduplication
   */
  showError(parsed: ParsedError): void {
    const now = Date.now()
    const strategy = ERROR_STRATEGIES[parsed.type]

    // Cleanup old entries
    this.cleanupOldEntries(now)

    // Check type-level throttling (e.g., only show "network error" once per 10s)
    const lastTypeShown = this.lastErrorTypeShown.get(parsed.type)
    if (lastTypeShown && now - lastTypeShown < strategy.minInterval) {
      // This error type was shown recently - skip
      return
    }

    // Check message-level deduplication
    const lastMsgShown = this.recentMessages.get(parsed.message)
    if (lastMsgShown && now - lastMsgShown < this.config.dedupeWindow) {
      return
    }

    // Reset window counter if window expired
    if (now - this.windowStart > this.config.windowDuration) {
      this.windowStart = now
      this.windowCount = 0
      this.pendingCount = 0
    }

    // Check window limit (only for errors that count against limit)
    if (strategy.countsAgainstLimit && this.windowCount >= this.config.maxPerWindow) {
      this.pendingCount++
      this.scheduleSummary()
      return
    }

    // Show the message
    if (strategy.showToast) {
      this.recentMessages.set(parsed.message, now)
      this.lastErrorTypeShown.set(parsed.type, now)
      if (strategy.countsAgainstLimit) {
        this.windowCount++
      }
      message.error(parsed.message)
    }
  }

  /**
   * Legacy: show error message string (without type awareness)
   * @deprecated Use showError(ParsedError) for better error handling
   */
  error(msg: string): void {
    this.showError({ message: msg, type: 'unknown' })
  }

  /**
   * Show a warning message with throttling/deduplication
   */
  warning(msg: string): void {
    const now = Date.now()
    this.cleanupOldEntries(now)

    const lastShown = this.recentMessages.get(msg)
    if (lastShown && now - lastShown < this.config.dedupeWindow) {
      return
    }

    if (now - this.windowStart > this.config.windowDuration) {
      this.windowStart = now
      this.windowCount = 0
    }

    if (this.windowCount >= this.config.maxPerWindow) {
      return // Silently skip warnings when throttled
    }

    this.recentMessages.set(msg, now)
    this.windowCount++
    message.warning(msg)
  }

  private cleanupOldEntries(now: number): void {
    // Cleanup message dedupe map
    const msgCutoff = now - this.config.dedupeWindow
    for (const [msg, timestamp] of this.recentMessages.entries()) {
      if (timestamp < msgCutoff) {
        this.recentMessages.delete(msg)
      }
    }

    // Cleanup type throttle map (use longest interval as cutoff)
    const typeCutoff = now - this.config.networkErrorWindow
    for (const [type, timestamp] of this.lastErrorTypeShown.entries()) {
      if (timestamp < typeCutoff) {
        this.lastErrorTypeShown.delete(type)
      }
    }
  }

  private scheduleSummary(): void {
    if (this.summaryTimeout) return

    this.summaryTimeout = setTimeout(() => {
      if (this.pendingCount > 0) {
        message.error(`${this.pendingCount} more error(s) suppressed`)
        this.pendingCount = 0
      }
      this.summaryTimeout = null
    }, this.config.windowDuration)
  }
}

// Singleton instance with default config
export const throttledMessage = new ThrottledMessageQueue()

// Factory for custom config
export function createThrottledMessage(config: Partial<MessageConfig>): ThrottledMessageQueue {
  return new ThrottledMessageQueue(config)
}
