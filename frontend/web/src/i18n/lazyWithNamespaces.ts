import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

import { ensureNamespaces, type TranslationNamespace } from './index'

type LazyModule<TProps extends object> = { default: ComponentType<TProps> }

export function lazyWithNamespaces<TProps extends object>(
  importer: () => Promise<LazyModule<TProps>>,
  namespaces: TranslationNamespace | readonly TranslationNamespace[],
): LazyExoticComponent<ComponentType<TProps>> {
  const namespaceList = Array.isArray(namespaces) ? [...namespaces] : [namespaces]

  return lazy(async () => {
    await ensureNamespaces(namespaceList)
    return importer()
  })
}
