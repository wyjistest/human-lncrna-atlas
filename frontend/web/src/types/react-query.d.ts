/**
 * TanStack React Query 全局类型注册
 *
 * Phase 9.18 - Codex审查修复
 *
 * 注册全局默认错误类型为 Error，保持与现有代码兼容
 * 虽然 TanStack Query v5 推荐使用 unknown，但我们的代码库
 * 已经广泛使用 Error 类型，为避免大规模重构，保持现有行为
 *
 * 各组件的 error prop 已经接受 unknown 类型，
 * 实际的错误类型安全通过 parseError 工具函数保障
 *
 * @see https://tanstack.com/query/v5/docs/framework/react/typescript
 */
import '@tanstack/react-query'

declare module '@tanstack/react-query' {
  interface Register {
    /**
     * 全局默认错误类型
     *
     * 使用 Error 保持与现有代码的兼容性
     * 错误类型收窄由 parseError 工具函数处理
     */
    defaultError: Error
  }
}
