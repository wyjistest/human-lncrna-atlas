import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

function usage() {
  return [
    'Usage:',
    '  node scripts/report-bundle-sizes.mjs [options]',
    '',
    'Options:',
    '  --dist <dir>    Build output directory (default: dist)',
    '  --top <n>       Show top N chunks (default: 10)',
    '  -h, --help      Show help',
    '',
    'Notes:',
    '  - This script reads dist/assets/*.js and prints the largest chunks (raw + gzip).',
    '  - It is intended for quick, evidence-driven bundle size triage.',
  ].join('\n')
}

function parseArgs(argv) {
  const args = {
    dist: 'dist',
    top: 10,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i]
    if (token === '--dist') {
      args.dist = argv[i + 1] || ''
      i += 1
      continue
    }
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
    throw new Error(`Unknown argument: ${token}\n\n${usage()}`)
  }

  if (!args.dist) {
    throw new Error(`Invalid --dist: ${args.dist}`)
  }

  return args
}

function formatKib(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`
}

function gzipBytes(buffer) {
  return zlib.gzipSync(buffer).length
}

function getJsAssets(distDir) {
  const assetsDir = path.join(distDir, 'assets')
  if (!fs.existsSync(assetsDir)) {
    throw new Error(`Missing assets dir: ${assetsDir}. Run: npm run build`)
  }

  const entries = fs.readdirSync(assetsDir, { withFileTypes: true })
  const files = []
  for (const ent of entries) {
    if (!ent.isFile()) continue
    if (!ent.name.endsWith('.js')) continue
    if (ent.name.endsWith('.js.map')) continue
    files.push(ent.name)
  }

  return files.map((name) => {
    const filePath = path.join(assetsDir, name)
    const buf = fs.readFileSync(filePath)
    return {
      file: name,
      bytes: buf.length,
      gzipBytes: gzipBytes(buf),
    }
  })
}

function printTop(title, items, topN) {
  console.log(title)
  const top = items.slice(0, topN)
  for (let i = 0; i < top.length; i += 1) {
    const it = top[i]
    console.log(`${i + 1}. ${it.file} ${formatKib(it.bytes)} (gz ${formatKib(it.gzipBytes)})`)
  }
  console.log('')
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  const distDir = path.resolve(process.cwd(), args.dist)

  const assets = getJsAssets(distDir)
  if (assets.length === 0) {
    throw new Error(`No JS assets found under: ${path.join(distDir, 'assets')}`)
  }

  const byBytes = [...assets].sort((a, b) => b.bytes - a.bytes)
  const byGzip = [...assets].sort((a, b) => b.gzipBytes - a.gzipBytes)

  console.log(`[bundle-sizes] dist=${path.relative(process.cwd(), distDir) || '.'}`)
  console.log('')

  printTop('Top JS chunks by size', byBytes, args.top)
  printTop('Top JS chunks by gzip size', byGzip, args.top)
}

main()

