import { useEffect, useMemo, useState } from 'react'
import { Button, Drawer, Grid, Layout, Menu, Typography } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  ApartmentOutlined,
  BranchesOutlined,
  DatabaseOutlined,
  HomeOutlined,
  InteractionOutlined,
  LineChartOutlined,
  MedicineBoxOutlined,
  MenuOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { LanguageSwitch } from '@/components/LanguageSwitch'
import { useRootStatus } from '@/hooks/useRootStatus'

const { Header, Sider, Content, Footer } = Layout
const { Text } = Typography

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation('nav')
  const { t: tHome } = useTranslation('home')
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { data: rootStatus } = useRootStatus()

  useEffect(() => {
    if (!isMobile) {
      setDrawerOpen(false)
    }
  }, [isMobile])

  // Compute selected keys based on path matching
  // This handles child routes like /genes/:id highlighting the parent /genes menu item
  const selectedKeys = useMemo(() => {
    const pathname = location.pathname
    const menuPaths = [
      '/admin/materialized-views',
      '/admin/cache',
      '/admin/monitoring',
      '/lncrna-chipseq-overlap',
      '/chipseq-compare',
      '/genome-browser',
      '/conservation',
      '/regulations',
      '/analysis',
      '/diseases',
      '/network',
      '/genes',
      '/stats',
      '/',
    ]
    // Find the first menu path that matches the current location
    const matchedPath = menuPaths.find((path) => {
      if (path === '/') {
        return pathname === '/'
      }
      return pathname === path || pathname.startsWith(`${path}/`)
    })
    return matchedPath ? [matchedPath] : [pathname]
  }, [location.pathname])

  const menuItems = useMemo(() => [
    { key: '/', icon: <HomeOutlined />, label: t('home') },
    { key: '/genes', icon: <DatabaseOutlined />, label: t('genes') },
    { key: '/diseases', icon: <MedicineBoxOutlined />, label: t('diseases') },
    { key: '/network', icon: <ApartmentOutlined />, label: t('network') },
    { key: '/conservation', icon: <BranchesOutlined />, label: t('conservation', 'Conservation') },
    { key: '/analysis', icon: <LineChartOutlined />, label: t('analysis', 'Analysis') },
    { key: '/lncrna-chipseq-overlap', icon: <InteractionOutlined />, label: t('overlap') },
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {isMobile && (
            <Button
              type="text"
              aria-label="Open navigation menu"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              style={{ color: 'white' }}
            />
          )}
          <span>{t('siteTitle')}</span>
        </div>
        <LanguageSwitch />
      </Header>
      <Layout>
        {!isMobile && (
          <Sider width={200} theme="light">
            <Menu
              mode="inline"
              selectedKeys={selectedKeys}
              items={menuItems}
              onClick={({ key }) => navigate(key)}
            />
          </Sider>
        )}
        <Content style={{ padding: 24, background: '#fff' }}>
          <Outlet />
        </Content>
      </Layout>
      <Footer style={{ padding: '12px 24px', background: '#fff', borderTop: '1px solid #f0f0f0' }}>
        <Text type="secondary">
          {tHome('sections.provenance')}
          {' · '}
          {tHome('status.apiVersion')}: {rootStatus?.version ?? tHome('status.unavailable')}
          {' · '}
          {tHome('status.dbMode')}: {rootStatus?.db_mode ?? tHome('status.unavailable')}
          {' · '}
          {tHome('status.dbName')}: {rootStatus?.db_name ?? tHome('status.unavailable')}
        </Text>
      </Footer>

      <Drawer
        placement="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        size="default"
        styles={{ body: { padding: 0 } }}
      >
        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          onClick={({ key }) => {
            navigate(key)
            setDrawerOpen(false)
          }}
        />
      </Drawer>
    </Layout>
  )
}
