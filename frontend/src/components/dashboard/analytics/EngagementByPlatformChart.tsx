// frontend/src/components/dashboard/analytics/EngagementByPlatformChart.tsx
'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface EngagementData {
  platform: string;
  likes: number;
  comments: number;
  shares: number;
}

interface EngagementByPlatformChartProps {
  data: EngagementData[];
  loading: boolean;
}

const ChartLoader = () => (
  <div className="flex items-center justify-center h-full">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
  </div>
);

const EngagementByPlatformChart = ({ data, loading }: EngagementByPlatformChartProps) => {
  if (loading) {
    return <ChartLoader />;
  }

  if (!data || data.length === 0) {
    return <div className="flex items-center justify-center h-full"><p className="text-gray-500">No data available to display.</p></div>;
  }

  const platformColors: { [key: string]: string } = {
    facebook: '#1877F2',
    instagram: '#E4405F',
    twitter: '#1DA1F2',
    youtube: '#FF0000',
  };

  const formattedData = data.map(d => ({
    ...d,
    platform: d.platform.charAt(0).toUpperCase() + d.platform.slice(1),
    fill: platformColors[d.platform.toLowerCase()] || '#8884d8',
  }));

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={formattedData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis 
          type="category" 
          dataKey="platform" 
          width={80} 
          tick={{ fill: '#6b7280', fontSize: 12 }} 
          axisLine={false} 
          tickLine={false} 
        />
        <Tooltip
          cursor={{ fill: '#f3f4f6' }}
          contentStyle={{
            background: 'white',
            border: '1px solid #e5e7eb',
            borderRadius: '0.5rem',
          }}
        />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '14px' }} />
        <Bar dataKey="likes" stackId="a" fill="#3b82f6" name="Likes" />
        <Bar dataKey="comments" stackId="a" fill="#22c55e" name="Comments" />
        <Bar dataKey="shares" stackId="a" fill="#f97316" name="Shares" />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default EngagementByPlatformChart;
