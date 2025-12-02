import { Routes, Route } from 'react-router-dom'
import { ConfigProvider } from 'antd'
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
          </Route>
        </Routes>
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
