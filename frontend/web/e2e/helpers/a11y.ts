import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

type A11yScanOptions = {
  include?: string[]
  exclude?: string[]
}

const SERIOUS_IMPACTS = new Set(['serious', 'critical'])

function formatHtmlSnippet(html?: string): string {
  if (!html) return ''
  const oneLine = html.replace(/\s+/g, ' ').trim()
  if (!oneLine) return ''
  return oneLine.length > 160 ? `${oneLine.slice(0, 160)}…` : oneLine
}

/**
 * A11y smoke：只阻断 serious/critical 的 axe violations。
 *
 * 说明：
 * - 目标是作为“生产前门禁”的轻量护栏，避免误报导致 CI 频繁红灯；
 * - 若需要更严格的门禁，可逐步把 moderate 也纳入阻断。
 */
export async function assertNoSeriousA11yViolations(
  page: Page,
  opts: A11yScanOptions = {},
): Promise<void> {
  const builder = new AxeBuilder({ page })
    // 自动化 smoke 里 color-contrast 噪声较高（placeholder/disabled 状态、主题变量等会触发大量误报）。
    // 对比度建议留给人工审查或单独的专项任务。
    .disableRules('color-contrast')

  for (const selector of opts.include ?? []) {
    builder.include(selector)
  }
  for (const selector of opts.exclude ?? []) {
    builder.exclude(selector)
  }

  const results = await builder.analyze()
  const violations = results.violations.filter((v) => v.impact && SERIOUS_IMPACTS.has(v.impact))

  if (violations.length === 0) return

  const lines: string[] = []
  lines.push(`A11y violations (impact: serious/critical): ${violations.length}`)

  for (const v of violations.slice(0, 10)) {
    lines.push(`- [${v.impact}] ${v.id}: ${v.help}`)
    if (v.helpUrl) lines.push(`  helpUrl: ${v.helpUrl}`)
    lines.push(`  nodes: ${v.nodes.length}`)

    const firstNode = v.nodes[0]
    if (!firstNode) continue

    if (firstNode.target?.length) {
      lines.push(`  target: ${firstNode.target.join(' | ')}`)
    }

    const snippet = formatHtmlSnippet(firstNode.html)
    if (snippet) {
      lines.push(`  html: ${snippet}`)
    }

    if (firstNode.failureSummary) {
      lines.push(`  summary: ${firstNode.failureSummary.replace(/\s+/g, ' ').trim()}`)
    }
  }

  if (violations.length > 10) {
    lines.push(`... and ${violations.length - 10} more`)
  }

  throw new Error(lines.join('\n'))
}
