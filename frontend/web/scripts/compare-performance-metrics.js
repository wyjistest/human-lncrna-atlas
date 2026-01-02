import fs from 'node:fs'
import path from 'node:path'

function usage() {
  return [
    'Usage:',
    '  node scripts/compare-performance-metrics.js --baseline <file> --current <file> [options]',
    '',
    'Options:',
    '  --out <file>                 Write report to a file (also prints to stdout)',
    '  --fail-on-regression         Exit non-zero if regressions exceed threshold',
    '  --regression-threshold <pct> Regression threshold percent (default: 10)',
    '',
    'Examples:',
    '  node scripts/compare-performance-metrics.js --baseline performance-baseline-metrics.json --current test-results/performance-latest-metrics.json',
    '  node scripts/compare-performance-metrics.js --baseline performance-baseline-metrics.json --current test-results/performance-latest-metrics.json --fail-on-regression',
  ].join('\n')
}

function parseArgs(argv) {
  const args = {
    baseline: undefined,
    current: undefined,
    out: undefined,
    failOnRegression: false,
    regressionThresholdPercent: 10,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i]
    if (token === '--baseline') {
      args.baseline = argv[i + 1]
      i += 1
      continue
    }
    if (token === '--current') {
      args.current = argv[i + 1]
      i += 1
      continue
    }
    if (token === '--out') {
      args.out = argv[i + 1]
      i += 1
      continue
    }
    if (token === '--fail-on-regression') {
      args.failOnRegression = true
      continue
    }
    if (token === '--regression-threshold') {
      const raw = argv[i + 1]
      i += 1
      const parsed = raw ? Number(raw) : NaN
      if (!Number.isFinite(parsed) || parsed < 0) {
        throw new Error(`Invalid --regression-threshold: ${raw}`)
      }
      args.regressionThresholdPercent = parsed
      continue
    }
    if (token === '-h' || token === '--help') {
      console.log(usage())
      process.exit(0)
    }
    throw new Error(`Unknown argument: ${token}\n\n${usage()}`)
  }

  return args
}

function readJsonFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8')
  return JSON.parse(raw)
}

function toNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function getNumberByPath(obj, dotPath) {
  const parts = dotPath.split('.')
  let cur = obj
  for (const part of parts) {
    if (cur == null || typeof cur !== 'object' || !(part in cur)) return undefined
    cur = cur[part]
  }
  return toNumber(cur)
}

function formatPct(value) {
  if (!Number.isFinite(value)) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function improvementPercent(baseline, current, higherIsBetter) {
  if (!Number.isFinite(baseline) || baseline === 0) return undefined
  if (!Number.isFinite(current)) return undefined
  if (higherIsBetter) {
    return ((current - baseline) / baseline) * 100
  }
  return ((baseline - current) / baseline) * 100
}

function isRegression(baseline, current, higherIsBetter, thresholdPercent) {
  if (!Number.isFinite(baseline) || baseline === 0) return false
  if (!Number.isFinite(current)) return false
  const threshold = thresholdPercent / 100
  if (higherIsBetter) {
    return current < baseline * (1 - threshold)
  }
  return current > baseline * (1 + threshold)
}

function padRight(text, width) {
  const s = String(text)
  return s.length >= width ? s : s + ' '.repeat(width - s.length)
}

function padLeft(text, width) {
  const s = String(text)
  return s.length >= width ? s : ' '.repeat(width - s.length) + s
}

function buildReport(baseline, current, options) {
  const items = [
    { path: 'critical_metrics.api_response_time.value_ms', label: 'API 响应时间 (ms)', higherIsBetter: false },
    { path: 'critical_metrics.cache_performance.cold_cache_time_ms', label: '冷缓存耗时 (ms)', higherIsBetter: false },
    { path: 'critical_metrics.cache_performance.warm_cache_time_ms', label: '热缓存耗时 (ms)', higherIsBetter: false },
    { path: 'critical_metrics.cache_performance.cache_hit_rate_percent', label: '缓存命中率 (%)', higherIsBetter: true },
    { path: 'critical_metrics.cache_performance.average_hit_time_ms', label: '平均命中耗时 (ms)', higherIsBetter: false },
    { path: 'critical_metrics.cache_performance.average_miss_time_ms', label: '平均未命中耗时 (ms)', higherIsBetter: false },
    { path: 'test_results.pass_rate_percent', label: '测试通过率 (%)', higherIsBetter: true },
  ]

  const rows = []
  const regressions = []

  for (const item of items) {
    const b = getNumberByPath(baseline, item.path)
    const c = getNumberByPath(current, item.path)
    if (b === undefined || c === undefined) continue

    const imp = improvementPercent(b, c, item.higherIsBetter)
    const reg = isRegression(b, c, item.higherIsBetter, options.regressionThresholdPercent)

    rows.push({
      label: item.label,
      path: item.path,
      baseline: b,
      current: c,
      improvement: imp,
      regression: reg,
    })

    if (reg) regressions.push(item.label)
  }

  const baselineDate = baseline?.test_date ? String(baseline.test_date) : 'N/A'
  const currentDate = current?.test_date ? String(current.test_date) : 'N/A'

  const lines = []
  lines.push('Performance Metrics Comparison')
  lines.push('='.repeat(80))
  lines.push(`Baseline: ${baselineDate}`)
  lines.push(`Current : ${currentDate}`)
  lines.push(`Regression threshold: ${options.regressionThresholdPercent}%`)
  lines.push('')

  if (rows.length === 0) {
    lines.push('No comparable numeric metrics found between baseline and current reports.')
    lines.push('')
  } else {
    const colMetric = 28
    const colBase = 14
    const colCurr = 14
    const colChange = 12
    const colStatus = 10

    lines.push(
      [
        padRight('Metric', colMetric),
        padLeft('Baseline', colBase),
        padLeft('Current', colCurr),
        padLeft('Change', colChange),
        padRight('Status', colStatus),
      ].join(' | ')
    )
    lines.push('-'.repeat(80))

    for (const row of rows) {
      const status = row.regression ? 'REGRESSION' : 'OK'
      lines.push(
        [
          padRight(row.label, colMetric),
          padLeft(row.baseline.toFixed(2), colBase),
          padLeft(row.current.toFixed(2), colCurr),
          padLeft(row.improvement === undefined ? 'N/A' : formatPct(row.improvement), colChange),
          padRight(status, colStatus),
        ].join(' | ')
      )
    }

    lines.push('-'.repeat(80))
    if (regressions.length > 0) {
      lines.push(`Regressions: ${regressions.join(', ')}`)
    } else {
      lines.push('Regressions: none')
    }
    lines.push('')
  }

  return { text: lines.join('\n'), regressions }
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  if (!args.baseline || !args.current) {
    console.error(usage())
    process.exit(2)
  }

  const baselinePath = path.resolve(process.cwd(), args.baseline)
  const currentPath = path.resolve(process.cwd(), args.current)
  const baseline = readJsonFile(baselinePath)
  const current = readJsonFile(currentPath)

  const { text, regressions } = buildReport(baseline, current, {
    regressionThresholdPercent: args.regressionThresholdPercent,
  })

  console.log(text)

  if (args.out) {
    const outPath = path.resolve(process.cwd(), args.out)
    fs.mkdirSync(path.dirname(outPath), { recursive: true })
    fs.writeFileSync(outPath, text + '\n', 'utf8')
  }

  if (args.failOnRegression && regressions.length > 0) {
    process.exit(1)
  }
}

main()
