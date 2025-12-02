import { apiClient } from './client'
import type { components } from '@/types'

type NetworkData = components['schemas']['NetworkData']

export const networkApi = {
  getGeneNetwork: (geneId: number, params?: {
    species_id?: number
    min_ba?: number
    max_distance?: number
    depth?: number
  }) => apiClient.get<NetworkData>(`/api/v1/network/gene/${geneId}`, { params }),
}
