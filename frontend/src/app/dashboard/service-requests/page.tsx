'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type ServiceRequest = {
  id: string;
  title: string;
  status: string;
  priority: string;
  created_at?: string | null;
};

export default function ServiceRequestsPage() {
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/service-requests')
      .then(({ data }) => {
        const items = data.data?.items || data.data || [];
        setRequests(Array.isArray(items) ? items : []);
      })
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Service Requests</h1>
          <p className="mt-1 text-sm text-gray-500">Track citizen requests and department assignments.</p>
        </div>
        <button className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
          New Request
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Title</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Priority</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {loading ? (
              <tr><td className="px-6 py-6 text-sm text-gray-500" colSpan={4}>Loading service requests...</td></tr>
            ) : requests.length ? (
              requests.map((request) => (
                <tr key={request.id}>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{request.title}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{request.status}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{request.priority}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{request.created_at || '-'}</td>
                </tr>
              ))
            ) : (
              <tr><td className="px-6 py-6 text-sm text-gray-500" colSpan={4}>No service requests found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}