import { useState, useRef, useMemo } from 'react'
import { Alert, Button, InputNumber, Select, Space } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useQueries, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { networkApi } from '@/api/network'
import { diseasesApi } from '@/api/diseases'
import type { DiseaseOption } from '@/api/diseases'
import type { AvailableCombination } from '@/types/network'
import { NetworkCard } from './components/NetworkCard'
import { handleBatchExport, type NetworkCardRef } from './utils/batchExport.tsx'
import { SPECIES_KEYS } from './types'

const DEFAULT_SPECIES_IDS = [1]
const DEFAULT_MIN_BA = 0

function parseIntegerParam(value: string | null, min: number, max = Number.MAX_SAFE_INTEGER): number | undefined {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) return undefined
  return parsed
}

function parseNumberParam(value: string | null, min: number, max = Number.MAX_SAFE_INTEGER): number | undefined {
  if (!value) return undefined
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) return undefined
  return parsed
}

function parseSpeciesIdsParam(value: string | null): number[] {
  if (!value) return []

  const uniqueSpeciesIds = new Set<number>()
  for (const rawValue of value.split(',')) {
    const speciesId = parseIntegerParam(rawValue.trim(), 1, 4)
    if (speciesId !== undefined) uniqueSpeciesIds.add(speciesId)
  }

  return Array.from(uniqueSpeciesIds).slice(0, 4)
}

/**
 * Network Page Component
 * Main page for disease network visualization across multiple species
 * Features:
 * - Multi-species network comparison
 * - Disease and ontology selection
 * - Batch export functionality
 * - Dynamic query with filtering
 */
