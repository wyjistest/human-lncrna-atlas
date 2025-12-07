/**
 * Type declarations for cytoscape-svg
 * cytoscape-svg 不导出类型，需要本地声明
 */

declare module 'cytoscape-svg' {
  import cytoscape from 'cytoscape'
  const ext: cytoscape.Ext
  export default ext
}

// 扩展 Cytoscape Core 类型
declare module 'cytoscape' {
  interface SvgExportOptions {
    /** 是否包含完整图形（包括视口外的节点） */
    full?: boolean
    /** 缩放比例 */
    scale?: number
    /** 背景颜色 */
    bg?: string
    /** 图片质量 (0-1) */
    quality?: number
  }

  interface Core {
    /** 导出为 SVG 字符串 */
    svg(options?: SvgExportOptions): string
  }
}
