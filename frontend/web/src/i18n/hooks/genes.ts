import { apiClient } from './client'
import type { components } from '@/types'

type GeneListItem = components['schemas']['GeneListItem']
type GeneDetail = components['schemas']['GeneDetail']
type PaginatedResponse<T> = components['schemas']['PaginatedResponse_GeneListItem_'] & { items: T[] }

export const genesApi = {
  list: (params: {
    page?: number
    page_size?: number
    gene_type?: string
    species_id?: number
    search?: string
  }) => apiClient.get<PaginatedResponse<GeneListItem>>('/api/v1/genes', { params }),

  detail: (geneId: number) => apiClient.get<GeneDetail>(`/api/v1/genes/${geneId}`),
}
