import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });

    this.client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          try {
            const refreshToken = localStorage.getItem('refresh_token');
            if (refreshToken) {
              const { data } = await axios.post(`${API_BASE}/auth/refresh`, null, {
                headers: { Authorization: `Bearer ${refreshToken}` },
              });
              localStorage.setItem('access_token', data.data.access_token);
              originalRequest.headers.Authorization = `Bearer ${data.data.access_token}`;
              return this.client(originalRequest);
            }
          } catch {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            if (typeof window !== 'undefined') {
              window.location.href = '/auth/login';
            }
          }
        }
        return Promise.reject(error);
      },
    );
  }

  get(url: string, params?: Record<string, unknown>) {
    return this.client.get(url, { params });
  }

  getBlob(url: string, params?: Record<string, unknown>) {
    return this.client.get(url, { params, responseType: 'blob' });
  }

  post(url: string, data?: unknown) {
    return this.client.post(url, data);
  }

  patch(url: string, data?: unknown) {
    return this.client.patch(url, data);
  }

  delete(url: string) {
    return this.client.delete(url);
  }

  upload(url: string, formData: FormData) {
    return this.client.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
}

export const api = new ApiClient();

