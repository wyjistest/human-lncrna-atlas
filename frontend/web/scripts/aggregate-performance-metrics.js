import fs from 'node:fs'
import path from 'node:path'
import { PERFORMANCE_METRICS_ITEMS } from './performance-metrics-items.js'

function usage() {
  return [
    'Usage:',
    '  node scripts/aggregate-performance-metrics.js --out <file> --inputs <file1> <file2> ...',
    '',
    'Options:',
    '  --out <file>        Write aggregated report JSON to a file',
    '  --inputs <files...> Input JSON report files (>= 1)',
    '',
    'Examples:',
    '  node scripts/aggregate-performance-metrics.js --out test-results/performance-median-metrics.json --inputs test-results/performance-run-1.json test-results/performance-run-2.json test-results/performance-run-3.json',
  ].join('\n')
}

function parseArgs(argv) {
  const args = {
    out: undefined,
    inputs: [],
  }

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i]
    if (token === '--out') {
      args.out = argv[i + 1]
      i += 1
      continue
    }
    if (token === '--inputs') {
      while (i + 1 < argv.length) {
        const next = argv[i + 1]
        if (next.startsWith('--')) break
        args.inputs.push(next)
        i += 1
      }
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

function setNumberByPath(obj, dotPath, value) {
  const parts = dotPath.split('.')
  let cur = obj
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i]
    const isLeaf = i === parts.length - 1
    if (isLeaf) {
      cur[part] = value
      return
    }
    const next = cur[part]
    if (next == null || typeof next !== 'object') {
      cur[part] = {}
    }
    cur = cur[part]
  }
}

function median(values) {
  const nums = values.filter((v) => typeof v === 'number' && Number.isFinite(v)).sort((a, b) => a - b)
  if (nums.length === 0) return undefined
  const mid = Math.floor(nums.length / 2)
  if (nums.length % 2 === 1) return nums[mid]
  return (nums[mid - 1] + nums[mid]) / 2
}

function buildMedianReport(reports, inputPaths) {
  const base = JSON.parse(JSON.stringify(reports[0]))
  base.test_date = new Date().toISOString().slice(0, 10)
  base.aggregation = {
    method: 'median',
    run_count: reports.length,
    inputs: inputPaths.map(String),
  }

  for (const item of PERFORMANCE_METRICS_ITEMS) {
    const values = reports.map((r) => getNumberByPath(r, item.path)).filter((v) => v !== undefined)
    const m = median(values)
    if (m === undefined) continue
    setNumberByPath(base, item.path, m)
  }

  return base
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  if (!args.out || args.inputs.length < 1) {
    console.error(usage())
    process.exit(2)
  }

  const outPath = path.resolve(process.cwd(), args.out)
  const inputPaths = args.inputs.map((p) => path.resolve(process.cwd(), p))

  const reports = inputPaths.map((p) => readJsonFile(p))
  const medianReport = buildMedianReport(reports, args.inputs)

  fs.mkdirSync(path.dirname(outPath), { recursive: true })
  fs.writeFileSync(outPath, JSON.stringify(medianReport, null, 2) + '\n', 'utf8')
  console.log(`Wrote median performance metrics: ${path.relative(process.cwd(), outPath)}`)
}

try {
  main()
} catch (error) {
  console.error(String(error?.message || error))
  process.exit(2)
}

