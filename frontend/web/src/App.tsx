import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import { useTranslation } from 'react-i18next'
import { ErrorBoundary } from './components/ErrorBoundary'
import MainLayout from './layouts/MainLayout'
import Home from './pages/Home'

// Lazy load route pages to keep initial bundle small
// Network: Cytoscape.js (~460KB gzipped)
const Network = lazy(() => import('./pages/Network'))
// Analysis: Various analysis components
const Analysis = lazy(() => import('./pages/Analysis'))
// Visualization: ECharts (~375KB gzipped)
const VisualizationHub = lazy(() => import('./pages/Visualization'))
const SankeyFlow = lazy(() => import('./pages/Visualization/SankeyFlow'))
const ChordDiagram = lazy(() => import('./pages/Visualization/ChordDiagram'))
// GenomeBrowser: IGV.js (~396KB gzipped)
const GenomeBrowser = lazy(() => import('./pages/GenomeBrowser'))

// Other pages (lazy to avoid pulling charts/export libs into the home route)
const Stats = lazy(() => import('./pages/Stats'))
const Genes = lazy(() => import('./pages/Genes'))
const GeneDetail = lazy(() => import('./pages/GeneDetail'))
const Regulations = lazy(() => import('./pages/Regulations'))
const Diseases = lazy(() => import('./pages/Diseases'))
const Conservation = lazy(() => import('./pages/Conservation'))
const Monitoring = lazy(() => import('./pages/Admin/Monitoring'))
const LncRNAChIPSeqOverlapPage = lazy(() => import('./pages/LncRNAChIPSeqOverlapPage'))
const ChIPSeqComparePage = lazy(() => import('./pages/ChIPSeqComparePage'))

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
            <Route path="stats" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Stats />
              </Suspense>
            } />
            <Route path="genes" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Genes />
              </Suspense>
            } />
            <Route path="genes/:geneId" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <GeneDetail />
              </Suspense>
            } />
            <Route path="regulations" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Regulations />
              </Suspense>
            } />
            <Route path="diseases" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Diseases />
              </Suspense>
            } />
            <Route path="network" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Network />
              </Suspense>
            } />
            <Route path="conservation" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Conservation />
              </Suspense>
            } />
            <Route path="analysis" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Analysis />
              </Suspense>
            } />
            <Route path="genome-browser" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <GenomeBrowser />
              </Suspense>
            } />
            <Route path="lncrna-chipseq-overlap" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <LncRNAChIPSeqOverlapPage />
              </Suspense>
            } />
            <Route path="chipseq-compare" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <ChIPSeqComparePage />
              </Suspense>
            } />
            <Route path="visualization" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <VisualizationHub />
              </Suspense>
            } />
            <Route path="visualization/chord" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <ChordDiagram />
              </Suspense>
            } />
            <Route path="visualization/sankey-flow" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <SankeyFlow />
              </Suspense>
            } />
            <Route path="admin/monitoring" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Monitoring />
              </Suspense>
            } />
          </Route>
        </Routes>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
