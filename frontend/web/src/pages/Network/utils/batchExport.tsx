import type React from 'react'
import { message, Modal, Checkbox, Space } from 'antd'
import { saveAs } from 'file-saver'
import type { Core } from 'cytoscape'
import type { NetworkData, NetworkNode, NetworkEdge } from '@/types/network'
import { escapeCSV } from '@/utils/csv'
import { SPECIES_EN_NAMES } from '../types'

/**
 * Generate CSV content from network data
 */
export const generateCSV = (data: NetworkData): string => {
  const nodeHeaders = ['ID', 'Label', 'Type', 'Gene ID', 'Core ID']
  const nodeRows = data.nodes.map((n: NetworkNode) =>
    [escapeCSV(n.id), escapeCSV(n.label), escapeCSV(n.type), escapeCSV(n.gene_id), escapeCSV(n.core_id)].join(',')
  )
  const nodeCSV = [nodeHeaders.join(','), ...nodeRows].join('\n')

  const edgeHeaders = ['Source', 'Target', 'Binding Affinity', 'Regulation ID']
  const edgeRows = data.edges.map((e: NetworkEdge) =>
    [escapeCSV(e.source), escapeCSV(e.target), escapeCSV(e.binding_affinity), escapeCSV(e.regulation_id)].join(',')
  )
  const edgeCSV = [edgeHeaders.join(','), ...edgeRows].join('\n')

  return `Nodes:\n${nodeCSV}\n\nEdges:\n${edgeCSV}`
}

export interface NetworkCardRef {
  cyRef: React.RefObject<Core>
  data: NetworkData | null
  speciesName: string
  isReady: boolean
}

export interface BatchExportOptions {
  speciesIds: number[]
  networkCardsRef: React.MutableRefObject<Map<number, NetworkCardRef>>
  getSpeciesName: (id: number) => string
  traitName?: string
  ontologyName?: string
  t: (key: string, params?: Record<string, unknown>) => string
}

/**
 * Batch export handler for multiple species networks
 * Exports PNG images (merged + individual), CSV, and JSON files to a ZIP archive
 */
