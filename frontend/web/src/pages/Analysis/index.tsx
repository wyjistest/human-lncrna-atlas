/**
 * Analysis Results Page
 *
 * Displays scientific analysis results from Jupyter Notebooks (Phase 6.0-B)
 * with 4 tabs: High Affinity, Conservation, Epigenetic, Disease Networks
 */

import { lazy, Suspense } from 'react'
import { Tabs, Spin } from 'antd'
import { ExperimentOutlined, BranchesOutlined, RadarChartOutlined, ApartmentOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { TabsProps } from 'antd'
import { useSearchParams } from 'react-router-dom'

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

type AnalysisTabKey = 'highAffinity' | 'conservation' | 'epigenetic' | 'disease'

const DEFAULT_TAB: AnalysisTabKey = 'highAffinity'
const ANALYSIS_TABS: AnalysisTabKey[] = ['highAffinity', 'conservation', 'epigenetic', 'disease']

function parseTab(value: string | null): AnalysisTabKey {
  const v = value as AnalysisTabKey | null
  return v && ANALYSIS_TABS.includes(v) ? v : DEFAULT_TAB
}

export default function Analysis() {
  const { t } = useTranslation('analysis')
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTab = parseTab(searchParams.get('tab'))

  const updateParams = (apply: (params: URLSearchParams) => void) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      apply(next)
      return next
    }, { replace: true })
  }

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
    <div style={{ padding: 24 }} data-testid="analysis-page">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, marginBottom: 8 }}>{t('title')}</h1>
        <p style={{ color: '#666', margin: 0 }}>{t('description')}</p>
      </div>

      <div data-testid="analysis-tabs">
        <Tabs
          activeKey={activeTab}
          items={items}
          onChange={(key) => {
            const nextTab = parseTab(key)
            updateParams((params) => {
              if (nextTab === DEFAULT_TAB) params.delete('tab')
              else params.set('tab', nextTab)
              params.delete('page')
            })
          }}
          destroyOnHidden
          size="large"
        />
      </div>
    </div>
  )
}
