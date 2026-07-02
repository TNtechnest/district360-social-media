'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

type SocialAccount = {
  id: string;
  platform: string;
  account_name?: string;
  username?: string;
  status?: string;
};

export default function SocialPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/social/accounts')
      .then(({ data }) => {
        const items = data.data?.items || data.data || [];
        setAccounts(Array.isArray(items) ? items : []);
      })
      .catch(() => setAccounts([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Social Media</h1>
          <p className="mt-1 text-sm text-gray-500">Manage connected social accounts and publishing channels.</p>
        </div>
        <Link href="/dashboard/social/accounts" className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">Manage Accounts</Link>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Connected Accounts</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {loading ? (
            <div className="px-6 py-6 text-sm text-gray-500">Loading social accounts...</div>
          ) : accounts.length ? (
            accounts.map((account) => (
              <div key={account.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{account.account_name || account.username || account.platform}</p>
                  <p className="text-sm text-gray-500">{account.platform}</p>
                </div>
                <span className="text-sm text-gray-600">{account.status || 'active'}</span>
              </div>
            ))
          ) : (
            <div className="px-6 py-6 text-sm text-gray-500">No social accounts connected.</div>
          )}
        </div>
      </div>
    </div>
  );
}