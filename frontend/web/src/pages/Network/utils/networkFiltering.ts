/**
 * Apply filters to network data (BA threshold, node type, degree)
 * @param data - Raw network data with nodes and edges
 * @param minBA - Minimum binding affinity threshold
 * @param nodeTypeFilter - Node type filter ('all' | 'lncRNA' | 'protein_coding')
 * @param minDegree - Minimum node degree (connection count)
 * @returns Filtered nodes and edges
 */
import type { NetworkData, NetworkNode, NetworkEdge } from '@/types/network'

export const applyNetworkFilters = (
  data: NetworkData,
  minBA: number,
  nodeTypeFilter: string,
  minDegree: number
) => {
  // 1. Filter edges (BA threshold)
  const filteredEdges = data.edges.filter((edge: NetworkEdge) => {
    const ba = edge.binding_affinity || 0
    return ba >= minBA
  })

  // 2. Calculate node degrees (connection count)
  const nodeDegrees = new Map<string, number>()
  filteredEdges.forEach((edge: NetworkEdge) => {
    nodeDegrees.set(edge.source, (nodeDegrees.get(edge.source) || 0) + 1)
    nodeDegrees.set(edge.target, (nodeDegrees.get(edge.target) || 0) + 1)
  })

  // 3. Filter nodes (type + degree)
  const filteredNodes = data.nodes.filter((node: NetworkNode) => {
    // Node type filter
    if (nodeTypeFilter !== 'all' && node.type !== nodeTypeFilter) {
      return false
    }
    // Degree filter
    const degree = nodeDegrees.get(node.id) || 0
    return degree >= minDegree
  })

  // 4. Get set of retained node IDs
  const nodeIds = new Set(filteredNodes.map((n: NetworkNode) => n.id))

  // 5. Only keep edges where both endpoints exist
  const finalEdges = filteredEdges.filter((edge: NetworkEdge) =>
    nodeIds.has(edge.source) && nodeIds.has(edge.target)
  )

  return { filteredNodes, finalEdges }
}
