import { Suspense } from 'react'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as i18nModule from './index'
import { lazyWithNamespaces } from './lazyWithNamespaces'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('lazyWithNamespaces', () => {
  it('在导入路由模块前先确保对应命名空间已加载', async () => {
    const callOrder: string[] = []

    const ensureNamespacesSpy = vi
      .spyOn(i18nModule, 'ensureNamespaces')
      .mockImplementation(async (namespaces) => {
        const list = Array.isArray(namespaces) ? namespaces : [namespaces]
        callOrder.push(`namespaces:${list.join(',')}`)
      })

    const importer = vi.fn(async () => {
      callOrder.push('importer')
      return {
        default: () => <div>Lazy route ready</div>,
      }
    })

    const LazyRoute = lazyWithNamespaces(importer, ['stats'])

    render(
      <Suspense fallback={<div>Loading route</div>}>
        <LazyRoute />
      </Suspense>,
    )

    expect(screen.getByText('Loading route')).toBeInTheDocument()
    expect(await screen.findByText('Lazy route ready')).toBeInTheDocument()
    expect(ensureNamespacesSpy).toHaveBeenCalledWith(['stats'])
    expect(importer).toHaveBeenCalledTimes(1)
    expect(callOrder).toEqual(['namespaces:stats', 'importer'])
  })
})
