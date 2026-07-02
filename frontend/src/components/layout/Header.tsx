'use client';

import { useAuth } from '@/lib/auth';

export default function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          Welcome, <span className="font-medium text-gray-900">{user?.full_name || 'User'}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-500">{user?.email}</span>
          <button
            onClick={logout}
            className="text-sm text-gray-600 hover:text-red-600 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
