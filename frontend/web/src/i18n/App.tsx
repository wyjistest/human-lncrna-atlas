import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import { useTranslation } from 'react-i18next'
import { ErrorBoundary } from './components/ErrorBoundary'
import MainLayout from './layouts/MainLayout'
import Home from './pages/Home'
import Stats from './pages/Stats'
import Genes from './pages/Genes'
import GeneDetail from './pages/GeneDetail'
import Regulations from './pages/Regulations'
import Diseases from './pages/Diseases'
import Network from './pages/Network'
import Monitoring from './pages/Admin/Monitoring'
import LncRNAChIPSeqOverlapPage from './pages/LncRNAChIPSeqOverlapPage'

// Lazy load GenomeBrowser (large IGV.js bundle)
const GenomeBrowser = lazy(() => import('./pages/GenomeBrowser'))

// Loading fallback for lazy loaded routes
const LazyLoadFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
    <Spin size="large" />
  </div>
)

function App() {
  const { i18n } = useTranslation()

  // Ant Design 语言包与 i18n 同步
  const antdLocale = i18n.language?.startsWith('en') ? enUS : zhCN

  return (
    <ErrorBoundary>
      <ConfigProvider locale={antdLocale}>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Home />} />
            <Route path="stats" element={<Stats />} />
            <Route path="genes" element={<Genes />} />
            <Route path="genes/:geneId" element={<GeneDetail />} />
            <Route path="regulations" element={<Regulations />} />
            <Route path="diseases" element={<Diseases />} />
            <Route path="network" element={<Network />} />
            <Route path="genome-browser" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <GenomeBrowser />
              </Suspense>
            } />
            <Route path="lncrna-chipseq-overlap" element={<LncRNAChIPSeqOverlapPage />} />
            <Route path="admin/monitoring" element={<Monitoring />} />
          </Route>
        </Routes>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
