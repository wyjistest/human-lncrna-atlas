import fs from 'node:fs'
import path from 'node:path'

function readIndexHtml() {
  const distPath = path.join(process.cwd(), 'dist', 'index.html')
  if (!fs.existsSync(distPath)) {
    console.error(`[preload-check] Missing build output: ${distPath}`)
    console.error('[preload-check] Run: npm run build')
    process.exit(1)
  }
  return fs.readFileSync(distPath, 'utf-8')
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
  const allowedPrefixes = [
    '/assets/react-vendor-',
    '/assets/query-vendor-',
    '/assets/i18n-vendor-',
    '/assets/antd-vendor-',
  ]
  return allowedPrefixes.some((p) => href.startsWith(p))
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
  console.error('- /assets/react-vendor-*')
  console.error('- /assets/query-vendor-*')
  console.error('- /assets/i18n-vendor-*')
  console.error('- /assets/antd-vendor-*')
  process.exit(1)
}

console.log(`[preload-check] OK (${hrefs.length} modulepreload link(s))`)
