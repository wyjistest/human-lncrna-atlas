import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock window.matchMedia (required by Antd)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock window.scrollTo
Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: vi.fn(),
})

// Mock ResizeObserver
class ResizeObserverMock {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
window.ResizeObserver = ResizeObserverMock

// Mock getComputedStyle (Antd needs this)
const originalGetComputedStyle = window.getComputedStyle
window.getComputedStyle = (element: Element) => {
  if (!element) {
    return {} as CSSStyleDeclaration
  }
  return originalGetComputedStyle(element)
}
