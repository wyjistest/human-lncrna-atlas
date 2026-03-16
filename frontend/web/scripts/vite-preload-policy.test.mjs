import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const viteConfigPath = path.join(process.cwd(), 'vite.config.ts')
const viteConfigSource = fs.readFileSync(viteConfigPath, 'utf-8')

test('html entry preload allowlist does not include Ant Design vendor chunk', () => {
  const allowedPrefixesMatch = viteConfigSource.match(
    /const allowedPrefixes = \[(?<block>[\s\S]*?)\n\s*\]/,
  )

  assert.ok(allowedPrefixesMatch?.groups?.block, 'Expected to find allowedPrefixes block')
  assert.doesNotMatch(
    allowedPrefixesMatch.groups.block,
    /antd-vendor/,
    'Ant Design vendor should stay lazy and not be modulepreloaded from index.html',
  )
})

test('non-html hosts still return original dependencies', () => {
  assert.match(
    viteConfigSource,
    /if \(hostType !== 'html'\)\s*\{\s*return deps\s*\}/,
    'Expected non-html preload resolution to preserve dependency lists',
  )
})
