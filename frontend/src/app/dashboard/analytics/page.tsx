// frontend/src/app/dashboard/analytics/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import StatCard from '@/components/dashboard/analytics/StatCard';
import ReachTrendChart from '@/components/dashboard/analytics/ReachTrendChart';
import EngagementByPlatformChart from '@/components/dashboard/analytics/EngagementByPlatformChart';
import { Users, BarChart2, Heart, MessageSquare, Share2 } from 'lucide-react';

// Data structure interfaces
interface ReachStats {
  total_reach: number;
  total_impressions: number;
}

interface EngagementStats {
  total_engagement: number;
  total_likes: number;
  total_comments: number;
  total_shares: number;
}

interface TrendData {
  date: string;
  total_reach: number;
  facebook_reach: number;
  twitter_reach: number;
  instagram_reach: number;
  youtube_reach: number;
}

interface EngagementPlatformData {
  platform: string;
  likes: number;
  comments: number;
  shares: number;
}

type AnalyticsData = {
  reach: ReachStats;
  engagement: EngagementStats;
  reachTrend: TrendData[];
  engagementByPlatform: EngagementPlatformData[];
};

const PageLoader = () => (
  <div className="flex items-center justify-center h-[60vh]">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500" />
    <p className="ml-4 text-gray-600">Loading Analytics Dashboard...</p>
  </div>
);

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [reachRes, engagementRes, trendRes, platformRes] = await Promise.all([
          api.get('/analytics/reach'),
          api.get('/analytics/engagement'),
          api.get('/analytics/reach/trend'),
          api.get('/analytics/engagement/platform'),
        ]);

        setData({
          reach: reachRes.data.data,
          engagement: engagementRes.data.data,
          reachTrend: trendRes.data.data,
          engagementByPlatform: platformRes.data.data,
        });
      } catch (error) {
        console.error('Failed to fetch analytics data:', error);
        // Optionally, set an error state and show a toast notification
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return <PageLoader />;
  }
  
  const { reach, engagement, reachTrend, engagementByPlatform } = data || {};

  const statCards = [
    { label: 'Total Reach', value: reach?.total_reach ?? 0, icon: Users, color: 'blue' },
    { label: 'Total Engagement', value: engagement?.total_engagement ?? 0, icon: BarChart2, color: 'green' },
    { label: 'Total Likes', value: engagement?.total_likes ?? 0, icon: Heart, color: 'pink' },
    { label: 'Total Comments', value: engagement?.total_comments ?? 0, icon: MessageSquare, color: 'indigo' },
  ];

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Social Media Analytics</h1>
      <p className="text-gray-500 mb-8">An overview of your social media performance.</p>
      
      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map(card => <StatCard key={card.label} {...card} />)}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Reach Trend (Last 30 Days)</h2>
          <ReachTrendChart data={reachTrend || []} loading={loading} />
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Engagement by Platform</h2>
          <EngagementByPlatformChart data={engagementByPlatform || []} loading={loading} />
        </div>
      </div>
    </div>
  );
}
