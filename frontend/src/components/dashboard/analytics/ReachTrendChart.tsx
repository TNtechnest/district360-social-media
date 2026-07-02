// frontend/src/components/dashboard/analytics/ReachTrendChart.tsx
'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useMemo } from 'react';

interface TrendData {
  date: string;
  total_reach: number;
  facebook_reach: number;
  twitter_reach: number;
  instagram_reach: number;
  youtube_reach: number;
}

interface ReachTrendChartProps {
  data: TrendData[];
  loading: boolean;
}

const ChartLoader = () => (
  <div className="flex items-center justify-center h-full">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
  </div>
);

const ReachTrendChart = ({ data, loading }: ReachTrendChartProps) => {
  const formattedData = useMemo(() => data.map(d => ({
    ...d,
    date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  })), [data]);

  if (loading) {
    return <ChartLoader />;
  }
  
  if (!data || data.length === 0) {
    return <div className="flex items-center justify-center h-full"><p className="text-gray-500">No data available to display.</p></div>;
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={formattedData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{
            background: 'white',
            border: '1px solid #e5e7eb',
            borderRadius: '0.5rem',
          }}
        />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '14px' }} />
        <Line type="monotone" dataKey="total_reach" name="Total Reach" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        <Line type="monotone" dataKey="facebook_reach" name="Facebook" stroke="#1877F2" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="instagram_reach" name="Instagram" stroke="#E4405F" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="twitter_reach" name="X (Twitter)" stroke="#1DA1F2" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="youtube_reach" name="YouTube" stroke="#FF0000" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default ReachTrendChart;
