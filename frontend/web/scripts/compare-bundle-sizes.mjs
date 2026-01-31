import fs from 'node:fs'
import path from 'node:path'

function usage() {
  return [
    'Usage:',
    '  node scripts/compare-bundle-sizes.mjs <baseline.json> <current.json> [options]',
    '',
    'Options:',
    '  --top <n>       Show top N chunks (default: 10)',
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

function delta(baselineValue, currentValue) {
  if (!Number.isFinite(baselineValue) || !Number.isFinite(currentValue)) return null
  return currentValue - baselineValue
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
}

main()

