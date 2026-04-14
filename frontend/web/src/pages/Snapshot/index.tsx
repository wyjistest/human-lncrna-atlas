import { Card, Col, Descriptions, Row, Space, Statistic, Tag, Typography } from 'antd'
import { useTranslation } from 'react-i18next'

import { PAPER_SNAPSHOT } from '@/config/paperSnapshot'
import { useRootStatus } from '@/hooks/useRootStatus'

const { Title, Paragraph, Text } = Typography

export default function Snapshot() {
  const { t } = useTranslation('snapshot')
  const { data: rootStatus } = useRootStatus()

  return (
    <div style={{ padding: 24 }}>
      <Space orientation="vertical" size={24} style={{ display: 'flex' }}>
        <Card>
          <Space orientation="vertical" size={12} style={{ display: 'flex' }}>
            <Space wrap size={[8, 8]}>
              <Tag color="blue">{t('sections.snapshot')}</Tag>
              <Tag color="gold">{t('sections.baseline')}</Tag>
            </Space>

            <Title level={1} style={{ margin: 0 }}>
              {t('title')}
            </Title>

            <Paragraph style={{ margin: 0, maxWidth: 860 }}>
              {t('subtitle')}
            </Paragraph>
          </Space>
        </Card>

        <Card title={t('sections.snapshot')}>
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={12} lg={6}>
              <Card>
                <Statistic title={t('cards.species')} value={PAPER_SNAPSHOT.species} />
              </Card>
            </Col>
            <Col xs={12} sm={12} lg={6}>
              <Card>
                <Statistic title={t('cards.candidateEdges')} value={PAPER_SNAPSHOT.candidateEdges} />
              </Card>
            </Col>
            <Col xs={12} sm={12} lg={6}>
              <Card>
                <Statistic title={t('cards.experiments')} value={PAPER_SNAPSHOT.experiments} />
              </Card>
            </Col>
            <Col xs={12} sm={12} lg={6}>
              <Card>
                <Statistic title={t('cards.peaks')} value={PAPER_SNAPSHOT.peaks} />
              </Card>
            </Col>
          </Row>
        </Card>

        <Card title={t('sections.baseline')}>
          <Space orientation="vertical" size={8} style={{ display: 'flex' }}>
            <Text strong>{t('baseline.title')}</Text>
            <Paragraph style={{ margin: 0 }}>{t('baseline.description')}</Paragraph>
          </Space>
        </Card>

        <Card title={t('sections.provenance')}>
          <Descriptions
            column={{ xs: 1, sm: 1, md: 3 }}
            items={[
              {
                key: 'version',
                label: t('status.apiVersion'),
                children: rootStatus?.version ?? t('status.unavailable'),
              },
              {
                key: 'db_mode',
                label: t('status.dbMode'),
                children: rootStatus?.db_mode ?? t('status.unavailable'),
              },
              {
                key: 'db_name',
                label: t('status.dbName'),
                children: rootStatus?.db_name ?? t('status.unavailable'),
              },
            ]}
          />
        </Card>
      </Space>
    </div>
  )
}
