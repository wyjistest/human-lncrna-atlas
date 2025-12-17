import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Suppress JSDOM CSS parsing errors (Antd CSS-in-JS compatibility issue)
// These errors occur because JSDOM doesn't support modern CSS features
// They go to stderr directly, bypassing console.error
const originalStderrWrite = process.stderr.write.bind(process.stderr)
process.stderr.write = (chunk: string | Uint8Array, ...args: unknown[]): boolean => {
  const text = typeof chunk === 'string' ? chunk : chunk.toString()
  if (text.includes('Could not parse CSS stylesheet')) {
    return true // Suppress CSS parsing errors
  }
  return originalStderrWrite(chunk, ...(args as []))
}

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

// Mock canvas for ECharts/zrender (JSDOM doesn't support canvas)
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  getImageData: vi.fn().mockReturnValue({ data: [] }),
  putImageData: vi.fn(),
  createImageData: vi.fn().mockReturnValue([]),
  setTransform: vi.fn(),
  drawImage: vi.fn(),
  save: vi.fn(),
  fillText: vi.fn(),
  restore: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  closePath: vi.fn(),
  stroke: vi.fn(),
  fill: vi.fn(),
  translate: vi.fn(),
  scale: vi.fn(),
  rotate: vi.fn(),
  arc: vi.fn(),
  measureText: vi.fn().mockReturnValue({ width: 0 }),
  transform: vi.fn(),
  rect: vi.fn(),
  clip: vi.fn(),
  createLinearGradient: vi.fn().mockReturnValue({
    addColorStop: vi.fn(),
  }),
  createRadialGradient: vi.fn().mockReturnValue({
    addColorStop: vi.fn(),
  }),
  createPattern: vi.fn(),
})

// Mock echarts-for-react globally to prevent canvas issues
vi.mock('echarts-for-react', () => ({
  default: vi.fn().mockImplementation(() => null),
}))

// Mock echarts core to prevent zrender canvas operations
vi.mock('echarts', () => ({
  init: vi.fn().mockReturnValue({
    setOption: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    getOption: vi.fn(),
  }),
  use: vi.fn(),
  registerTheme: vi.fn(),
}))

// Mock echarts/core for treeshaking imports
vi.mock('echarts/core', () => ({
  init: vi.fn().mockReturnValue({
    setOption: vi.fn(),
    dispose: vi.fn(),
    resize: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    getOption: vi.fn(),
  }),
  use: vi.fn(),
}))

