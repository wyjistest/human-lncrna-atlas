/**
 * Axios客户端配置
 */
import axios from 'axios';
import { message } from 'antd';

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
    // 可以在这里添加token等
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 统一错误处理
    if (error.response) {
      const { status, data } = error.response;

      switch (status) {
        case 429:
          message.error('请求过于频繁，请稍后再试');
          break;
        case 500:
          message.error(data.detail || '服务器错误');
          break;
        case 404:
          message.error('资源不存在');
          break;
        default:
          message.error(data.detail || '请求失败');
      }
    } else if (error.request) {
      message.error('网络错误，请检查连接');
    }

    return Promise.reject(error);
  }
);
