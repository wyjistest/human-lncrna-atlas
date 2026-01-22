/**
 * Visualization Hub Page
 *
 * Central navigation page for all visualization features
 * Displays cards for each visualization type with descriptions
 */

import { Card, Row, Col, Typography, Space, Breadcrumb } from 'antd'
import {
  HomeOutlined,
  PartitionOutlined,
  ForkOutlined,
  RadarChartOutlined,
  HeatMapOutlined,
  ApartmentOutlined,
  DotChartOutlined
} from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const { Title, Paragraph, Text } = Typography

/**
 * Visualization card definition
 */
interface VisualizationCard {
  title: string
  description: string
  path: string
  icon: React.ReactNode
  color: string
  // Optional category tag
  category?: 'network' | 'flow' | 'matrix' | 'genomic'
}

/**
 * Visualization Hub Page Component
 */
export default function VisualizationHub() {
  const { t } = useTranslation('visualization')
  const navigate = useNavigate()

  // Define all visualizations
  const visualizations: VisualizationCard[] = [
    {
      title: t('hub.network.title', 'Network Graph'),
      description: t('hub.network.description', 'Interactive gene regulatory network with Cytoscape.js'),
      path: '/network',
      icon: <ApartmentOutlined style={{ fontSize: 48 }} />,
      color: '#1890ff',
      category: 'network'
    },
    {
      title: t('hub.sankey.title', 'Sankey Flow'),
      description: t('hub.sankey.description', 'lncRNA → Gene → Disease three-layer flow diagram'),
      path: '/visualization/sankey-flow',
      icon: <ForkOutlined style={{ fontSize: 48 }} />,
      color: '#52c41a',
      category: 'flow'
    },
    {
      title: t('hub.chord.title', 'Chord Diagram'),
      description: t('hub.chord.description', 'Circular relationship visualization (lncRNA ↔ Gene)'),
      path: '/visualization/chord',
      icon: <RadarChartOutlined style={{ fontSize: 48 }} />,
      color: '#722ed1',
      category: 'network'
    },
    {
      title: t('hub.conservation.title', 'Conservation Matrix'),
      description: t('hub.conservation.description', 'Cross-species conservation heatmap'),
      path: '/conservation',
      icon: <HeatMapOutlined style={{ fontSize: 48 }} />,
      color: '#fa8c16',
      category: 'matrix'
    },
    {
      title: t('hub.genome.title', 'Genome Browser'),
      description: t('hub.genome.description', 'IGV.js genomic visualization with tracks'),
      path: '/genome-browser',
      icon: <DotChartOutlined style={{ fontSize: 48 }} />,
      color: '#eb2f96',
      category: 'genomic'
    }
  ]

  return (
    <div style={{ padding: 24 }} data-testid="visualization-page">
      {/* Breadcrumb */}
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
              <>
                <PartitionOutlined />
                <span style={{ marginLeft: 4 }}>
                  {t('hub.breadcrumb', 'Visualizations')}
                </span>
              </>
            )
          }
        ]}
      />

      {/* Page Header */}
      <Space orientation="vertical" size="small" style={{ width: '100%', marginBottom: 32 }}>
        <Title level={2}>{t('hub.title', 'Visualization Hub')}</Title>
        <Paragraph type="secondary">
          {t(
            'hub.description',
            'Explore lncRNA regulatory relationships through interactive visualizations. Choose from network graphs, flow diagrams, heatmaps, and genomic browsers.'
          )}
        </Paragraph>
      </Space>

      {/* Visualization Cards */}
      <Row gutter={[24, 24]}>
        {visualizations.map((viz) => (
          <Col xs={24} sm={12} lg={8} key={viz.path}>
            <Card
              data-testid="visualization-card"
              hoverable
              onClick={() => navigate(viz.path)}
              style={{
                height: '100%',
                borderTop: `4px solid ${viz.color}`,
                cursor: 'pointer'
              }}
              styles={{
                body: {
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '32px 24px'
                }
              }}
            >
              <div style={{ color: viz.color, marginBottom: 16 }}>
                {viz.icon}
              </div>
              <Title level={4} style={{ marginBottom: 8 }}>
                {viz.title}
              </Title>
              <Text type="secondary" style={{ fontSize: 14 }}>
                {viz.description}
              </Text>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Additional Info Section */}
      <Card
        style={{ marginTop: 32 }}
        styles={{ body: { padding: 24 } }}
      >
        <Space orientation="vertical" size={16}>
          <Title level={4}>{t('hub.info.title', 'About Visualizations')}</Title>
          <Paragraph>
            {t(
              'hub.info.description',
              'Each visualization provides unique insights into lncRNA regulatory networks:'
            )}
          </Paragraph>
          <ul style={{ paddingLeft: 24 }}>
            <li>
              <Text strong>Network Graph: </Text>
              <Text>
                {t(
                  'hub.info.network',
                  'Explore complex regulatory relationships with interactive node-edge graphs. Filter by species, diseases, and binding affinity.'
                )}
              </Text>
            </li>
            <li>
              <Text strong>Sankey Flow: </Text>
              <Text>
                {t(
                  'hub.info.sankey',
                  'Visualize three-layer flow from lncRNAs through genes to diseases. Understand regulatory cascades.'
                )}
              </Text>
            </li>
            <li>
              <Text strong>Conservation Matrix: </Text>
              <Text>
                {t(
                  'hub.info.conservation',
                  'Compare conservation patterns across 4 primate species with interactive heatmaps. Click cells to explore shared regulations.'
                )}
              </Text>
            </li>
            <li>
              <Text strong>Genome Browser: </Text>
              <Text>
                {t(
                  'hub.info.genome',
                  'View genomic coordinates, ChIP-seq peaks, and RepeatMasker annotations on an IGV.js browser.'
                )}
              </Text>
            </li>
          </ul>
        </Space>
      </Card>
    </div>
  )
}
