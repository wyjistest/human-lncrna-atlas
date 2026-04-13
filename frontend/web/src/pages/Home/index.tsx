import { type ReactNode, useEffect, useState } from 'react'
import {
  ApartmentOutlined,
  BarChartOutlined,
  BranchesOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  InteractionOutlined,
  LinkOutlined,
  RadarChartOutlined,
} from '@ant-design/icons'
import { Button, Card, Col, Descriptions, Row, Space, Statistic, Tag, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { apiClient } from '@/api/client'
import { PAPER_SNAPSHOT } from '@/config/paperSnapshot'

const { Title, Paragraph, Text } = Typography

type RootStatus = {
  version?: string
  db_mode?: string
  db_name?: string
}

type EntryCard = {
  titleKey: string
  descKey: string
  path: string
  icon: ReactNode
}

const startHereCards: EntryCard[] = [
  {
    titleKey: 'cards.byGene.title',
    descKey: 'cards.byGene.desc',
    path: '/genes',
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#1d4ed8' }} />,
  },
  {
    titleKey: 'cards.byTrait.title',
    descKey: 'cards.byTrait.desc',
    path: '/diseases',
    icon: <ApartmentOutlined style={{ fontSize: 28, color: '#0369a1' }} />,
  },
  {
    titleKey: 'cards.conservation.title',
    descKey: 'cards.conservation.desc',
    path: '/conservation',
    icon: <BranchesOutlined style={{ fontSize: 28, color: '#047857' }} />,
  },
  {
    titleKey: 'cards.epigenomic.title',
    descKey: 'cards.epigenomic.desc',
    path: '/lncrna-chipseq-overlap',
    icon: <InteractionOutlined style={{ fontSize: 28, color: '#b45309' }} />,
  },
]

const advancedCards: EntryCard[] = [
  {
    titleKey: 'cards.edges.title',
    descKey: 'cards.edges.desc',
    path: '/regulations',
    icon: <LinkOutlined style={{ fontSize: 28, color: '#0f766e' }} />,
  },
  {
    titleKey: 'cards.genomeBrowser.title',
    descKey: 'cards.genomeBrowser.desc',
    path: '/genome-browser',
    icon: <ExperimentOutlined style={{ fontSize: 28, color: '#7c3aed' }} />,
  },
  {
    titleKey: 'cards.statistics.title',
    descKey: 'cards.statistics.desc',
    path: '/stats',
    icon: <BarChartOutlined style={{ fontSize: 28, color: '#7c2d12' }} />,
  },
  {
    titleKey: 'cards.compare.title',
    descKey: 'cards.compare.desc',
    path: '/chipseq-compare',
    icon: <RadarChartOutlined style={{ fontSize: 28, color: '#be123c' }} />,
  },
]

function EntrySection({
  title,
  cards,
  onNavigate,
  t,
}: {
  title: string
  cards: EntryCard[]
  onNavigate: (path: string) => void
  t: (key: string) => string
}) {
  return (
    <Card title={title}>
      <Row gutter={[16, 16]}>
        {cards.map((card) => (
          <Col key={card.path} xs={24} sm={12} xl={6}>
            <Card
              hoverable
              onClick={() => onNavigate(card.path)}
              style={{ height: '100%' }}
              bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 12 }}
            >
              {card.icon}
              <Title level={4} style={{ margin: 0 }}>
                {t(card.titleKey)}
              </Title>
              <Text type="secondary">{t(card.descKey)}</Text>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  )
}

export default function Home() {
  const navigate = useNavigate()
  const { t } = useTranslation('home')
  const [rootStatus, setRootStatus] = useState<RootStatus | null>(null)

  useEffect(() => {
    let active = true

    apiClient
      .get<RootStatus>('/')
      .then(({ data }) => {
        if (active) {
          setRootStatus(data)
        }
      })
      .catch(() => {
        if (active) {
          setRootStatus(null)
        }
      })

    return () => {
      active = false
    }
  }, [])

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={24} style={{ display: 'flex' }}>
        <Card
          style={{
            borderRadius: 16,
            background:
              'linear-gradient(135deg, rgba(15,118,110,0.08), rgba(29,78,216,0.08))',
          }}
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space wrap size={[8, 8]}>
              <Tag color="blue">{t('hero.paperFreeze')}</Tag>
              <Tag color="gold">{t('hero.paperBaseline')}</Tag>
            </Space>

            <Title level={1} style={{ margin: 0 }}>
              {t('title')}
            </Title>
            <Title level={3} style={{ margin: 0, fontWeight: 500 }}>
              {t('subtitle')}
            </Title>

            <Paragraph style={{ margin: 0, maxWidth: 860, fontSize: 16 }}>
              {t('hero.description')}
            </Paragraph>

            <Space wrap size={[12, 12]}>
              <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate('/analysis')}>
                {t('hero.snapshotLink')}
              </Button>
              <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate('/stats')}>
                {t('hero.currentStatusLink')}
              </Button>
            </Space>
          </Space>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={12} sm={12} lg={6}>
            <Card>
              <Statistic title={t('stats.species')} value={PAPER_SNAPSHOT.species} />
            </Card>
          </Col>
          <Col xs={12} sm={12} lg={6}>
            <Card>
              <Statistic
                title={t('stats.candidateEdges')}
                value={PAPER_SNAPSHOT.candidateEdges}
              />
            </Card>
          </Col>
          <Col xs={12} sm={12} lg={6}>
            <Card>
              <Statistic title={t('stats.experiments')} value={PAPER_SNAPSHOT.experiments} />
            </Card>
          </Col>
          <Col xs={12} sm={12} lg={6}>
            <Card>
              <Statistic title={t('stats.peaks')} value={PAPER_SNAPSHOT.peaks} />
            </Card>
          </Col>
        </Row>

        <EntrySection
          title={t('sections.startHere')}
          cards={startHereCards}
          onNavigate={navigate}
          t={t}
        />

        <EntrySection
          title={t('sections.advancedTools')}
          cards={advancedCards}
          onNavigate={navigate}
          t={t}
        />

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
