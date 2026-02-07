import fs from 'node:fs'
import path from 'node:path'

function usage() {
  return [
    'Usage:',
    '  node scripts/compare-bundle-sizes.mjs <baseline.json> <current.json> [options]',
    '',
    'Options:',
    '  --top <n>       Show top N chunks (default: 10)',
    '  --max-entry-regression-pct <n>     Fail if entry.gzipBytes regresses by more than N% (default: 2)',
    '  --max-preloads-regression-pct <n>  Fail if modulepreload gzip total regresses by more than N% (default: 2)',
    '  -h, --help      Show help',
    '',
    'Notes:',
    '  - This script compares two JSON snapshots produced by report-bundle-sizes.mjs --json ...',
    '  - It focuses on stable signals (entry/modulepreload/manualChunks) for evidence-driven triage.',
  ].join('\n')
}

function parseArgs(argv) {
  const args = {
    baseline: '',
    current: '',
    top: 10,
    maxEntryRegressionPct: 2,
    maxPreloadsRegressionPct: 2,
  }

  const positional = []
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i]
    if (token === '--top') {
      const raw = argv[i + 1]
      i += 1
      const parsed = raw ? Number(raw) : NaN
      if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error(`Invalid --top: ${raw}`)
      }
      args.top = parsed
      continue
    }
    if (token === '--max-entry-regression-pct') {
      const raw = argv[i + 1]
      i += 1
      const parsed = raw ? Number(raw) : NaN
      if (!Number.isFinite(parsed) || parsed < 0) {
        throw new Error(`Invalid --max-entry-regression-pct: ${raw}`)
      }
      args.maxEntryRegressionPct = parsed
      continue
    }
    if (token === '--max-preloads-regression-pct') {
      const raw = argv[i + 1]
      i += 1
      const parsed = raw ? Number(raw) : NaN
      if (!Number.isFinite(parsed) || parsed < 0) {
        throw new Error(`Invalid --max-preloads-regression-pct: ${raw}`)
      }
      args.maxPreloadsRegressionPct = parsed
      continue
    }
    if (token === '-h' || token === '--help') {
      console.log(usage())
      process.exit(0)
    }
    if (token.startsWith('-')) {
      throw new Error(`Unknown argument: ${token}\n\n${usage()}`)
    }
    positional.push(token)
  }

  if (positional.length !== 2) {
    throw new Error(`Expected 2 positional args (baseline.json, current.json)\n\n${usage()}`)
  }

  args.baseline = positional[0]
  args.current = positional[1]
  return args
}

function readJson(filePath) {
  const text = fs.readFileSync(filePath, 'utf8')
  return JSON.parse(text)
}

function formatKib(bytes) {
  if (!Number.isFinite(bytes)) return '-'
  return `${(bytes / 1024).toFixed(1)} kB`
}

function formatDeltaKib(deltaBytes) {
  if (!Number.isFinite(deltaBytes)) return '-'
  const sign = deltaBytes > 0 ? '+' : ''
  return `${sign}${(deltaBytes / 1024).toFixed(1)} kB`
}

