import type { NodeSingular } from 'cytoscape'

export type LayoutOptions = {
  animate?: boolean
  animationDuration?: number
}

/**
 * Get layout configuration for Cytoscape
 * @param layoutName - Name of the layout algorithm
 * @param options - Override common layout options (e.g. disable animation for large graphs)
 * @returns Cytoscape layout configuration object
 */
export const getLayoutConfig = (layoutName: string, options?: LayoutOptions) => {
  const baseConfig = {
    animate: options?.animate ?? true,
    animationDuration: options?.animationDuration ?? 500
  }

  switch (layoutName) {
    case 'concentric':
      return {
        name: 'concentric',
        ...baseConfig,
        concentric: (node: NodeSingular) => node.data('type') === 'lncRNA' ? 2 : 1,
        levelWidth: () => 1,
        minNodeSpacing: 60
      }
    case 'cose':
      return {
        name: 'cose',
        ...baseConfig,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 100,
        edgeElasticity: () => 100,
        nestingFactor: 1.2
      }
    case 'circle':
      return {
        name: 'circle',
        ...baseConfig,
        radius: 200,
        startAngle: -Math.PI / 2
      }
    case 'grid':
      return {
        name: 'grid',
        ...baseConfig,
        rows: undefined,
        cols: undefined
      }
    case 'breadthfirst':
      return {
        name: 'breadthfirst',
        ...baseConfig,
        directed: true,
        spacingFactor: 1.5,
        roots: '[type="lncRNA"]'  // Use selector string instead of node collection
      }
    case 'random':
      return {
        name: 'random',
        ...baseConfig
      }
    default:
      return {
        name: 'concentric',
        ...baseConfig,
        concentric: (node: NodeSingular) => node.data('type') === 'lncRNA' ? 2 : 1,
        levelWidth: () => 1,
        minNodeSpacing: 60
      }
  }
}
