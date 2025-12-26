import { Drawer, Descriptions, Tag } from 'antd'
import { useTranslation } from 'react-i18next'
import { LoadingState } from '@/components/LoadingState'
import type { GeneDetail } from '@/types/network'

interface GeneDetailDrawerProps {
  open: boolean
  onClose: () => void
  geneDetail: GeneDetail | null
  loading: boolean
}

/**
 * Gene detail drawer component
 * Displays comprehensive gene information including conservation, coordinates, and connections
 */
export const GeneDetailDrawer = ({ open, onClose, geneDetail, loading }: GeneDetailDrawerProps) => {
  const { t } = useTranslation('network')

  return (
    <Drawer
      title={t('drawer.title')}
      placement="right"
      onClose={onClose}
      open={open}
      styles={{ wrapper: { width: 400 } }}
    >
      {loading ? (
        <LoadingState />
      ) : geneDetail ? (
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label={t('drawer.geneName')}>{geneDetail.gene_name}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.ensemblId')}>{geneDetail.gene_ensembl_id ?? 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.ensemblLink')}>
            {geneDetail.gene_ensembl_id?.startsWith('ENSG') ? (
              <a
                href={`https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${geneDetail.gene_ensembl_id.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#1890ff', textDecoration: 'underline' }}
              >
                {t('drawer.viewInEnsembl')}
              </a>
            ) : (
              <span style={{ color: '#999' }}>{t('drawer.ensemblLinkNA')}</span>
            )}
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.fantomLink')}>
            <a
              href={`https://fantom.gsc.riken.jp/cat/v1/#/genes/${geneDetail.gene_ensembl_id?.replace(/_(marmoset|macaque|chimpanzee|chimp)$/i, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#1890ff', textDecoration: 'underline' }}
            >
              {t('drawer.viewInFantom')}
            </a>
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.geneType')}>
            <Tag color={geneDetail.gene_type === 'lncRNA' ? 'blue' : 'green'}>
              {geneDetail.gene_type}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.speciesLabel')}>
            <Tag color="orange" style={{ fontSize: 13, padding: '2px 8px' }}>
              {geneDetail.species_name ?? 'N/A'}
            </Tag>
            <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>
              (ID: {geneDetail.species_id})
            </span>
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.conservationLabel')}>
            <Tag
              color={geneDetail.conservation_count === 4 ? 'green' : geneDetail.conservation_count === 1 ? 'red' : 'blue'}
              style={{ fontSize: 14, padding: '4px 12px', fontWeight: 'bold', fontFamily: 'monospace' }}
            >
              {geneDetail.conservation_label}
            </Tag>
            <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>
              {t('drawer.conservationCount', { count: geneDetail.conservation_count })}
            </span>
            <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
              {geneDetail.conservation_label[0] === '1' && t('species.human') + ' '}
              {geneDetail.conservation_label[1] === '1' && t('species.chimpanzee') + ' '}
              {geneDetail.conservation_label[2] === '1' && t('species.macaque') + ' '}
              {geneDetail.conservation_label[3] === '1' && t('species.marmoset')}
            </div>
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.chromosome')}>{geneDetail.chromosome || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.startPosition')}>{geneDetail.gene_start?.toLocaleString() || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.endPosition')}>{geneDetail.gene_end?.toLocaleString() || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.strand')}>{geneDetail.strand || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.coreId')}>{geneDetail.core_id ?? 'N/A'}</Descriptions.Item>
          <Descriptions.Item label={t('drawer.asSource')}>
            {geneDetail.connections?.as_source || 0}
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.asTarget')}>
            {geneDetail.connections?.as_target || 0}
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.totalRegulations')}>
            {geneDetail.connections?.total || 0}
          </Descriptions.Item>
          <Descriptions.Item label={t('drawer.totalBA')}>
            {geneDetail.connections?.total_ba?.toFixed(2) || 0}
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <div>{t('drawer.noData')}</div>
      )}
    </Drawer>
  )
}
