import { useMemo } from 'react'
import { Layout, Menu } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { HomeOutlined, DatabaseOutlined, LinkOutlined, MedicineBoxOutlined, BarChartOutlined, ApartmentOutlined, DashboardOutlined, ExperimentOutlined, InteractionOutlined, RadarChartOutlined, BranchesOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { LanguageSwitch } from '@/components/LanguageSwitch'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation('nav')

  const menuItems = useMemo(() => [
    { key: '/', icon: <HomeOutlined />, label: t('home') },
    { key: '/stats', icon: <BarChartOutlined />, label: t('stats') },
    { key: '/genes', icon: <DatabaseOutlined />, label: t('genes') },
    { key: '/regulations', icon: <LinkOutlined />, label: t('regulations') },
    { key: '/diseases', icon: <MedicineBoxOutlined />, label: t('diseases') },
    { key: '/network', icon: <ApartmentOutlined />, label: t('network') },
    { key: '/conservation', icon: <BranchesOutlined />, label: t('conservation', 'Conservation') },
    { key: '/lncrna-chipseq-overlap', icon: <InteractionOutlined />, label: t('overlap') },
    { key: '/chipseq-compare', icon: <RadarChartOutlined />, label: t('chipseqCompare', 'ChIP-seq Compare') },
    { key: '/genome-browser', icon: <ExperimentOutlined />, label: t('genomeBrowser') },
    { type: 'divider' as const },
    { key: '/admin/monitoring', icon: <DashboardOutlined />, label: t('monitoring', 'Monitoring') },
  ], [t])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        color: 'white',
        fontSize: 20,
        fontWeight: 'bold'
      }}>
        <span>{t('siteTitle')}</span>
        <LanguageSwitch />
      </Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 24, background: '#fff' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
