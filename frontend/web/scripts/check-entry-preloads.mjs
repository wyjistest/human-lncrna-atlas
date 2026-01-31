import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

// Budgets (uncompressed bytes; aligns with Vite's chunk size warnings).
const ENTRY_BUDGET_BYTES = 200 * 1024
const PRELOAD_TOTAL_BUDGET_BYTES = 1500 * 1024

const PRELOAD_BUDGETS = [
  { name: 'react-vendor', prefix: '/assets/react-vendor-', maxBytes: 120 * 1024 },
  { name: 'query-vendor', prefix: '/assets/query-vendor-', maxBytes: 120 * 1024 },
  { name: 'i18n-vendor', prefix: '/assets/i18n-vendor-', maxBytes: 200 * 1024 },
  // AntD is expected to be large; budget is intentionally loose to only catch big regressions.
  { name: 'antd-vendor', prefix: '/assets/antd-vendor-', maxBytes: 1500 * 1024 },
]

function readIndexHtml() {
  const distPath = path.join(process.cwd(), 'dist', 'index.html')
  if (!fs.existsSync(distPath)) {
    console.error(`[preload-check] Missing build output: ${distPath}`)
    console.error('[preload-check] Run: npm run build')
    process.exit(1)
  }
  return fs.readFileSync(distPath, 'utf-8')
}

function extractEntryModuleSrc(html) {
  const re = /<script\s+[^>]*type="module"[^>]*src="([^"]+)"[^>]*><\/script>/i
  const match = re.exec(html)
  return match ? match[1] : undefined
}

function extractModulepreloadHrefs(html) {
  const hrefs = []
  const re = /<link\s+[^>]*rel="modulepreload"[^>]*href="([^"]+)"[^>]*>/g
  let match
  while ((match = re.exec(html)) !== null) {
    hrefs.push(match[1])
  }
  return hrefs
}

function isAllowedPreload(href) {
  // We allow only core vendors on the first paint.
  // Any heavy, route-lazy vendor should NOT be modulepreloaded by dist/index.html.
  return PRELOAD_BUDGETS.some((b) => href.startsWith(b.prefix))
}

function formatKib(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`
}

function resolveDistPath(href) {
  const rel = href.startsWith('/') ? href.slice(1) : href
  return path.join(process.cwd(), 'dist', rel)
}

function fileSizeBytes(filePath) {
  return fs.statSync(filePath).size
}

function gzipSizeBytes(filePath) {
  const buf = fs.readFileSync(filePath)
  return zlib.gzipSync(buf).length
}

function failBudget(reason, details) {
  console.error(`[preload-check] ${reason}`)
  if (details) console.error(details)
  process.exit(1)
}

const html = readIndexHtml()
const hrefs = extractModulepreloadHrefs(html)

const disallowed = hrefs.filter((h) => !isAllowedPreload(h))
if (disallowed.length > 0) {
  console.error('[preload-check] Disallowed modulepreload entries found in dist/index.html:')
  for (const href of disallowed) {
    console.error(`- ${href}`)
  }
  console.error('')
  console.error('[preload-check] Allowed modulepreload entries are limited to:')
  for (const b of PRELOAD_BUDGETS) {
    console.error(`- ${b.prefix}*`)
  }
  process.exit(1)
}

const entrySrc = extractEntryModuleSrc(html)
if (!entrySrc) {
  failBudget('Missing entry <script type="module" ... src="..."> in dist/index.html')
}
if (!entrySrc.startsWith('/assets/')) {
  failBudget(`Unexpected entry src: ${entrySrc}`, 'Expected it to start with /assets/.')
}

const entryPath = resolveDistPath(entrySrc)
if (!fs.existsSync(entryPath)) {
  failBudget(`Missing entry bundle file: ${entryPath}`)
}

const entryBytes = fileSizeBytes(entryPath)
const entryGzipBytes = gzipSizeBytes(entryPath)
if (entryBytes > ENTRY_BUDGET_BYTES) {
  failBudget(
    `Entry bundle exceeds budget (${formatKib(entryBytes)} > ${formatKib(ENTRY_BUDGET_BYTES)}): ${entrySrc}`
  )
}

let preloadTotalBytes = 0
let preloadTotalGzipBytes = 0
for (const href of hrefs) {
  const budget = PRELOAD_BUDGETS.find((b) => href.startsWith(b.prefix))
  if (!budget) continue

  const filePath = resolveDistPath(href)
  if (!fs.existsSync(filePath)) {
    failBudget(`Missing preloaded file: ${filePath}`)
  }

  const sizeBytes = fileSizeBytes(filePath)
  const gzBytes = gzipSizeBytes(filePath)
  preloadTotalBytes += sizeBytes
  preloadTotalGzipBytes += gzBytes

  if (sizeBytes > budget.maxBytes) {
    failBudget(
      `Preloaded chunk exceeds budget (${formatKib(sizeBytes)} > ${formatKib(budget.maxBytes)}): ${href}`
    )
  }
}

if (preloadTotalBytes > PRELOAD_TOTAL_BUDGET_BYTES) {
  failBudget(
    `Preloaded total exceeds budget (${formatKib(preloadTotalBytes)} > ${formatKib(PRELOAD_TOTAL_BUDGET_BYTES)})`
  )
}

console.log(`[preload-check] OK (${hrefs.length} modulepreload link(s))`)
console.log(`[preload-check] entry: ${path.basename(entryPath)} = ${formatKib(entryBytes)} (gz ${formatKib(entryGzipBytes)})`)
console.log(`[preload-check] preloads: total = ${formatKib(preloadTotalBytes)} (gz ${formatKib(preloadTotalGzipBytes)})`)
