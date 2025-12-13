import { useMemo } from 'react'
import { Drawer, Descriptions, Tag, Tabs, Alert, Table } from 'antd'
import type { TabsProps } from 'antd'
import { useTranslation } from 'react-i18next'
import { LoadingState } from '@/components/LoadingState'
import { ErrorState } from '@/components/ErrorState'
import { SPECIES_KEYS } from '../types'

interface ComparisonDrawerProps {
  open: boolean
  onClose: () => void
  selectedLncrna: {
    geneId: number
    coreId: number
    geneName: string
  } | null
  comparisonData: any
  loading: boolean
  error: any
}

/**
 * Cross-species comparison drawer component
 * Shows conserved targets across multiple species
 */
export const ComparisonDrawer = ({
  open,
  onClose,
  selectedLncrna,
  comparisonData,
  loading,
  error
}: ComparisonDrawerProps) => {
  const { t } = useTranslation('network')

  // Memoize tab items to avoid React Compiler memoization issues
  const tabItems: TabsProps['items'] = useMemo(() => {
    if (!comparisonData?.species_networks) return []

    const conservedSet = new Set(comparisonData.conserved_targets || [])

    return Object.entries(comparisonData.species_networks).map(([speciesIdStr, speciesData]: [string, any]) => {
      const sid = parseInt(speciesIdStr)
      const speciesKey = SPECIES_KEYS[sid] || 'unknown'
      const speciesName = t(`species.${speciesKey}`, { id: sid })

      return {
        key: speciesIdStr,
        label: (
          <span>
            {speciesName}
            <Tag color="blue" style={{ marginLeft: 8 }}>
              {t('comparison.targetCount', { count: speciesData.target_count })}
            </Tag>
          </span>
        ),
        children: (
          <div>
            {speciesData.truncated && (
              <Alert
                message={t('comparison.truncatedWarning', {
                  count: speciesData.target_count,
                  total: speciesData.total_target_count
                })}
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
              />
            )}
            <Table
              dataSource={speciesData.targets}
              rowKey={(record: any, index?: number) => `${record.target_gene_id}-${record.target_core_id}-${index ?? 0}`}
              size="small"
              pagination={{ pageSize: 20, showSizeChanger: true }}
              columns={[
                {
                  title: t('comparison.targetGene'),
                  dataIndex: 'target_name',
                  key: 'target_name',
                  render: (name: string) => name || '-'
                },
                {
                  title: t('comparison.coreId'),
                  dataIndex: 'target_core_id',
                  key: 'target_core_id'
                },
                {
                  title: t('comparison.bindingAffinity'),
                  dataIndex: 'binding_affinity',
                  key: 'binding_affinity',
                  render: (ba: number) => ba?.toFixed(2) || '-',
                  sorter: (a: any, b: any) => (a.binding_affinity || 0) - (b.binding_affinity || 0)
                },
                {
                  title: t('comparison.conserved'),
                  dataIndex: 'target_core_id',
                  key: 'conserved',
                  render: (coreId: number) => {
                    const isConserved = conservedSet.has(coreId)
                    if (isConserved) {
                      // Count how many species this target appears in
                      const count = Object.values(comparisonData.species_networks).filter(
                        (sn: any) => sn.targets.some((target: any) => target.target_core_id === coreId)
                      ).length
                      return (
                        <Tag color="green">
                          {t('comparison.conservedIn', { count })}
                        </Tag>
                      )
                    }
                    return <span style={{ color: '#999' }}>-</span>
                  },
                  filters: [
                    { text: t('comparison.conserved'), value: 'conserved' },
                    { text: t('comparison.notConserved'), value: 'not_conserved' }
                  ],
                  onFilter: (value: any, record: any) => {
                    const isConserved = conservedSet.has(record.target_core_id)
                    return value === 'conserved' ? isConserved : !isConserved
                  }
                }
              ]}
            />
          </div>
        )
      }
    })
  }, [comparisonData, t])

  return (
    <Drawer
      title={t('comparison.title')}
      placement="right"
      onClose={onClose}
      open={open}
      width={800}
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : comparisonData ? (
        <div>
          {/* Summary Information */}
          <Descriptions column={1} bordered size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t('comparison.lncrnaLabel')}>
              {selectedLncrna?.geneName}
            </Descriptions.Item>
            <Descriptions.Item label={t('comparison.coreIdLabel')}>
              {comparisonData.lncrna_core_id}
            </Descriptions.Item>
            <Descriptions.Item label={t('comparison.conservedTargetsLabel')}>
              <Tag color="blue" style={{ fontSize: 14, padding: '4px 12px' }}>
                {comparisonData.conserved_target_count}
              </Tag>
              <span style={{ marginLeft: 8, color: '#666' }}>
                {t('comparison.conservedCount', {
                  count: comparisonData.conserved_target_count,
                  speciesCount: Object.keys(comparisonData.species_networks).length
                })}
              </span>
            </Descriptions.Item>
          </Descriptions>

          {/* Species-wise comparison tabs */}
          <Tabs items={tabItems} />
        </div>
      ) : (
        <div>{t('comparison.noDataForSpecies')}</div>
      )}
    </Drawer>
  )
}
