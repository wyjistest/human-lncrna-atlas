import { useEffect, useMemo, useState } from 'react'
import { Button, Drawer, Grid, Layout, Menu } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { MenuOutlined, HomeOutlined, DatabaseOutlined, LinkOutlined, MedicineBoxOutlined, BarChartOutlined, ApartmentOutlined, DashboardOutlined, ExperimentOutlined, InteractionOutlined, RadarChartOutlined, BranchesOutlined, LineChartOutlined, DeleteOutlined, TableOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { LanguageSwitch } from '@/components/LanguageSwitch'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation('nav')
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    if (!isMobile) {
      setDrawerOpen(false)
    }
  }, [isMobile])

  // Compute selected keys based on path matching
  // This handles child routes like /genes/:id highlighting the parent /genes menu item
  const selectedKeys = useMemo(() => {
    const pathname = location.pathname
    // Define menu paths in order of specificity (longer paths first)
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
    { key: '/stats', icon: <BarChartOutlined />, label: t('stats') },
    { key: '/genes', icon: <DatabaseOutlined />, label: t('genes') },
    { key: '/regulations', icon: <LinkOutlined />, label: t('regulations') },
    { key: '/diseases', icon: <MedicineBoxOutlined />, label: t('diseases') },
    { key: '/network', icon: <ApartmentOutlined />, label: t('network') },
    { key: '/conservation', icon: <BranchesOutlined />, label: t('conservation', 'Conservation') },
    { key: '/analysis', icon: <LineChartOutlined />, label: t('analysis', 'Analysis') },
    { key: '/lncrna-chipseq-overlap', icon: <InteractionOutlined />, label: t('overlap') },
    { key: '/chipseq-compare', icon: <RadarChartOutlined />, label: t('chipseqCompare', 'ChIP-seq Compare') },
    { key: '/genome-browser', icon: <ExperimentOutlined />, label: t('genomeBrowser') },
    { type: 'divider' as const },
    { key: '/admin/cache', icon: <DeleteOutlined />, label: t('cache', 'Cache') },
    { key: '/admin/materialized-views', icon: <TableOutlined />, label: t('materializedViews', 'Materialized Views') },
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
