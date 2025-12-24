/**
 * Axios 客户端配置
 *
 * 注意: 错误处理已移至 QueryClient 的 QueryCache/MutationCache 全局处理
 * 参见 src/main.tsx 中的 queryClient 配置
 */
import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT, ADMIN_API_KEY } from '@/config/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // ⚠️ SECURITY WARNING ⚠️
    // Admin API Key 通过前端环境变量注入，会随构建产物暴露。
    // 仅适用于以下场景：
    //   1. Admin 页面仅在内网/VPN 访问
    //   2. 使用反向代理（如 Nginx）注入 X-Admin-API-Key
    //   3. 开发/测试环境
    // 生产公网环境建议使用后端会话式鉴权替代。
    const isAdminRequest = config.url?.includes('/admin')

    // SECURITY: Only allow frontend-provided Admin API Key in DEV builds.
    // Production builds must rely on reverse proxy injection or backend auth.
    if (isAdminRequest && import.meta.env.DEV && ADMIN_API_KEY) {
      config.headers['X-Admin-API-Key'] = ADMIN_API_KEY;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
// 注意: 不在此处调用 message.error()，由 React Query 全局处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 直接 reject 错误，让 React Query 的 QueryCache.onError 处理
    return Promise.reject(error);
  }
);
