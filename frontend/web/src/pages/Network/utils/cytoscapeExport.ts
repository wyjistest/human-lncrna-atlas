import cytoscape from 'cytoscape'

/** PNG export options for Cytoscape */
export interface CytoscapePngOptions {
  output?: 'blob' | 'base64' | 'base64uri'
  bg?: string
  full?: boolean
  scale?: number
  maxWidth?: number
  maxHeight?: number
}

function dataUrlToBlob(dataUrl: string): Blob {
  if (typeof Blob === 'undefined') {
    throw new Error('Blob is not available in this environment')
  }

  const [header, data] = dataUrl.split(',')
  if (!header || data === undefined) {
    throw new Error('Invalid data URL')
  }

  const mimeMatch = header.match(/^data:([^;]*)(;base64)?/i)
  const mimeType = mimeMatch?.[1] || 'application/octet-stream'
  const isBase64 = header.toLowerCase().includes(';base64')

  const binary = isBase64 ? atob(data) : decodeURIComponent(data)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: mimeType })
}

export function exportCytoscapePngBlob(
  cy: cytoscape.Core,
  options: CytoscapePngOptions
): Blob {
  const blobOptions: CytoscapePngOptions & { output: 'blob' } = {
    ...options,
    output: 'blob',
  }

  const raw: unknown = cy.png(blobOptions)

  if (typeof Blob !== 'undefined' && raw instanceof Blob) {
    return raw
  }
  if (typeof raw === 'string') {
    return dataUrlToBlob(raw)
  }

  throw new Error('Unexpected Cytoscape PNG export type')
}

