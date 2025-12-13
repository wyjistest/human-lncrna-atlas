/**
 * Axios 客户端配置
 *
 * 注意: 错误处理已移至 QueryClient 的 QueryCache/MutationCache 全局处理
 * 参见 src/main.tsx 中的 queryClient 配置
 */
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token 等认证信息
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
