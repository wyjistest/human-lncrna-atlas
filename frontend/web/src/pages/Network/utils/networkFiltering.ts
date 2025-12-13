/**
 * Apply filters to network data (BA threshold, node type, degree)
 * @param data - Raw network data with nodes and edges
 * @param minBA - Minimum binding affinity threshold
 * @param nodeTypeFilter - Node type filter ('all' | 'lncRNA' | 'protein_coding')
 * @param minDegree - Minimum node degree (connection count)
 * @returns Filtered nodes and edges
 */
export const applyNetworkFilters = (
  data: any,
  minBA: number,
  nodeTypeFilter: string,
  minDegree: number
) => {
  // 1. Filter edges (BA threshold)
  const filteredEdges = data.edges.filter((edge: any) => {
    const ba = edge.binding_affinity || 0
    return ba >= minBA
  })

  // 2. Calculate node degrees (connection count)
  const nodeDegrees = new Map<string, number>()
  filteredEdges.forEach((edge: any) => {
    nodeDegrees.set(edge.source, (nodeDegrees.get(edge.source) || 0) + 1)
    nodeDegrees.set(edge.target, (nodeDegrees.get(edge.target) || 0) + 1)
  })

  // 3. Filter nodes (type + degree)
  const filteredNodes = data.nodes.filter((node: any) => {
    // Node type filter
    if (nodeTypeFilter !== 'all' && node.type !== nodeTypeFilter) {
      return false
    }
    // Degree filter
    const degree = nodeDegrees.get(node.id) || 0
    return degree >= minDegree
  })

  // 4. Get set of retained node IDs
  const nodeIds = new Set(filteredNodes.map((n: any) => n.id))

  // 5. Only keep edges where both endpoints exist
  const finalEdges = filteredEdges.filter((edge: any) =>
    nodeIds.has(edge.source) && nodeIds.has(edge.target)
  )

  return { filteredNodes, finalEdges }
}
