/**
 * Cytoscape 类型扩展
 * 补充 cytoscape 自带类型定义中缺失的方法
 */

import cytoscape from 'cytoscape'

declare module 'cytoscape' {
  // 扩展默认导出函数
  export function use(ext: Ext): void

  /**
   * EventObject - Cytoscape 事件对象
   * 用于事件处理器回调函数的参数类型
   */
  export interface EventObject {
    /** 事件类型 (如 "tap", "mouseover") */
    type: string
    /** 事件命名空间 */
    namespace: string
    /** 触发事件的元素或 Core */
    target: NodeSingular | EdgeSingular | Core
    /** 对应的 Core 实例 */
    cy: Core
    /** 事件时间戳 */
    timeStamp: number
    /** 原始浏览器事件 (如果适用) */
    originalEvent?: MouseEvent | TouchEvent | KeyboardEvent
    /** 渲染位置 */
    renderedPosition?: { x: number; y: number }
    /** 模型位置 */
    position?: { x: number; y: number }
    /** 阻止默认行为 */
    preventDefault: () => void
    /** 停止传播 */
    stopPropagation: () => void
    /** 立即停止传播 */
    stopImmediatePropagation: () => void
  }

  // NodeSingular 类型（如果缺失）
  export interface NodeSingular extends Singular {
    data(name?: string): unknown
    data(name: string, value: unknown): this
    degree(includeLoops?: boolean): number
    addClass(classes: string): this
    removeClass(classes: string): this
  }

  interface Core {
    // 事件方法 - 支持多种签名
    on(events: string, handler: (evt: EventObject) => void): this
    on(events: string, selector: string, handler: (evt: EventObject) => void): this
    off(events: string, handler?: (evt: EventObject) => void): this
    off(events: string, selector?: string, handler?: (evt: EventObject) => void): this

    // 元素选择
    nodes(selector?: string): NodeCollection
    edges(selector?: string): EdgeCollection
    $id(id: string): NodeSingular | EdgeSingular

    // 视图方法
    fit(eles?: Collection, padding?: number): this
    center(eles?: Collection): this
    animate(options: AnimateOptions, params?: AnimateParams): this

    // 布局
    layout(options: LayoutOptions): Layouts

    // 导出
    png(options?: ExportOptions): string
    jpg(options?: ExportOptions): string
    svg(options?: SvgExportOptions): string

    // 生命周期
    destroy(): void
  }

  interface AnimateOptions {
    zoom?: number
    pan?: Position
    center?: { eles: Collection }
    fit?: { eles: Collection; padding?: number }
  }

  interface AnimateParams {
    duration?: number
    easing?: string
    complete?: () => void
  }

  interface ExportOptions {
    output?: 'blob' | 'base64uri' | 'base64'
    bg?: string
    full?: boolean
    scale?: number
    maxWidth?: number
    maxHeight?: number
    quality?: number
  }

  interface SvgExportOptions {
    full?: boolean
    scale?: number
    bg?: string
    quality?: number
  }

  // 扩展类型
  type Ext = (cy: typeof cytoscape) => void

  // CytoscapeOptions（如果缺失）
  interface CytoscapeOptions {
    container?: HTMLElement | null
    elements?: ElementDefinition[]
    style?: StylesheetStyle[]
    layout?: LayoutOptions
    [key: string]: unknown
  }
}