export default function Network() {
  const { t } = useTranslation('network')
  const [searchParams] = useSearchParams()

  const initialFilters = useMemo(() => {
    const parsedSpeciesIds = parseSpeciesIdsParam(searchParams.get('species_ids'))
    const parsedTraitId = parseIntegerParam(searchParams.get('trait_id'), 1)
    const parsedOntologyId = parseIntegerParam(searchParams.get('ontology_id'), 1)
    const parsedMinBa = parseNumberParam(searchParams.get('min_ba'), 0)

    return {
      speciesIds: parsedSpeciesIds.length > 0 ? parsedSpeciesIds : DEFAULT_SPECIES_IDS,
      traitId: parsedTraitId,
      ontologyId: parsedOntologyId,
      minBa: parsedMinBa ?? DEFAULT_MIN_BA,
      shouldAutoQuery:
        parsedSpeciesIds.length > 0 &&
        parsedTraitId !== undefined &&
        parsedOntologyId !== undefined &&
        parsedMinBa !== undefined,
    }
  }, [searchParams])

  const [speciesIds, setSpeciesIds] = useState<number[]>(initialFilters.speciesIds)
  const [traitId, setTraitId] = useState<number | undefined>(initialFilters.traitId)
  const [ontologyId, setOntologyId] = useState<number | undefined>(initialFilters.ontologyId)
  const [minBa, setMinBa] = useState<number>(initialFilters.minBa)
  const [queryTrigger, setQueryTrigger] = useState(initialFilters.shouldAutoQuery ? 1 : 0)

  // 本地化物种选项
  const speciesOptions = useMemo(() => [
    { label: t('species.human'), value: 1 },
    { label: t('species.chimpanzee'), value: 2 },
    { label: t('species.macaque'), value: 3 },
    { label: t('species.marmoset'), value: 4 },
  ], [t])

  // 获取物种名称的辅助函数
  const getSpeciesName = (speciesId: number) => {
    const key = SPECIES_KEYS[speciesId]
    return key ? t(`species.${key}`) : t('species.unknown', { id: speciesId })
  }

  // 批量导出: 收集所有 NetworkCard 的 cyRef 和数据
  const networkCardsRef = useRef<Map<number, NetworkCardRef>>(new Map())

  // 获取有网络数据的组合
  const { data: availableCombinations } = useQuery({
    queryKey: ['available-combinations'],
    queryFn: async ({ signal }) => {
      const res = await networkApi.getAvailableCombinations(undefined, signal)
      return res.data.combinations
    }
  })

  // 获取疾病选项列表（轻量级 API）
  const {
    data: diseaseOptions,
    isLoading: diseaseOptionsLoading,
    isError: diseaseOptionsError,
    refetch: refetchDiseaseOptions
  } = useQuery({
    queryKey: ['disease-options'],
    queryFn: ({ signal }) => diseasesApi.getOptions(signal),
    staleTime: 10 * 60 * 1000, // 10分钟缓存
  })

  // Memoize available combinations for selected species
  const availableForSelectedSpecies = useMemo(() => {
    if (!availableCombinations) return []
    return availableCombinations.filter((c: AvailableCombination) =>
      speciesIds.some(speciesId => c.species_id === speciesId)
    )
  }, [availableCombinations, speciesIds])

  // Filter traits based on available combinations
  const traits = useMemo(() => {
    const traitsList = diseaseOptions?.traits
    if (!traitsList) return []
    const availableTraitIds = new Set(availableForSelectedSpecies.map((c: AvailableCombination) => c.trait_id))
    return traitsList.filter(trait => availableTraitIds.has(trait.trait_id))
  }, [diseaseOptions, availableForSelectedSpecies])

  // Filter ontologies based on selected trait
  const ontologies = useMemo(() => {
    if (availableForSelectedSpecies.length === 0 || !traitId) return []
    const ontologyMap = new Map<number, string>()

    availableForSelectedSpecies
      .filter((c: AvailableCombination) => c.trait_id === traitId)
      .forEach((c: AvailableCombination) => {
        if (!ontologyMap.has(c.ontology_id)) {
          ontologyMap.set(c.ontology_id, c.ontology_name || `Ontology ${c.ontology_id}`)
        }
      })

    return Array.from(ontologyMap.entries()).map(([id, name]) => ({
      ontology_id: id,
      ontology_name: name
    }))
  }, [availableForSelectedSpecies, traitId])

  // 使用 useQueries 并行查询多个物种
  const networkQueries = useQueries({
    queries: speciesIds.map(speciesId => ({
      queryKey: ['network', speciesId, traitId, ontologyId, minBa, queryTrigger],
      queryFn: async ({ signal }) => {
        if (!traitId || !ontologyId) return null
        const res = await networkApi.getDiseaseNetwork({
          species_id: speciesId,
          trait_id: traitId,
          ontology_id: ontologyId,
          min_ba: minBa
        }, signal)
        return res.data
      },
      enabled: queryTrigger > 0 && !!traitId && !!ontologyId,
      staleTime: 0
    }))
  })

  const handleQuery = () => {
    if (!traitId || !ontologyId) {
      return
    }
    if (speciesIds.length === 0) {
      return
    }
    setQueryTrigger(prev => prev + 1)
  }

  const handleSpeciesChange = (values: number[]) => {
    if (values.length > 4) {
      return
    }
    setSpeciesIds(values)
    setTraitId(undefined)
    setOntologyId(undefined)

    // 清理 networkCardsRef 中不再选中的物种数据
    const newSpeciesSet = new Set(values)
    Array.from(networkCardsRef.current.keys()).forEach(id => {
      if (!newSpeciesSet.has(id)) {
        networkCardsRef.current.delete(id)
      }
    })
    setQueryTrigger(0)
  }

  // 批量导出处理
  const handleBatchExportClick = () => {
    const traitName = traits?.find((t: DiseaseOption) => t.trait_id === traitId)?.trait_name || `trait-${traitId || 'unknown'}`
    const ontologyName = ontologies?.find((o: { ontology_id: number; ontology_name: string }) => o.ontology_id === ontologyId)?.ontology_name || `ontology-${ontologyId || 'unknown'}`

    handleBatchExport({
      speciesIds,
      networkCardsRef,
      getSpeciesName,
      traitName,
      ontologyName,
      t
    })
  }

  // 计算网格列数
  const gridColumns = speciesIds.length === 1 ? 1 : 2

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('title')}</h1>
      <p style={{ color: '#666', marginBottom: 16 }}>
        {t('description')}
      </p>
      <Space style={{ marginBottom: 16 }} wrap>
        <span>{t('species.label')}:</span>
        <Select
          data-testid="network-species-select"
          mode="multiple"
          value={speciesIds}
          onChange={handleSpeciesChange}
          style={{ minWidth: 200 }}
          maxTagCount={2}
          placeholder={t('species.placeholder')}
          options={speciesOptions}
        />
        <span>{t('disease.label')}:</span>
        <Select
          data-testid="network-disease-select"
          placeholder={t('disease.placeholder')}
          value={traitId}
          onChange={(v) => {
            setTraitId(v)
            setOntologyId(undefined)
            setQueryTrigger(0)
          }}
          style={{ width: 250 }}
          showSearch
          loading={diseaseOptionsLoading}
          disabled={diseaseOptionsLoading || diseaseOptionsError}
          filterOption={(input, option) => {
            const label = typeof option?.label === 'string' ? option.label : ''
            return label.toLowerCase().includes(input.toLowerCase())
          }}
          options={traits?.map((tr: DiseaseOption) => ({ label: tr.trait_name, value: tr.trait_id }))}
        />
        <span>{t('ontology.label')}:</span>
        <Select
          data-testid="network-ontology-select"
          placeholder={t('ontology.placeholder')}
          value={ontologyId}
          onChange={(v) => {
            setOntologyId(v)
            setQueryTrigger(0)
          }}
          style={{ width: 250 }}
          disabled={!traitId}
          showSearch
          filterOption={(input, option) => {
            const label = typeof option?.label === 'string' ? option.label : ''
            return label.toLowerCase().includes(input.toLowerCase())
          }}
          options={ontologies?.map((o: { ontology_id: number; ontology_name: string }) => ({ label: o.ontology_name, value: o.ontology_id }))}
        />
        <span>{t('query.minBaLabel')}</span>
        <InputNumber
          min={0}
          max={100}
          precision={0}
          value={minBa}
          onChange={(value) => setMinBa(typeof value === 'number' ? value : 0)}
          style={{ width: 120 }}
        />
        <Button data-testid="network-query-button" type="primary" onClick={handleQuery} disabled={!traitId || !ontologyId}>
          {t('query.button')}
        </Button>
        {/* 批量导出按钮 */}
        {queryTrigger > 0 && speciesIds.length > 0 && (
          <Button
            icon={<DownloadOutlined />}
            onClick={handleBatchExportClick}
            disabled={networkQueries.some(q => q.isLoading || !q.data)}
          >
            {t('batchExport.buttonWithCount', { count: speciesIds.length })}
          </Button>
        )}
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title={t('query.minBaHelper')}
        description={t('query.visualFilterNote')}
      />

      {diseaseOptionsError && (
        <Alert
          type="warning"
          title={t('disease.loadError') || 'Failed to load disease options'}
          description={t('disease.loadErrorDesc') || 'Please try refreshing the page'}
          action={
            <Button size="small" onClick={() => refetchDiseaseOptions()}>
              {t('disease.retry') || 'Retry'}
            </Button>
          }
          style={{ marginBottom: 16 }}
          showIcon
          closable
        />
      )}

      {queryTrigger > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${gridColumns}, 1fr)`,
          gap: 20,
          maxWidth: gridColumns === 1 ? 800 : 1600,
          margin: '0 auto'
        }}>
          {speciesIds.map((speciesId, index) => {
            const query = networkQueries[index]
            const speciesName = getSpeciesName(speciesId)

            return (
              <NetworkCard
                key={speciesId}
                speciesId={speciesId}
                speciesName={speciesName}
                data={query.data ?? null}
                loading={query.isLoading}
                error={query.error ?? null}
                onRefReady={(cyRef, isReady) => {
                  networkCardsRef.current.set(speciesId, {
                    cyRef,
                    data: query.data ?? null,
                    speciesName,
                    isReady: isReady && !query.isLoading && !query.error && !!query.data
                  })
                }}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
