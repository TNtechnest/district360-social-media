'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Instagram,
  Loader2,
  Plus,
  RefreshCw,
  Unplug,
} from 'lucide-react';
import { api } from '@/lib/api';

type Platform = 'facebook' | 'instagram' | string;

type SocialAccount = {
  id: string;
  platform: Platform;
  label?: string;
  platform_account_id?: string;
  username?: string;
  is_active?: boolean;
  config?: {
    page_id?: string;
    page_name?: string;
    linked_page_id?: string;
    instagram_account_id?: string;
    token_expires_at?: string | null;
  };
  created_at?: string | null;
};

type TokenStatus = {
  is_valid?: boolean;
  expires_at?: string | null;
  days_remaining?: number | null;
};

type BusyAction = {
  accountId?: string;
  action: 'facebook' | 'instagram' | 'refresh' | 'disconnect' | 'load' | null;
};

function pageName(account: SocialAccount) {
  return account.config?.page_name || account.username || account.label || account.platform_account_id || 'Connected account';
}

function platformLabel(platform: Platform) {
  if (platform === 'facebook') return 'Facebook';
  if (platform === 'instagram') return 'Instagram';
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}

function statusText(account: SocialAccount, status?: TokenStatus) {
  if (account.is_active === false) return 'Disconnected';
  if (status?.is_valid === false) return 'Token expired';
  if (typeof status?.days_remaining === 'number') return `${status.days_remaining} days left`;
  return 'Connected';
}

function statusClass(account: SocialAccount, status?: TokenStatus) {
  if (account.is_active === false || status?.is_valid === false) {
    return 'bg-red-50 text-red-700 ring-red-200';
  }
  if (typeof status?.days_remaining === 'number' && status.days_remaining <= 7) {
    return 'bg-amber-50 text-amber-700 ring-amber-200';
  }
  return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
}

function formatDate(value?: string | null) {
  if (!value) return 'Not reported';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not reported';
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

export default function SocialAccountsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [tokenStatus, setTokenStatus] = useState<Record<string, TokenStatus>>({});
  const [busy, setBusy] = useState<BusyAction>({ action: 'load' });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const metaAccounts = useMemo(
    () => accounts.filter((account) => account.platform === 'facebook' || account.platform === 'instagram'),
    [accounts],
  );

  const loadAccounts = useCallback(async () => {
    setBusy({ action: 'load' });
    setError(null);
    try {
      const { data } = await api.get('/social/accounts', { per_page: 100 });
      const items = data.data?.items || data.data || [];
      const nextAccounts = Array.isArray(items) ? items : [];
      setAccounts(nextAccounts);

      const statuses = await Promise.all(
        nextAccounts
          .filter((account: SocialAccount) => account.platform === 'facebook' || account.platform === 'instagram')
          .map(async (account: SocialAccount) => {
            try {
              const response = await api.get(`/social/oauth/accounts/${account.id}/token-status`);
              return [account.id, response.data.data] as const;
            } catch {
              return [account.id, {}] as const;
            }
          }),
      );
      setTokenStatus(Object.fromEntries(statuses));
    } catch {
      setAccounts([]);
      setTokenStatus({});
      setError('Unable to load social accounts.');
    } finally {
      setBusy({ action: null });
    }
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const connect = async (platform: 'facebook' | 'instagram') => {
    setBusy({ action: platform });
    setError(null);
    setNotice(null);
    try {
      const { data } = await api.post('/social/oauth/login', {
        platform_scope: platform,
        connection_label: platform === 'facebook' ? 'Facebook Page' : 'Instagram Account',
      });
      const url = data.data?.authorization_url;
      if (url) {
        window.location.href = url;
        return;
      }
      setError('OAuth login did not return an authorization URL.');
    } catch {
      setError(`Unable to start ${platformLabel(platform)} login.`);
    } finally {
      setBusy({ action: null });
    }
  };

  const refreshToken = async (account: SocialAccount) => {
    setBusy({ accountId: account.id, action: 'refresh' });
    setError(null);
    setNotice(null);
    try {
      const { data } = await api.post(`/social/oauth/accounts/${account.id}/refresh-token`);
      setTokenStatus((current) => ({ ...current, [account.id]: data.data }));
      setNotice(`${pageName(account)} token refreshed.`);
    } catch {
      setError(`Unable to refresh token for ${pageName(account)}.`);
    } finally {
      setBusy({ action: null });
    }
  };

  const disconnect = async (account: SocialAccount) => {
    setBusy({ accountId: account.id, action: 'disconnect' });
    setError(null);
    setNotice(null);
    try {
      await api.delete(`/social/accounts/${account.id}`);
      setAccounts((current) => current.filter((item) => item.id !== account.id));
      setTokenStatus((current) => {
        const next = { ...current };
        delete next[account.id];
        return next;
      });
      setNotice(`${pageName(account)} disconnected.`);
    } catch {
      setError(`Unable to disconnect ${pageName(account)}.`);
    } finally {
      setBusy({ action: null });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Social Accounts</h1>
          <p className="mt-1 text-sm text-gray-500">Connect and maintain district Facebook Pages and Instagram accounts.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => connect('facebook')}
            disabled={busy.action === 'facebook'}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-primary-600 px-4 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy.action === 'facebook' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Connect Facebook
          </button>
          <button
            type="button"
            onClick={() => connect('instagram')}
            disabled={busy.action === 'instagram'}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-gray-900 px-4 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy.action === 'instagram' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Instagram className="h-4 w-4" />}
            Connect Instagram
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="font-semibold text-gray-900">Connected Accounts</h2>
            <p className="mt-1 text-sm text-gray-500">{metaAccounts.length} Meta account connection{metaAccounts.length === 1 ? '' : 's'}</p>
          </div>
          <button
            type="button"
            onClick={loadAccounts}
            disabled={busy.action === 'load'}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-gray-300 px-3 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy.action === 'load' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-6 py-3">Page Name</th>
                <th className="px-6 py-3">Platform</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Page ID</th>
                <th className="px-6 py-3">Token Expiry</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {busy.action === 'load' ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">Loading connected accounts...</td>
                </tr>
              ) : metaAccounts.length ? (
                metaAccounts.map((account) => {
                  const status = tokenStatus[account.id];
                  const isBusy = busy.accountId === account.id;
                  return (
                    <tr key={account.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">{pageName(account)}</div>
                        <div className="mt-1 text-xs text-gray-500">{account.label || account.platform_account_id}</div>
                      </td>
                      <td className="px-6 py-4 text-gray-700">{platformLabel(account.platform)}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${statusClass(account, status)}`}>
                          {statusText(account, status)}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-gray-600">
                        {account.config?.page_id || account.config?.linked_page_id || account.platform_account_id || 'Not reported'}
                      </td>
                      <td className="px-6 py-4 text-gray-600">{formatDate(status?.expires_at || account.config?.token_expires_at)}</td>
                      <td className="px-6 py-4">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => refreshToken(account)}
                            disabled={isBusy}
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-gray-300 px-3 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isBusy && busy.action === 'refresh' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            Refresh Token
                          </button>
                          <button
                            type="button"
                            onClick={() => disconnect(account)}
                            disabled={isBusy}
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-red-200 px-3 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isBusy && busy.action === 'disconnect' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                            Disconnect
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-gray-500">
                    <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-gray-100">
                      <ExternalLink className="h-5 w-5 text-gray-500" />
                    </div>
                    <div className="font-medium text-gray-900">No connected Meta accounts</div>
                    <div className="mt-1 text-sm text-gray-500">Use Connect Facebook or Connect Instagram to begin.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}