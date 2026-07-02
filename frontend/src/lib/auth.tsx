'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api } from './api';

interface User {
  id: string;
  district_id: string;
  email: string;
  full_name: string;
  roles: string[];
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (districtId: string, email: string, password: string) => Promise<void>;
  loginWithOtp: (districtId: string, email: string, otpCode: string) => Promise<void>;
  sendOtp: (email: string, districtId?: string) => Promise<{ otp?: string }>;
  logout: () => void;
  isAuthenticated: boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUser({
          id: payload.sub,
          district_id: payload.district_id,
          email: payload.email,
          full_name: payload.email || 'User',
          roles: payload.roles || [],
        });
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (districtId: string, email: string, password: string) => {
    const { data } = await api.post('/auth/login', { district_id: districtId, email, password });
    localStorage.setItem('access_token', data.data.access_token);
    localStorage.setItem('refresh_token', data.data.refresh_token);
    setUser(data.data.user);
    router.push('/dashboard');
  }, [router]);

  const sendOtp = useCallback(async (email: string, districtId?: string) => {
    const { data } = await api.post('/auth/otp/send', { email, district_id: districtId || 'system' });
    return data.data as { otp?: string };
  }, []);

  const loginWithOtp = useCallback(async (districtId: string, email: string, otpCode: string) => {
    const { data } = await api.post('/auth/otp/login', {
      district_id: districtId, email, otp_code: otpCode,
    });
    localStorage.setItem('access_token', data.data.access_token);
    localStorage.setItem('refresh_token', data.data.refresh_token);
    setUser(data.data.user);
    router.push('/dashboard');
  }, [router]);

  const logout = useCallback(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      api.post('/auth/logout').catch(() => {});
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    router.push('/auth/login');
  }, [router]);

  const hasPermission = useCallback((resource: string, action: string) => {
    return true;
  }, []);

  return (
    <AuthContext.Provider value={{
      user, loading, login, loginWithOtp, sendOtp, logout,
      isAuthenticated: !!user, hasPermission,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
