import enAnalysis from './en/analysis.json'
import enConservation from './en/conservation.json'
import enDiseases from './en/diseases.json'
import enGenomeBrowser from './en/genomeBrowser.json'
import enHome from './en/home.json'
import enNav from './en/nav.json'
import enNetwork from './en/network.json'
import enOverlap from './en/overlap.json'
import enRegulations from './en/regulations.json'
import zhAnalysis from './zh-CN/analysis.json'
import zhConservation from './zh-CN/conservation.json'
import zhDiseases from './zh-CN/diseases.json'
import zhGenomeBrowser from './zh-CN/genomeBrowser.json'
import zhHome from './zh-CN/home.json'
import zhNav from './zh-CN/nav.json'
import zhNetwork from './zh-CN/network.json'
import zhOverlap from './zh-CN/overlap.json'
import zhRegulations from './zh-CN/regulations.json'

describe('paper-first narrative locale content', () => {
  it('aligns English public labels with the paper-facing narrative', () => {
    expect(enHome.title).toBe('Human LncRNA Atlas Companion')
    expect(enNav.home).toBe('Overview')
    expect(enNav.diseases).toBe('Traits')
    expect(enNav.network).toBe('Trait-centered Networks')
    expect(enNav.conservation).toBe('Conservation & Rewiring')
    expect(enNav.overlap).toBe('Epigenomic Context')
    expect(enNav.analysis).toBe('Evidence Hub')

    expect(enDiseases.title).toBe('Traits & Associations')
    expect(enRegulations.title).toBe('Candidate Regulatory Edges')
    expect(enNetwork.title).toBe('Trait-centered Networks')
    expect(enConservation.title).toBe('Conservation & Rewiring')
    expect(enAnalysis.title).toBe('Evidence Hub')
    expect(enAnalysis.tabs.highAffinity).toBe('Global Architecture')
    expect(enAnalysis.tabs.conservation).toBe('Conservation & Rewiring')
    expect(enAnalysis.tabs.epigenetic).toBe('Epigenomic Context')
    expect(enAnalysis.tabs.disease).toBe('Trait-centered Subnetworks')
    expect(enOverlap.page.title).toBe('Epigenomic Context')
    expect(enOverlap.page.description).not.toMatch(/enrich/i)
    expect(enOverlap.page.description).toMatch(/overlap|co-localization|context/i)
    expect(enGenomeBrowser.chipseq.baselineGuide).toMatch(/8 core histone marks \+ DNase-HS/)
    expect(enGenomeBrowser.chipseq.baselineGuide).toMatch(/CTCF/)
    expect(enGenomeBrowser.chipseq.baselineGuide).toMatch(/H4K20me1/)
  })

  it('aligns Simplified Chinese public labels with the same narrative', () => {
    expect(zhHome.title).toBe('Human LncRNA Atlas Companion')
    expect(zhNav.home).toBe('总览')
    expect(zhNav.diseases).toBe('性状')
    expect(zhNav.network).toBe('性状中心网络')
    expect(zhNav.conservation).toBe('保守性与重连')
    expect(zhNav.overlap).toBe('表观组学背景')
    expect(zhNav.analysis).toBe('证据中心')

    expect(zhDiseases.title).toBe('性状与关联')
    expect(zhRegulations.title).toBe('候选调控边')
    expect(zhNetwork.title).toBe('性状中心网络')
    expect(zhConservation.title).toBe('保守性与重连')
    expect(zhAnalysis.title).toBe('证据中心')
    expect(zhAnalysis.tabs.highAffinity).toBe('全局架构')
    expect(zhAnalysis.tabs.conservation).toBe('保守性与重连')
    expect(zhAnalysis.tabs.epigenetic).toBe('表观组学背景')
    expect(zhAnalysis.tabs.disease).toBe('性状中心子网络')
    expect(zhOverlap.page.title).toBe('表观组学背景')
    expect(zhOverlap.page.description).not.toMatch(/富集/)
    expect(zhOverlap.page.description).toMatch(/重叠|共定位|背景/)
    expect(zhGenomeBrowser.chipseq.baselineGuide).toMatch(/8 种核心组蛋白标记 \+ DNase-HS/)
    expect(zhGenomeBrowser.chipseq.baselineGuide).toMatch(/CTCF/)
    expect(zhGenomeBrowser.chipseq.baselineGuide).toMatch(/H4K20me1/)
  })
})