function formatPct(pct) {
  if (!Number.isFinite(pct)) return '-'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

function delta(baselineValue, currentValue) {
  if (!Number.isFinite(baselineValue) || !Number.isFinite(currentValue)) return null
  return currentValue - baselineValue
}

function pctDelta(baselineValue, currentValue) {
  if (!Number.isFinite(baselineValue) || !Number.isFinite(currentValue)) return null
  if (baselineValue === 0) {
    return currentValue === 0 ? 0 : null
  }
  return ((currentValue - baselineValue) / baselineValue) * 100
}

function sumBytes(list) {
  if (!Array.isArray(list)) return 0
  let total = 0
  for (const it of list) {
    if (it && Number.isFinite(it.bytes)) total += it.bytes
  }
  return total
}

function sumGzipBytes(list) {
  if (!Array.isArray(list)) return 0
  let total = 0
  for (const it of list) {
    if (it && Number.isFinite(it.gzipBytes)) total += it.gzipBytes
  }
  return total
}

function findChunkFamily(snapshot, family) {
  const assets = Array.isArray(snapshot.assets) ? snapshot.assets : []
  const matches = assets.filter((a) => {
    if (!a || typeof a.file !== 'string') return false
    return a.file.startsWith(`${family}-`) && a.file.endsWith('.js')
  })
  if (matches.length === 0) return null
  return matches.reduce((best, it) => (it.bytes > best.bytes ? it : best), matches[0])
}

function stableKeyFromFile(file) {
  if (typeof file !== 'string' || !file) return ''

  const families = [
    'react-vendor',
    'query-vendor',
    'i18n-vendor',
    'antd-vendor',
    'echarts-core',
    'echarts-react',
    'cytoscape-vendor',
    'igv-vendor',
    'file-vendor',
    'pdf-vendor',
    'zip-vendor',
  ]

  for (const family of families) {
    if (file.startsWith(`${family}-`) && file.endsWith('.js')) {
      return family
    }
  }

  const withoutExt = file.endsWith('.js') ? file.slice(0, -3) : file
  const lastDash = withoutExt.lastIndexOf('-')
  if (lastDash <= 0) return withoutExt
  return withoutExt.slice(0, lastDash)
}

function summarizeModulePreloads(snapshot) {
  const list = Array.isArray(snapshot.modulePreloads) ? snapshot.modulePreloads : []
  const byKey = new Map()

  for (const it of list) {
    if (!it || typeof it.file !== 'string') continue
    const key = stableKeyFromFile(it.file)
    if (!key) continue

    const prev = byKey.get(key) || { key, bytes: 0, gzipBytes: 0, file: it.file }
    byKey.set(key, {
      key,
      file: prev.file || it.file,
      bytes: prev.bytes + (Number.isFinite(it.bytes) ? it.bytes : 0),
      gzipBytes: prev.gzipBytes + (Number.isFinite(it.gzipBytes) ? it.gzipBytes : 0),
    })
  }

  return byKey
}

function regressionGate(label, baselineValue, currentValue, maxPct) {
  const baseOk = Number.isFinite(baselineValue)
  const curOk = Number.isFinite(currentValue)
  if (!baseOk || !curOk) {
    return {
      label,
      baselineValue,
      currentValue,
      maxPct,
      status: 'FAIL',
      pct: null,
      reason: 'missing_value',
    }
  }

  if (baselineValue === 0) {
    if (currentValue === 0) {
      return { label, baselineValue, currentValue, maxPct, status: 'PASS', pct: 0, reason: null }
    }
    return { label, baselineValue, currentValue, maxPct, status: 'FAIL', pct: null, reason: 'baseline_zero' }
  }

  const pct = ((currentValue - baselineValue) / baselineValue) * 100
  if (pct > maxPct) {
    return { label, baselineValue, currentValue, maxPct, status: 'FAIL', pct, reason: 'regression' }
  }
  return { label, baselineValue, currentValue, maxPct, status: 'PASS', pct, reason: null }
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  const baselinePath = path.resolve(process.cwd(), args.baseline)
  const currentPath = path.resolve(process.cwd(), args.current)

  const baseline = readJson(baselinePath)
  const current = readJson(currentPath)

  if (baseline.schemaVersion !== 1 || current.schemaVersion !== 1) {
    throw new Error('Unsupported snapshot schemaVersion (expected 1)')
  }

  console.log(
    `[bundle-size-diff] baseline=${path.relative(process.cwd(), baselinePath)} current=${path.relative(process.cwd(), currentPath)}`
  )

  const bEntry = baseline.entry || {}
  const cEntry = current.entry || {}
  const entryDelta = delta(bEntry.bytes, cEntry.bytes)
  const entryGzDelta = delta(bEntry.gzipBytes, cEntry.gzipBytes)

  console.log(
    `Entry: ${formatKib(bEntry.bytes)} (gz ${formatKib(bEntry.gzipBytes)}) -> ` +
      `${formatKib(cEntry.bytes)} (gz ${formatKib(cEntry.gzipBytes)}) ` +
      `(delta ${formatDeltaKib(entryDelta)}, gz delta ${formatDeltaKib(entryGzDelta)})`
  )

  const bPreBytes = sumBytes(baseline.modulePreloads)
  const cPreBytes = sumBytes(current.modulePreloads)
  const bPreGz = sumGzipBytes(baseline.modulePreloads)
  const cPreGz = sumGzipBytes(current.modulePreloads)

  console.log(
    `Modulepreload total: ${formatKib(bPreBytes)} (gz ${formatKib(bPreGz)}) -> ` +
      `${formatKib(cPreBytes)} (gz ${formatKib(cPreGz)}) ` +
      `(delta ${formatDeltaKib(cPreBytes - bPreBytes)}, gz delta ${formatDeltaKib(cPreGz - bPreGz)})`
  )

  console.log('')
  console.log('Chunk families (manualChunks):')

  const families = [
    'react-vendor',
    'query-vendor',
    'i18n-vendor',
    'antd-vendor',
    'echarts-core',
    'echarts-react',
    'cytoscape-vendor',
    'igv-vendor',
    'file-vendor',
    'pdf-vendor',
    'zip-vendor',
  ]

  for (const family of families) {
    const b = findChunkFamily(baseline, family) || {}
    const c = findChunkFamily(current, family) || {}
    const dBytes = delta(b.bytes, c.bytes)
    const dGz = delta(b.gzipBytes, c.gzipBytes)

    console.log(
      `${family}: ${formatKib(b.bytes)} (gz ${formatKib(b.gzipBytes)}) -> ` +
        `${formatKib(c.bytes)} (gz ${formatKib(c.gzipBytes)}) ` +
        `(delta ${formatDeltaKib(dBytes)}, gz delta ${formatDeltaKib(dGz)})`
    )
  }

  console.log('')
  console.log(`Top JS chunks in current snapshot (top=${args.top})`)

  const assets = Array.isArray(current.assets) ? current.assets : []
  const byBytes = [...assets].sort((a, b) => (b.bytes || 0) - (a.bytes || 0))
  const top = byBytes.slice(0, args.top)
  for (let i = 0; i < top.length; i += 1) {
    const it = top[i]
    console.log(`${i + 1}. ${it.file} ${formatKib(it.bytes)} (gz ${formatKib(it.gzipBytes)})`)
  }

  const gates = [
    regressionGate('entry.gzipBytes', bEntry.gzipBytes, cEntry.gzipBytes, args.maxEntryRegressionPct),
    regressionGate('modulepreload.gzipBytesTotal', bPreGz, cPreGz, args.maxPreloadsRegressionPct),
  ]

  const failed = gates.filter((g) => g.status !== 'PASS')
  const thresholdLine = `[bundle-size-gate] thresholds: entry<=${args.maxEntryRegressionPct}% modulepreload<=${args.maxPreloadsRegressionPct}%`
  console.log('')
  console.log(thresholdLine)
  for (const g of gates) {
    const d = delta(g.baselineValue, g.currentValue)
    const pct = pctDelta(g.baselineValue, g.currentValue)
    const baselineStr = Number.isFinite(g.baselineValue) ? `${g.baselineValue} B` : '-'
    const currentStr = Number.isFinite(g.currentValue) ? `${g.currentValue} B` : '-'
    const status = g.status
    console.log(
      `[bundle-size-gate] ${g.label}: baseline=${baselineStr} current=${currentStr} ` +
        `delta=${d === null ? '-' : `${d > 0 ? '+' : ''}${d} B`} (${formatPct(pct)}) => ${status}`
    )
  }

  if (failed.length > 0) {
    console.log('')
    console.log('[bundle-size-gate] Modulepreload gzip delta by chunk key (top=10):')

    const bMap = summarizeModulePreloads(baseline)
    const cMap = summarizeModulePreloads(current)
    const keys = new Set([...bMap.keys(), ...cMap.keys()])
    const rows = []
    for (const key of keys) {
      const b = bMap.get(key) || { gzipBytes: 0, bytes: 0 }
      const c = cMap.get(key) || { gzipBytes: 0, bytes: 0 }
      const dGz = (Number.isFinite(c.gzipBytes) ? c.gzipBytes : 0) - (Number.isFinite(b.gzipBytes) ? b.gzipBytes : 0)
      const p = pctDelta(b.gzipBytes, c.gzipBytes)
      rows.push({ key, bGz: b.gzipBytes, cGz: c.gzipBytes, dGz, pct: p })
    }
    rows.sort((a, b) => (b.dGz || 0) - (a.dGz || 0) || a.key.localeCompare(b.key))
    for (const row of rows.slice(0, 10)) {
      console.log(
        `- ${row.key}: gz ${formatKib(row.bGz)} -> ${formatKib(row.cGz)} ` +
          `(gz delta ${formatDeltaKib(row.dGz)}, pct ${formatPct(row.pct)})`
      )
    }

    process.exit(1)
  }
}

main()
