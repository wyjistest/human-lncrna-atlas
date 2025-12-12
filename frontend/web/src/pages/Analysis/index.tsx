/**
 * Analysis Results Page
 *
 * Displays scientific analysis results from Jupyter Notebooks (Phase 6.0-B)
 * with 4 tabs: High Affinity, Conservation, Epigenetic, Disease Networks
 */

import { useState, lazy, Suspense } from 'react'
import { Tabs, Spin } from 'antd'
import { ExperimentOutlined, BranchesOutlined, RadarChartOutlined, ApartmentOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { TabsProps } from 'antd'

// Lazy load tab components for better performance
const HighAffinityTab = lazy(() => import('./components/HighAffinityTab'))
const ConservationTab = lazy(() => import('./components/ConservationTab'))
const EpigeneticTab = lazy(() => import('./components/EpigeneticTab'))
const DiseaseTab = lazy(() => import('./components/DiseaseTab'))

// Loading fallback
const TabLoadingFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
    <Spin size="large" />
  </div>
)

export default function Analysis() {
  const { t } = useTranslation('analysis')
  const [activeTab, setActiveTab] = useState('highAffinity')

  const items: TabsProps['items'] = [
    {
      key: 'highAffinity',
      label: (
        <span>
          <ExperimentOutlined />
          {t('tabs.highAffinity')}
        </span>
      ),
      children: (
        <Suspense fallback={<TabLoadingFallback />}>
          <HighAffinityTab />
        </Suspense>
      ),
    },
    {
      key: 'conservation',
      label: (
        <span>
          <BranchesOutlined />
          {t('tabs.conservation')}
        </span>
      ),
      children: (
        <Suspense fallback={<TabLoadingFallback />}>
          <ConservationTab />
        </Suspense>
      ),
    },
    {
      key: 'epigenetic',
      label: (
        <span>
          <RadarChartOutlined />
          {t('tabs.epigenetic')}
        </span>
      ),
      children: (
        <Suspense fallback={<TabLoadingFallback />}>
          <EpigeneticTab />
        </Suspense>
      ),
    },
    {
      key: 'disease',
      label: (
        <span>
          <ApartmentOutlined />
          {t('tabs.disease')}
        </span>
      ),
      children: (
        <Suspense fallback={<TabLoadingFallback />}>
          <DiseaseTab />
        </Suspense>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, marginBottom: 8 }}>{t('title')}</h1>
        <p style={{ color: '#666', margin: 0 }}>{t('description')}</p>
      </div>

      <Tabs
        activeKey={activeTab}
        items={items}
        onChange={setActiveTab}
        destroyInactiveTabPane
        size="large"
      />
    </div>
  )
}
