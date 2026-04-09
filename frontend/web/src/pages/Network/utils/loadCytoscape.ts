import type { Core, CytoscapeOptions } from 'cytoscape'

type CytoscapeFactory = (options: CytoscapeOptions) => Core

let cytoscapeLoader: Promise<CytoscapeFactory> | null = null
let svgPluginRegistered = false

export async function loadNetworkCytoscape(): Promise<CytoscapeFactory> {
  if (!cytoscapeLoader) {
    cytoscapeLoader = Promise.all([
      import('cytoscape'),
      import('cytoscape-svg'),
    ])
      .then(([cytoscapeModule, cytoscapeSvgModule]) => {
        const cytoscape = cytoscapeModule.default

        if (!svgPluginRegistered && typeof window !== 'undefined') {
          cytoscape.use(cytoscapeSvgModule.default)
          svgPluginRegistered = true
        }

        return cytoscape as unknown as CytoscapeFactory
      })
      .catch((error) => {
        cytoscapeLoader = null
        throw error
      })
  }

  return cytoscapeLoader
}
