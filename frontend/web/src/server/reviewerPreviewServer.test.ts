import http from 'node:http'
import { once } from 'node:events'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { createReviewerPreviewServer } from '../../scripts/reviewer-preview-server.mjs'

type RunningServer = {
  server: http.Server
  baseUrl: string
}

async function listen(server: http.Server): Promise<RunningServer> {
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  if (!address || typeof address === 'string') {
    throw new Error('无法获取监听端口')
  }
  return {
    server,
    baseUrl: `http://127.0.0.1:${address.port}`,
  }
}

describe('reviewer preview server', () => {
  let tempDir = ''
  let upstream: RunningServer | null = null
  let preview: RunningServer | null = null

  beforeEach(async () => {
    tempDir = await mkdtemp(path.join(os.tmpdir(), 'reviewer-preview-'))
    await mkdir(path.join(tempDir, 'assets'))
    await writeFile(path.join(tempDir, 'index.html'), '<html><body>snapshot shell</body></html>')
    await writeFile(path.join(tempDir, 'assets', 'app.js'), 'console.log("preview")')

    upstream = await listen(
      http.createServer((req, res) => {
        if (req.url === '/api/v1/ping') {
          res.writeHead(200, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ ok: true }))
          return
        }

        if (req.url === '/health') {
          res.writeHead(200, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ status: 'ok' }))
          return
        }

        if (req.url === '/genomes/demo.txt') {
          res.writeHead(200, { 'content-type': 'text/plain' })
          res.end('genome-demo')
          return
        }

        res.writeHead(404)
        res.end('missing')
      }),
    )

    preview = await listen(
      createReviewerPreviewServer({
        distDir: tempDir,
        apiTarget: upstream.baseUrl,
      }),
    )
  })

  afterEach(async () => {
    await preview?.server.closeAllConnections()
    await upstream?.server.closeAllConnections()
    await new Promise((resolve) => preview?.server.close(resolve))
    await new Promise((resolve) => upstream?.server.close(resolve))
    if (tempDir) {
      await rm(tempDir, { recursive: true, force: true })
    }
  })

  it('提供已构建的静态资源', async () => {
    const response = await fetch(`${preview!.baseUrl}/assets/app.js`)

    expect(response.status).toBe(200)
    expect(await response.text()).toContain('console.log("preview")')
  })

  it('对子路由返回 index.html 作为 SPA fallback', async () => {
    const response = await fetch(`${preview!.baseUrl}/snapshot`)

    expect(response.status).toBe(200)
    expect(await response.text()).toContain('snapshot shell')
  })

  it('代理 api、health 和 genomes 请求到后端', async () => {
    const apiResponse = await fetch(`${preview!.baseUrl}/api/v1/ping`)
    const healthResponse = await fetch(`${preview!.baseUrl}/health`)
    const genomesResponse = await fetch(`${preview!.baseUrl}/genomes/demo.txt`)

    expect(apiResponse.status).toBe(200)
    expect(await apiResponse.json()).toEqual({ ok: true })
    expect(healthResponse.status).toBe(200)
    expect(await healthResponse.json()).toEqual({ status: 'ok' })
    expect(genomesResponse.status).toBe(200)
    expect(await genomesResponse.text()).toBe('genome-demo')
  })

  it('阻止读取 dist 目录外的文件', async () => {
    const response = await fetch(`${preview!.baseUrl}/%2e%2e/package.json`)

    expect(response.status).toBe(404)
  })
})
