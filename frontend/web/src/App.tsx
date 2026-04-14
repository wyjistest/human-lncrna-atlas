import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import { useTranslation } from 'react-i18next'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazyWithNamespaces } from './i18n/lazyWithNamespaces'
import MainLayout from './layouts/MainLayout'
import Home from './pages/Home'

// Lazy load route pages to keep initial bundle small
// Network: Cytoscape.js (~460KB gzipped)
const Network = lazyWithNamespaces(() => import('./pages/Network'), ['network'])
// Analysis: Various analysis components
const Analysis = lazyWithNamespaces(() => import('./pages/Analysis'), ['analysis'])
const Snapshot = lazyWithNamespaces(() => import('./pages/Snapshot'), ['snapshot'])
// Visualization: ECharts (~375KB gzipped)
const VisualizationHub = lazyWithNamespaces(() => import('./pages/Visualization'), ['visualization'])
const SankeyFlow = lazyWithNamespaces(() => import('./pages/Visualization/SankeyFlow'), ['visualization'])
const ChordDiagram = lazyWithNamespaces(() => import('./pages/Visualization/ChordDiagram'), ['visualization'])
// GenomeBrowser: IGV.js (~396KB gzipped)
const GenomeBrowser = lazyWithNamespaces(() => import('./pages/GenomeBrowser'), ['genomeBrowser'])

// Other pages (lazy to avoid pulling charts/export libs into the home route)
const Stats = lazyWithNamespaces(() => import('./pages/Stats'), ['stats'])
const Genes = lazyWithNamespaces(() => import('./pages/Genes'), ['genes'])
const GeneDetail = lazyWithNamespaces(
  () => import('./pages/GeneDetail'),
  ['genes', 'regulations', 'genomeBrowser'],
)
const Regulations = lazyWithNamespaces(
  () => import('./pages/Regulations'),
  ['regulations', 'genomeBrowser'],
)
const Diseases = lazyWithNamespaces(() => import('./pages/Diseases'), ['diseases'])
const Conservation = lazyWithNamespaces(() => import('./pages/Conservation'), ['conservation'])
const Monitoring = lazy(() => import('./pages/Admin/Monitoring'))
const CacheManagement = lazy(() => import('./pages/Admin/Cache'))
const MaterializedViews = lazy(() => import('./pages/Admin/MaterializedViews'))
const LncRNAChIPSeqOverlapPage = lazyWithNamespaces(
  () => import('./pages/LncRNAChIPSeqOverlapPage'),
  ['overlap'],
)
const ChIPSeqComparePage = lazyWithNamespaces(
  () => import('./pages/ChIPSeqComparePage'),
  ['globalCompare', 'genes'],
)

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
      <ConfigProvider
        locale={antdLocale}
        theme={{
          token: {
            // AntD 默认 primary（#1677ff）在白底 14px 文本下对比度略低（axe: color-contrast）。
            // 选择更深的蓝色以满足 WCAG AA（≥4.5:1）。
            colorPrimary: '#0958d9',
            // breadcrumb / secondary 描述文本默认较浅（约 #8c8c8c），对比度不足；提升可读性。
            colorTextDescription: '#595959',
          },
        }}
      >
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
            <Route path="snapshot" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <Snapshot />
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
            <Route path="admin/cache" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <CacheManagement />
              </Suspense>
            } />
            <Route path="admin/materialized-views" element={
              <Suspense fallback={<LazyLoadFallback />}>
                <MaterializedViews />
              </Suspense>
            } />
          </Route>
        </Routes>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
