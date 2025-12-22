/**
 * 类型统一导出文件
 *
 * 规范：所有组件必须从 '@/types' 导入类型
 * 禁止直接从 './api' 或 './api-extensions' 导入
 */

// 引入 React Query 全局类型扩展（Phase 9.18）
// 该文件注册 defaultError: unknown，强制显式错误类型收窄
import './react-query.d'

// 导出 OpenAPI 自动生成的类型
export * from './api'

// 导出扩展类型（不包含与 network.ts 重复的类型）
export * from './api-extensions'

// 导出网络可视化类型（优先使用 network.ts 中的定义）
export * from './network'

// 导出监控相关类型
export * from './monitoring'

// 导出统计相关类型
export * from './stats'
