import { Card, Row, Col, Statistic } from 'antd'
import { DatabaseOutlined, LinkOutlined, MedicineBoxOutlined, ApartmentOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useStats } from '@/hooks/useStats'

export default function Home() {
  const navigate = useNavigate()
  const { data } = useStats()
  const { t } = useTranslation('home')

  return (
    <div style={{ padding: 24 }}>
      <h1>{t('title')}</h1>
      <p style={{ fontSize: 16, color: '#666', marginBottom: 32 }}>{t('subtitle')}</p>

      <Row gutter={16} style={{ marginBottom: 32 }}>
        <Col span={6}>
          <Card>
            <Statistic title={t('stats.totalGenes')} value={data?.total_genes} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title={t('stats.lncRNA')} value={data?.total_lncrna} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title={t('stats.regulations')} value={data?.total_regulations} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title={t('stats.diseaseAssociations')} value={data?.total_trait_associations} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={6}>
          <Card hoverable onClick={() => navigate('/genes')}>
            <DatabaseOutlined style={{ fontSize: 32, color: '#1890ff' }} />
            <h3>{t('cards.genes.title')}</h3>
            <p>{t('cards.genes.desc')}</p>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate('/regulations')}>
            <LinkOutlined style={{ fontSize: 32, color: '#52c41a' }} />
            <h3>{t('cards.regulations.title')}</h3>
            <p>{t('cards.regulations.desc')}</p>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate('/diseases')}>
            <MedicineBoxOutlined style={{ fontSize: 32, color: '#fa8c16' }} />
            <h3>{t('cards.diseases.title')}</h3>
            <p>{t('cards.diseases.desc')}</p>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => navigate('/network')}>
            <ApartmentOutlined style={{ fontSize: 32, color: '#722ed1' }} />
            <h3>{t('cards.network.title')}</h3>
            <p>{t('cards.network.desc')}</p>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
