'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface DashboardStats {
  total_service_requests: number;
  open_requests: number;
  published_posts: number;
  scheduled_posts: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/analytics/reach').then(({ data }) => {
      setStats(data.data || { total_service_requests: 0, open_requests: 0, published_posts: 0, scheduled_posts: 0 });
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    );
  }

  const cards = [
    { label: 'Service Requests', value: stats?.total_service_requests ?? 0, color: 'bg-blue-500' },
    { label: 'Open Requests', value: stats?.open_requests ?? 0, color: 'bg-amber-500' },
    { label: 'Published Posts', value: stats?.published_posts ?? 0, color: 'bg-green-500' },
    { label: 'Scheduled Posts', value: stats?.scheduled_posts ?? 0, color: 'bg-purple-500' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard Overview</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((card) => (
          <div key={card.label} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${card.color}`} />
              <div>
                <p className="text-sm text-gray-500">{card.label}</p>
                <p className="text-2xl font-bold text-gray-900">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/dashboard/service-requests" className="block p-4 border border-gray-200 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors">
            <p className="font-medium text-gray-900">View Service Requests</p>
            <p className="text-sm text-gray-500 mt-1">Manage citizen grievances</p>
          </a>
          <a href="/dashboard/social" className="block p-4 border border-gray-200 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors">
            <p className="font-medium text-gray-900">Social Media</p>
            <p className="text-sm text-gray-500 mt-1">Manage posts and accounts</p>
          </a>
          <a href="/dashboard/reports" className="block p-4 border border-gray-200 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors">
            <p className="font-medium text-gray-900">Generate Reports</p>
            <p className="text-sm text-gray-500 mt-1">Export analytics and KPIs</p>
          </a>
        </div>
      </div>
    </div>
  );
}
