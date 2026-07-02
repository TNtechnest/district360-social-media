// frontend/src/components/dashboard/analytics/StatCard.tsx
'use client';

import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
}

const StatCard = ({ label, value, icon: Icon, color }: StatCardProps) => {
  const iconColor = `text-${color}-500`;
  const bgColor = `bg-${color}-50`;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex items-center gap-6">
      <div className={`w-12 h-12 flex items-center justify-center rounded-full ${bgColor}`}>
        <Icon className={`w-6 h-6 ${iconColor}`} />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );
};

export default StatCard;
