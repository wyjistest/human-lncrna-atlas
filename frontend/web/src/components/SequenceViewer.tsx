/**
 * 序列查看器组件
 * 用于展示 LncRNA 和 DNA 序列数据
 */
import { Modal, Descriptions, Typography, Spin, Empty, Button, message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import { useRegulationDetail } from '@/hooks/useRegulations'
import { useTranslation } from 'react-i18next'

const { Text, Paragraph } = Typography

interface SequenceViewerProps {
  regulationId: number | null
  open: boolean
  onClose: () => void
}

export function SequenceViewer({ regulationId, open, onClose }: SequenceViewerProps) {
  const { t } = useTranslation('regulations')
  const { data, isLoading } = useRegulationDetail(regulationId)

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      message.success(t('sequence.copied', { label }))
    } catch {
      message.error(t('sequence.copyFailed'))
    }
  }

  const formatSequence = (seq: string | null | undefined) => {
    if (!seq) return null
    // 每 60 个字符换行
    return seq.match(/.{1,60}/g)?.join('\n') || seq
  }

  return (
    <Modal
      title={t('sequence.title')}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
    >
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
        </div>
      ) : !data ? (
        <Empty description={t('sequence.noData')} />
      ) : (
        <div>
          <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t('sequence.lncrnaGene')}>
              {data.lncrna_gene_name || 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label={t('sequence.targetGene')}>
              {data.target_gene_name || 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label={t('sequence.lncrnaPosition')}>
              {data.lncrna_start?.toLocaleString() ?? 'N/A'} - {data.lncrna_end?.toLocaleString() ?? 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label={t('sequence.dnaPosition')}>
              {data.dna_start?.toLocaleString() ?? 'N/A'} - {data.dna_end?.toLocaleString() ?? 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label={t('sequence.bindingAffinity')}>
              {data.binding_affinity ? Number(data.binding_affinity).toFixed(2) : 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label={t('sequence.chromosome')}>
              {data.target_chromosome || 'N/A'}
            </Descriptions.Item>
          </Descriptions>

          {/* LncRNA 序列 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong>{t('sequence.lncrnaSequence')}</Text>
              {data.lncrna_sequence && (
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(data.lncrna_sequence!, 'LncRNA')}
                >
                  {t('sequence.copy')}
                </Button>
              )}
            </div>
            {data.lncrna_sequence ? (
              <Paragraph
                code
                style={{
                  fontFamily: 'monospace',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  backgroundColor: '#f5f5f5',
                  padding: 12,
                  borderRadius: 4,
                  maxHeight: 200,
                  overflow: 'auto',
                }}
              >
                {formatSequence(data.lncrna_sequence)}
              </Paragraph>
            ) : (
              <Text type="secondary">{t('sequence.notAvailable')}</Text>
            )}
            {data.lncrna_sequence && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sequence.length')}: {data.lncrna_sequence.length} bp
              </Text>
            )}
          </div>

          {/* DNA 序列 */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong>{t('sequence.dnaSequence')}</Text>
              {data.dna_sequence && (
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(data.dna_sequence!, 'DNA')}
                >
                  {t('sequence.copy')}
                </Button>
              )}
            </div>
            {data.dna_sequence ? (
              <Paragraph
                code
                style={{
                  fontFamily: 'monospace',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  backgroundColor: '#f5f5f5',
                  padding: 12,
                  borderRadius: 4,
                  maxHeight: 200,
                  overflow: 'auto',
                }}
              >
                {formatSequence(data.dna_sequence)}
              </Paragraph>
            ) : (
              <Text type="secondary">{t('sequence.notAvailable')}</Text>
            )}
            {data.dna_sequence && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('sequence.length')}: {data.dna_sequence.length} bp
              </Text>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
