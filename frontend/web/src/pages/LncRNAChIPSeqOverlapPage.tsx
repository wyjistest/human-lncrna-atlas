/**
 * lncRNA-ChIP-seq Overlap Analysis Page
 *
 * 展示 lncRNA 结合位点与 ChIP-seq peaks 的重叠分析结果
 */

import { Typography, Space, Breadcrumb, Card } from 'antd'
import { HomeOutlined, ExperimentOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { LncRNAChIPSeqOverlapTable } from '@/components/LncRNAChIPSeqOverlapTable'

const { Title, Paragraph } = Typography

export default function LncRNAChIPSeqOverlapPage() {
  const { t } = useTranslation('overlap')

  return (
    <div style={{ padding: '24px' }}>
      {/* 面包屑导航 */}
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          {
            title: (
              <Link to="/">
                <HomeOutlined />
              </Link>
            )
          },
          {
            title: (
              <Link to="/regulations">
                <ExperimentOutlined />
                <span style={{ marginLeft: 4 }}>
                  {t('breadcrumb.regulations', 'Regulations')}
                </span>
              </Link>
            )
          },
          {
            title: t('breadcrumb.overlap', 'lncRNA-ChIP-seq Overlap')
          }
        ]}
      />

      {/* 页面标题和说明 */}
      <Space orientation="vertical" size="large" style={{ width: '100%', marginBottom: 24 }}>
        <div>
          <Title level={2}>
            {t('page.title', 'lncRNA-ChIP-seq Overlap Analysis')}
          </Title>
          <Paragraph type="secondary">
            {t(
              'page.description',
              'Analyze the genomic overlap between lncRNA binding sites and ChIP-seq peaks. ' +
              'This reveals which epigenetic marks are enriched at lncRNA target regions.'
            )}
          </Paragraph>
        </div>
      </Space>

      {/* 主组件 - 启用 IGV 浏览器集成 */}
      <Card>
        <LncRNAChIPSeqOverlapTable
          enableExport={true}
          enableIGV={true}
          defaultShowIGV={false}
        />
      </Card>
    </div>
  )
}
