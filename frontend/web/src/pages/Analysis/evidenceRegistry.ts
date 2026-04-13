export type AnalysisTabKey = 'highAffinity' | 'conservation' | 'epigenetic' | 'disease'

export interface AnalysisEvidenceItem {
  id: string
  label: string
  href: string
}

export interface AnalysisTabDescriptor {
  summaryKey: string
  downstreamActionKey?: string
  evidence: AnalysisEvidenceItem[]
  downstreamReady: boolean
}

const GITHUB_BLOB_BASE_URL = 'https://github.com/wyjistest/human-lncrna-atlas/blob/main'

function createDocHref(path: string): string {
  return `${GITHUB_BLOB_BASE_URL}/${path}`
}

const ANALYSIS_TAB_DESCRIPTORS: Record<AnalysisTabKey, AnalysisTabDescriptor> = {
  highAffinity: {
    summaryKey: 'tabIntro.highAffinity',
    downstreamActionKey: 'workspace.openRegulations',
    downstreamReady: true,
    evidence: [
      {
        id: 'results-summary',
        label: 'Results Summary',
        href: createDocHref('docs/paper/results_summary.md'),
      },
    ],
  },
  conservation: {
    summaryKey: 'tabIntro.conservation',
    downstreamReady: false,
    evidence: [
      {
        id: 'results-summary',
        label: 'Results Summary',
        href: createDocHref('docs/paper/results_summary.md'),
      },
    ],
  },
  epigenetic: {
    summaryKey: 'tabIntro.epigenetic',
    downstreamActionKey: 'workspace.openOverlap',
    downstreamReady: true,
    evidence: [
      {
        id: 'overlap-test-guide',
        label: 'Overlap Test Guide',
        href: createDocHref('docs/reports/HOW_TO_TEST_OVERLAP_PAGE.md'),
      },
      {
        id: 'chipseq-audit',
        label: 'ChIP-seq Audit',
        href: createDocHref('docs/reports/CHIPSEQ_HG19_AUDIT_AND_ASSOCIATIONS_2026-02-12.md'),
      },
    ],
  },
  disease: {
    summaryKey: 'tabIntro.disease',
    downstreamActionKey: 'workspace.openNetwork',
    downstreamReady: true,
    evidence: [
      {
        id: 'results-summary',
        label: 'Results Summary',
        href: createDocHref('docs/paper/results_summary.md'),
      },
    ],
  },
}

export function getAnalysisTabDescriptor(tabKey: AnalysisTabKey): AnalysisTabDescriptor {
  return ANALYSIS_TAB_DESCRIPTORS[tabKey]
}
