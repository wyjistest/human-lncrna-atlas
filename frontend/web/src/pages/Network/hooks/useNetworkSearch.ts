import { useState, useEffect } from 'react'
import type { Core, NodeSingular } from 'cytoscape'

/**
 * Network search hook - handles node search and highlighting
 * @param cyRef - Reference to Cytoscape instance
 * @returns Search state and control functions
 */
export const useNetworkSearch = (cyRef: React.RefObject<Core>) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{id: string, label: string}>>([])

  // Independent search highlight effect (doesn't trigger graph rebuild)
  useEffect(() => {
    if (!cyRef.current) return

    // Clear all highlights
    cyRef.current.nodes().removeClass('highlighted')

    // Apply highlights if search term exists
    if (searchTerm) {
      const newResults: Array<{id: string, label: string}> = []
      cyRef.current.nodes().forEach((node: NodeSingular) => {
        const nodeLabel = node.data('label') as string
        const nodeId = node.data('id') as string
        if (nodeLabel.toLowerCase().includes(searchTerm.toLowerCase()) || nodeId.toLowerCase().includes(searchTerm.toLowerCase())) {
          node.addClass('highlighted')
          newResults.push({ id: nodeId, label: nodeLabel })
        }
      })
      setSearchResults(newResults)

      // Auto-focus if only one result
      if (newResults.length === 1) {
        const node = cyRef.current.$id(newResults[0].id)
        cyRef.current.animate({
          center: { eles: node },
          zoom: 2
        }, {
          duration: 500
        })
      }
    } else {
      setSearchResults([])
    }
  }, [searchTerm, cyRef])

  /**
   * Highlight and focus on a specific node
   */
  const highlightNode = (nodeId: string) => {
    if (!cyRef.current) return

    const node = cyRef.current.$id(nodeId)

    // Clear other highlights
    cyRef.current.nodes().removeClass('highlighted')

    // Highlight selected node
    node.addClass('highlighted')

    // Focus on node
    cyRef.current.animate({
      center: { eles: node },
      zoom: 2
    }, {
      duration: 500
    })
  }

  return {
    searchTerm,
    setSearchTerm,
    searchResults,
    highlightNode
  }
}
