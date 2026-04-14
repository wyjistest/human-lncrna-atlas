import http from 'node:http'
import { Readable } from 'node:stream'
import { access, readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const CONTENT_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp',
}

function getContentType(filePath) {
  return CONTENT_TYPES[path.extname(filePath).toLowerCase()] || 'application/octet-stream'
}

function getRequestUrl(req) {
  return new URL(req.url || '/', 'http://127.0.0.1')
}

function shouldProxy(pathname) {
  return pathname === '/health' || pathname.startsWith('/api/') || pathname === '/genomes' || pathname.startsWith('/genomes/')
}

async function readRequestBody(req) {
  if (req.method === 'GET' || req.method === 'HEAD') {
    return undefined
  }

  const chunks = []
  for await (const chunk of req) {
    chunks.push(chunk)
  }
  return Buffer.concat(chunks)
}

async function proxyRequest(req, res, apiTarget) {
  const requestUrl = getRequestUrl(req)
  const upstreamUrl = new URL(`${requestUrl.pathname}${requestUrl.search}`, apiTarget)
  const body = await readRequestBody(req)
  const headers = new Headers()

  for (const [key, value] of Object.entries(req.headers)) {
    if (value === undefined) {
      continue
    }
    if (Array.isArray(value)) {
      headers.set(key, value.join(', '))
      continue
    }
    headers.set(key, value)
  }

  headers.set('host', upstreamUrl.host)
  headers.set('x-forwarded-host', req.headers.host || '')
  headers.set('x-forwarded-proto', 'http')

  const upstreamResponse = await fetch(upstreamUrl, {
    method: req.method,
    headers,
    body,
    duplex: body ? 'half' : undefined,
  })

  for (const [key, value] of upstreamResponse.headers.entries()) {
    res.setHeader(key, value)
  }

  res.statusCode = upstreamResponse.status

  if (!upstreamResponse.body || req.method === 'HEAD') {
    res.end()
    return
  }

  Readable.fromWeb(upstreamResponse.body).pipe(res)
}

async function resolveStaticFile(distDir, pathname) {
  const decodedPath = decodeURIComponent(pathname)
  const relativePath = decodedPath.replace(/^\/+/, '')
  const normalizedPath = path.normalize(relativePath)
  const candidatePath = path.resolve(distDir, normalizedPath)
  const distRoot = path.resolve(distDir)

  if (!candidatePath.startsWith(distRoot)) {
    return null
  }

  try {
    const fileStat = await stat(candidatePath)
    if (fileStat.isDirectory()) {
      const indexPath = path.join(candidatePath, 'index.html')
      await access(indexPath)
      return indexPath
    }
    if (fileStat.isFile()) {
      return candidatePath
    }
  } catch {
    return null
  }

  return null
}

async function sendFile(res, filePath, method) {
  const content = await readFile(filePath)
  res.statusCode = 200
  res.setHeader('content-type', getContentType(filePath))
  res.setHeader('content-length', Buffer.byteLength(content))
  if (method === 'HEAD') {
    res.end()
    return
  }
  res.end(content)
}

async function handleStaticRequest(req, res, distDir) {
  const { pathname } = getRequestUrl(req)
  const filePath = await resolveStaticFile(distDir, pathname)

  if (filePath) {
    await sendFile(res, filePath, req.method)
    return
  }

  if (path.extname(pathname)) {
    res.statusCode = 404
    res.end('Not Found')
    return
  }

  await sendFile(res, path.join(distDir, 'index.html'), req.method)
}

export function createReviewerPreviewServer({
  distDir = path.resolve(__dirname, '../dist'),
  apiTarget = 'http://127.0.0.1:8010',
} = {}) {
  return http.createServer(async (req, res) => {
    try {
      const { pathname } = getRequestUrl(req)
      if (shouldProxy(pathname)) {
        await proxyRequest(req, res, apiTarget)
        return
      }

      await handleStaticRequest(req, res, distDir)
    } catch (error) {
      res.statusCode = 502
      res.setHeader('content-type', 'text/plain; charset=utf-8')
      res.end(`Preview server error: ${error instanceof Error ? error.message : 'unknown error'}`)
    }
  })
}

function getCliOptions() {
  const port = Number.parseInt(process.env.REVIEWER_PREVIEW_PORT || '6003', 10)
  const host = process.env.REVIEWER_PREVIEW_HOST || '127.0.0.1'
  const distDir = path.resolve(process.env.REVIEWER_PREVIEW_DIST_DIR || path.resolve(__dirname, '../dist'))
  const apiTarget = process.env.REVIEWER_PREVIEW_API_TARGET || 'http://127.0.0.1:8010'
  return { apiTarget, distDir, host, port }
}

async function main() {
  const { apiTarget, distDir, host, port } = getCliOptions()
  const server = createReviewerPreviewServer({ apiTarget, distDir })

  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(port, host, resolve)
  })

  console.log(`reviewer preview server listening on http://${host}:${port}`)
  console.log(`dist=${distDir}`)
  console.log(`apiTarget=${apiTarget}`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
