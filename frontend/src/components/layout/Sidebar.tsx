'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  ClipboardList,
  FileBarChart,
  Image,
  LayoutDashboard,
  MessageSquareText,
  PenLine,
  Settings,
  Smartphone,
  Users,
  type LucideIcon,
} from 'lucide-react';

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

const NAV_ITEMS: NavItem[] = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/dashboard/service-requests', label: 'Service Requests', icon: ClipboardList },
  { href: '/dashboard/users', label: 'Users', icon: Users },
  { href: '/dashboard/social', label: 'Social Media', icon: Smartphone },
  { href: '/dashboard/collector', label: 'Collector', icon: MessageSquareText },
  { href: '/dashboard/content', label: 'Content', icon: PenLine },
  { href: '/dashboard/media', label: 'Media Library', icon: Image },
  { href: '/dashboard/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/dashboard/reports', label: 'Reports', icon: FileBarChart },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-bold text-gray-900">District360</h2>
      </div>
      <nav className="p-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === '/dashboard' ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

