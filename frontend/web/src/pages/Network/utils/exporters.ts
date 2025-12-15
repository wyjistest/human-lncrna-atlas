import { message } from 'antd'
import { saveAs } from 'file-saver'
import type { Core } from 'cytoscape'
import type { NetworkData, NetworkNode, NetworkEdge } from '@/types/network'

/** Translation function type */
type TranslateFn = (key: string, params?: Record<string, unknown>) => string

/**
 * CSV escape function (prevent CSV injection and formula injection)
 * Security measures:
 * 1. Prepend single quote to strings starting with =, +, -, @, \t, \r to prevent formula injection
 * 2. Wrap strings containing comma, double quote, or newline in double quotes
 */
export const escapeCSV = (val: unknown): string => {
  let str = String(val ?? '')

  // Prevent CSV formula injection: Excel/Sheets interprets these as formulas
  if (/^[=+\-@\t\r]/.test(str)) {
    str = "'" + str
  }

  // Handle special characters that need quoting
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * Export network as PNG image
 */
export const exportAsPNG = async (
  cyRef: React.RefObject<Core>,
  speciesName: string,
  t: TranslateFn
) => {
  if (!cyRef.current) {
    message.error(t('export.networkNotLoaded'))
    return
  }

  const messageKey = `png-${speciesName}-${Date.now()}`
  try {
    message.loading({ content: t('export.generating', { species: speciesName, format: 'PNG' }), key: messageKey, duration: 0 })

    // Cytoscape's png() returns Blob when output: 'blob'
    const png = cyRef.current.png({
      output: 'blob',
      bg: 'white',
      full: true,
      scale: 2  // 2x resolution
    }) as unknown as Blob

    const url = URL.createObjectURL(png)
    const a = document.createElement('a')
    a.href = url
    a.download = `network-${speciesName}-${Date.now()}.png`
    a.click()
    URL.revokeObjectURL(url)
    message.success({ content: t('export.success', { species: speciesName, format: 'PNG' }), key: messageKey })
  } catch (error) {
    message.error({ content: t('export.failed', { species: speciesName, format: 'PNG' }), key: messageKey })
    console.error(error)
  }
}

/**
 * Export network as SVG image
 */
export const exportAsSVG = (
  cyRef: React.RefObject<Core>,
  speciesName: string,
  t: TranslateFn
) => {
  if (!cyRef.current) {
    message.error(t('export.networkNotLoaded'))
    return
  }

  const messageKey = `svg-${speciesName}-${Date.now()}`
  message.loading({ content: t('export.generating', { species: speciesName, format: 'SVG' }), key: messageKey, duration: 0 })

  try {
    const svgContent = cyRef.current.svg({
      full: true,
      scale: 2,
      bg: '#ffffff'
    })

    const blob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' })
    saveAs(blob, `network-${speciesName}-${Date.now()}.svg`)
    message.success({ content: t('export.success', { species: speciesName, format: 'SVG' }), key: messageKey })
  } catch (error) {
    console.error('SVG export failed:', error)
    message.error({ content: t('export.failed', { species: speciesName, format: 'SVG' }), key: messageKey })
  }
}

/**
 * Export network data as CSV
 */
export const exportAsCSV = (
  data: NetworkData,
  speciesName: string,
  t: TranslateFn
) => {
  if (!data) {
    message.error(t('export.noData'))
    return
  }

  const messageKey = `csv-${speciesName}-${Date.now()}`
  // Use setTimeout to avoid blocking UI on large graphs
  message.loading({ content: t('export.generating', { species: speciesName, format: 'CSV' }), key: messageKey, duration: 0 })
  setTimeout(() => {
    try {
      // Export nodes (use escapeCSV to prevent injection)
      const nodeHeaders = ['ID', 'Label', 'Type', 'Gene ID', 'Core ID']
      const nodeRows = data.nodes.map((n: NetworkNode) =>
        [escapeCSV(n.id), escapeCSV(n.label), escapeCSV(n.type), escapeCSV(n.gene_id), escapeCSV(n.core_id)].join(',')
      )
      const nodeCSV = [nodeHeaders.join(','), ...nodeRows].join('\n')

      // Export edges (use escapeCSV to prevent injection)
      const edgeHeaders = ['Source', 'Target', 'Binding Affinity', 'Regulation ID']
      const edgeRows = data.edges.map((e: NetworkEdge) =>
        [escapeCSV(e.source), escapeCSV(e.target), escapeCSV(e.binding_affinity), escapeCSV(e.regulation_id)].join(',')
      )
      const edgeCSV = [edgeHeaders.join(','), ...edgeRows].join('\n')

      const csvContent = `Nodes:\n${nodeCSV}\n\nEdges:\n${edgeCSV}`
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `network-data-${speciesName}-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
      message.success({ content: t('export.success', { species: speciesName, format: 'CSV' }), key: messageKey })
    } catch (error) {
      message.error({ content: t('export.failed', { species: speciesName, format: 'CSV' }), key: messageKey })
      console.error(error)
    }
  }, 0)
}

/**
 * Export network data as JSON
 */
export const exportAsJSON = (
  data: NetworkData,
  speciesName: string,
  t: TranslateFn
) => {
  if (!data) {
    message.error(t('export.noData'))
    return
  }

  const messageKey = `json-${speciesName}-${Date.now()}`
  // Use setTimeout to avoid blocking UI on large graphs
  message.loading({ content: t('export.generating', { species: speciesName, format: 'JSON' }), key: messageKey, duration: 0 })
  setTimeout(() => {
    try {
      const jsonContent = JSON.stringify(data, null, 2)
      const blob = new Blob([jsonContent], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `network-data-${speciesName}-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success({ content: t('export.success', { species: speciesName, format: 'JSON' }), key: messageKey })
    } catch (error) {
      message.error({ content: t('export.failed', { species: speciesName, format: 'JSON' }), key: messageKey })
      console.error(error)
    }
  }, 0)
}