export const handleBatchExport = ({
  speciesIds,
  networkCardsRef,
  getSpeciesName,
  traitName = 'unknown',
  ontologyName = 'unknown',
  t
}: BatchExportOptions) => {
  // Validate all species are loaded
  const notReady = speciesIds.filter(id => {
    const card = networkCardsRef.current.get(id)
    return !card || !card.isReady
  })

  if (notReady.length > 0) {
    const notReadyNames = notReady.map(id => getSpeciesName(id)).join(', ')
    message.warning({
      content: t('batchExport.notReady', { count: notReady.length, names: notReadyNames }),
      duration: 4
    })
    return
  }

  let selectedFormats: string[] = ['png', 'csv']

  Modal.confirm({
    title: t('batchExport.title'),
    width: 500,
    content: (
      <div>
        <p style={{ marginBottom: 16 }}>
          {t('batchExport.speciesCount', { count: speciesIds.length })}
        </p>
        <p style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>
          {t('batchExport.diseaseLabel')}: {traitName}<br />
          {t('batchExport.ontologyLabel')}: {ontologyName}
        </p>
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>{t('batchExport.selectFormats')}:</div>
          <Checkbox.Group
            defaultValue={['png', 'csv']}
            onChange={(values) => {
              selectedFormats = values as string[]
            }}
          >
            <Space orientation="vertical">
              <Checkbox value="png">{t('batchExport.pngFormat')}</Checkbox>
              <Checkbox value="csv">{t('batchExport.csvFormat')}</Checkbox>
              <Checkbox value="json">{t('batchExport.jsonFormat')}</Checkbox>
            </Space>
          </Checkbox.Group>
        </div>
        <p style={{ fontSize: 12, color: '#999' }}>
          {t('batchExport.zipNote')}
        </p>
      </div>
    ),
    okText: t('batchExport.startExport'),
    cancelText: t('batchExport.cancel'),
    onOk: async () => {
      // Validate at least one format is selected
      if (selectedFormats.length === 0) {
        message.warning(t('batchExport.selectAtLeastOne'))
        return Promise.reject() // Prevent Modal from closing
      }

      const messageKey = `batch-export-${Date.now()}`

      try {
        message.loading({
          content: t('batchExport.preparing'),
          key: messageKey,
          duration: 0
        })

        // Get ready cards for selected species
        const readyCards = speciesIds
          .map(id => {
            const card = networkCardsRef.current.get(id)
            return card ? [id, card] as [number, typeof card] : null
          })
          .filter((entry): entry is [number, NonNullable<typeof entry>[1]] =>
            entry !== null &&
            entry[1].isReady &&
            !!entry[1].cyRef.current &&
            !!entry[1].data
          )

        if (readyCards.length === 0) {
          message.warning({
            content: t('batchExport.noExportable'),
            key: messageKey
          })
          return
        }

        // 动态导入：只有在批量导出时才加载 jszip，减少 Network 页面首包体积
        const { default: JSZip } = await import('jszip')
        const zip = new JSZip()

        // Generate timestamp for filenames
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
        const safeTraitName = traitName.replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
        const safeOntologyName = ontologyName.replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')

        // ========== PNG Export (merged + individual) ==========
        if (selectedFormats.includes('png')) {
          message.loading({
            content: t('batchExport.generatingImages'),
            key: messageKey,
            duration: 0
          })

          const speciesImages: Array<{
            speciesId: number
            speciesName: string
            imageElement: HTMLImageElement
            objectURL: string
            blob: Blob
            width: number
            height: number
          }> = []

          try {
            // Export PNG for each species
            for (const [speciesId, card] of readyCards) {
              const { cyRef, speciesName } = card
              if (!cyRef.current) continue

              const blob = cyRef.current.png({
                output: 'blob',
                bg: 'white',
                full: true,
                scale: 2
              }) as unknown as Blob

              // Use Object URL instead of base64 (save memory)
              const objectURL = URL.createObjectURL(blob)

              // Create temporary Image to get dimensions
              const img = new Image()
              img.crossOrigin = 'Anonymous'

              await new Promise((resolve, reject) => {
                img.onload = () => resolve(null)
                img.onerror = (error) => {
                  console.error(`Image load failed for ${speciesName}:`, error)
                  URL.revokeObjectURL(objectURL)
                  reject(error)
                }
                img.src = objectURL
              })

              speciesImages.push({
                speciesId,
                speciesName,
                imageElement: img,
                objectURL,
                blob,
                width: img.width,
                height: img.height
              })

              // Give UI thread a break
              await new Promise(resolve => setTimeout(resolve, 0))
            }

            if (speciesImages.length === 0) {
              throw new Error('No exportable images')
            }

            // Add individual images to ZIP first
            for (const { speciesId, blob } of speciesImages) {
              const speciesEnName = SPECIES_EN_NAMES[speciesId] || `species-${speciesId}`
              const safeSpeciesName = speciesEnName.replace(/[^a-zA-Z0-9]/g, '-')
              const individualFileName = `${safeSpeciesName}-${safeTraitName}-${safeOntologyName}-${timestamp}.png`
              zip.file(individualFileName, blob)
            }

            // Calculate merged canvas dimensions
            const cols = Math.ceil(Math.sqrt(speciesImages.length))
            const rows = Math.ceil(speciesImages.length / cols)
            const padding = 40
            const titleHeight = 60

            const maxWidth = Math.max(...speciesImages.map(img => img.width))
            const maxHeight = Math.max(...speciesImages.map(img => img.height))

            const cellWidth = maxWidth
            const cellHeight = maxHeight + titleHeight
            const canvasWidth = cols * cellWidth + (cols + 1) * padding
            const canvasHeight = rows * cellHeight + (rows + 1) * padding

            // Create and draw canvas
            const canvas = document.createElement('canvas')
            canvas.width = canvasWidth
            canvas.height = canvasHeight
            const ctx = canvas.getContext('2d')

            if (!ctx) {
              throw new Error('Canvas context creation failed')
            }

            // Fill white background
            ctx.fillStyle = 'white'
            ctx.fillRect(0, 0, canvasWidth, canvasHeight)

            // Draw each species image
            for (let i = 0; i < speciesImages.length; i++) {
              const { speciesName, imageElement, width, height } = speciesImages[i]
              const col = i % cols
              const row = Math.floor(i / cols)

              const x = padding + col * (cellWidth + padding)
              const y = padding + row * (cellHeight + padding)

              // Draw title
              ctx.fillStyle = '#000'
              ctx.font = 'bold 32px Arial'
              ctx.textAlign = 'center'
              ctx.fillText(speciesName, x + cellWidth / 2, y + 40)

              // Draw image (centered)
              const imgX = x + (cellWidth - width) / 2
              const imgY = y + titleHeight
              ctx.drawImage(imageElement, imgX, imgY, width, height)
            }

            // Convert to Blob and add to ZIP (merged image)
            try {
              const mergedBlob = await new Promise<Blob>((resolve, reject) => {
                canvas.toBlob((blob) => {
                  if (blob) resolve(blob)
                  else reject(new Error('Canvas toBlob failed'))
                }, 'image/png')
              })

              const mergedFileName = `network-comparison-${safeTraitName}-${safeOntologyName}-${timestamp}.png`
              zip.file(mergedFileName, mergedBlob)
            } catch (mergeError) {
              console.error('Merged image generation failed:', mergeError)
              message.warning(t('batchExport.mergeImageFailed'))
            }

            // Clean up Object URLs
            speciesImages.forEach(({ objectURL }) => {
              URL.revokeObjectURL(objectURL)
            })

          } catch (error) {
            console.error('PNG export failed:', error)
            message.error(t('batchExport.pngFailed'))

            // Clean up Object URLs on error
            if (speciesImages && speciesImages.length > 0) {
              speciesImages.forEach(({ objectURL }) => {
                URL.revokeObjectURL(objectURL)
              })
            }
          }
        }

        // ========== CSV and JSON Export ==========
        for (const [speciesId, card] of readyCards) {
          const { data, speciesName } = card
          const speciesEnName = SPECIES_EN_NAMES[speciesId] || `species-${speciesId}`
          const safeSpeciesName = speciesEnName.replace(/[^a-zA-Z0-9]/g, '-')
          const prefix = `${safeSpeciesName}-${safeTraitName}-${safeOntologyName}-${timestamp}`

          // Export CSV
          if (selectedFormats.includes('csv') && data) {
            try {
              const csv = generateCSV(data)
              zip.file(`${prefix}.csv`, csv)
            } catch (error) {
              console.error(`${speciesName} CSV export failed:`, error)
            }
          }

          // Export JSON
          if (selectedFormats.includes('json') && data) {
            try {
              const json = JSON.stringify(data, null, 2)
              zip.file(`${prefix}.json`, json)
            } catch (error) {
              console.error(`${speciesName} JSON export failed:`, error)
            }
          }
        }

        message.loading({
          content: t('batchExport.packing'),
          key: messageKey,
          duration: 0
        })

        const blob = await zip.generateAsync({ type: 'blob' })

        const zipFileName = `network-comparison-${timestamp}.zip`
        saveAs(blob, zipFileName)

        message.destroy(messageKey)
        message.success({
          content: t('batchExport.success', { count: readyCards.length }),
          duration: 3
        })
      } catch (error) {
        console.error('Batch export failed:', error)
        message.destroy(messageKey)
        message.error({
          content: t('batchExport.failed'),
          duration: 3
        })
      }
    }
  })
}
