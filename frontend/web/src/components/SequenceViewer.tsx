/**
 * 序列查看器组件
 * 用于展示 LncRNA 和 DNA 序列数据
 */
import { Modal, Descriptions, Typography, Spin, Empty, Button, message, Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons'
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

  // 生成 FASTA 格式内容
  const generateFasta = (sequence: string, header: string) => {
    // FASTA 格式：每行 60 个字符
    const formattedSeq = sequence.match(/.{1,60}/g)?.join('\n') || sequence
    return `>${header}\n${formattedSeq}\n`
  }

  // 下载序列为 FASTA 文件
  const downloadFasta = (type: 'lncrna' | 'dna' | 'both') => {
    if (!data) return

    let content = ''
    let filename = ''
    const lncrnaName = data.lncrna_gene_name || 'LncRNA'
    const targetName = data.target_gene_name || 'Target'

    if (type === 'lncrna' && data.lncrna_sequence) {
      const header = `${lncrnaName}|pos:${data.lncrna_start}-${data.lncrna_end}|len:${data.lncrna_sequence.length}bp`
      content = generateFasta(data.lncrna_sequence, header)
      filename = `${lncrnaName}_lncrna.fasta`
    } else if (type === 'dna' && data.dna_sequence) {
      const header = `${targetName}|chr:${data.target_chromosome}|pos:${data.dna_start}-${data.dna_end}|len:${data.dna_sequence.length}bp`
      content = generateFasta(data.dna_sequence, header)
      filename = `${targetName}_dna.fasta`
    } else if (type === 'both') {
      if (data.lncrna_sequence) {
        const lncrnaHeader = `${lncrnaName}|type:lncrna|pos:${data.lncrna_start}-${data.lncrna_end}|len:${data.lncrna_sequence.length}bp`
        content += generateFasta(data.lncrna_sequence, lncrnaHeader)
      }
      if (data.dna_sequence) {
        const dnaHeader = `${targetName}|type:dna|chr:${data.target_chromosome}|pos:${data.dna_start}-${data.dna_end}|len:${data.dna_sequence.length}bp`
        content += generateFasta(data.dna_sequence, dnaHeader)
      }
      filename = `${lncrnaName}_${targetName}_sequences.fasta`
    }

    if (!content) {
      message.error(t('sequence.downloadFailed'))
      return
    }

    // 创建并下载文件
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename.replace(/[^a-zA-Z0-9._-]/g, '_')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success(t('sequence.downloaded'))
  }

  // 下载菜单项
  const downloadMenuItems: MenuProps['items'] = [
    {
      key: 'lncrna',
      label: t('sequence.downloadLncrna'),
      disabled: !data?.lncrna_sequence,
      onClick: () => downloadFasta('lncrna'),
    },
    {
      key: 'dna',
      label: t('sequence.downloadDna'),
      disabled: !data?.dna_sequence,
      onClick: () => downloadFasta('dna'),
    },
    { type: 'divider' },
    {
      key: 'both',
      label: t('sequence.downloadBoth'),
      disabled: !data?.lncrna_sequence && !data?.dna_sequence,
      onClick: () => downloadFasta('both'),
    },
  ]

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
          {/* 元信息和下载按钮 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <Descriptions column={2} bordered size="small" style={{ flex: 1 }}>
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
            <Dropdown menu={{ items: downloadMenuItems }} placement="bottomRight">
              <Button icon={<DownloadOutlined />} style={{ marginLeft: 16 }}>
                {t('sequence.download')}
              </Button>
            </Dropdown>
          </div>

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
