'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, MessageSquare, Smile, ThumbsDown } from 'lucide-react';
import { api } from '@/lib/api';
import StatCard from '@/components/dashboard/analytics/StatCard';

type DailyTrendPoint = {
  date: string;
  comments: number;
};

type SentimentTrendPoint = {
  date: string;
  positive: number;
  negative: number;
  neutral: number;
  mixed: number;
};

type DepartmentTrendPoint = {
  department: string;
  complaints: number;
};

type CollectorDashboardData = {
  widgets: {
    total_comments: number;
    positive: number;
    negative: number;
    complaints: number;
  };
  charts: {
    daily_trend: DailyTrendPoint[];
    sentiment_trend: SentimentTrendPoint[];
    department_trend: DepartmentTrendPoint[];
  };
};

const emptyData: CollectorDashboardData = {
  widgets: {
    total_comments: 0,
    positive: 0,
    negative: 0,
    complaints: 0,
  },
  charts: {
    daily_trend: [],
    sentiment_trend: [],
    department_trend: [],
  },
};

const formatDate = (value: string) => new Date(value).toLocaleDateString('en-US', {
  month: 'short',
  day: 'numeric',
});

const chartText = { fill: '#6b7280', fontSize: 12 };

function ChartEmptyState() {
  return (
    <div className="flex h-80 items-center justify-center text-sm text-gray-500">
      No data available.
    </div>
  );
}

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">{title}</h2>
      {children}
    </section>
  );
}

export default function CollectorDashboardPage() {
  const [data, setData] = useState<CollectorDashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/social/collector/dashboard', { days: 14 })
      .then(({ data: response }) => {
        setData(response.data || emptyData);
        setError('');
      })
      .catch(() => {
        setData(emptyData);
        setError('Collector dashboard data could not be loaded.');
      })
      .finally(() => setLoading(false));
  }, []);

  const dailyTrend = useMemo(() => data.charts.daily_trend.map((point) => ({
    ...point,
    label: formatDate(point.date),
  })), [data.charts.daily_trend]);

  const sentimentTrend = useMemo(() => data.charts.sentiment_trend.map((point) => ({
    ...point,
    label: formatDate(point.date),
  })), [data.charts.sentiment_trend]);

  const departmentTrend = data.charts.department_trend;

  const statCards = [
    { label: 'Total Comments', value: data.widgets.total_comments, icon: MessageSquare, color: 'blue' },
    { label: 'Positive', value: data.widgets.positive, icon: Smile, color: 'green' },
    { label: 'Negative', value: data.widgets.negative, icon: ThumbsDown, color: 'red' },
    { label: 'Complaints', value: data.widgets.complaints, icon: AlertTriangle, color: 'amber' },
  ];

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary-500" />
        <p className="ml-4 text-gray-600">Loading Collector Dashboard...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Collector Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Monitor citizen comments, sentiment, complaints, and department routing.</p>
      </div>

      {error ? (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => <StatCard key={card.label} {...card} />)}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-8 xl:grid-cols-2">
        <ChartPanel title="Daily Trend">
          {dailyTrend.length ? (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={dailyTrend} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={chartText} axisLine={false} tickLine={false} />
                <YAxis tick={chartText} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '0.5rem' }} />
                <Line type="monotone" dataKey="comments" name="Comments" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <ChartEmptyState />}
        </ChartPanel>

        <ChartPanel title="Sentiment Trend">
          {sentimentTrend.length ? (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={sentimentTrend} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={chartText} axisLine={false} tickLine={false} />
                <YAxis tick={chartText} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '0.5rem' }} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '14px' }} />
                <Line type="monotone" dataKey="positive" name="Positive" stroke="#16a34a" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="negative" name="Negative" stroke="#dc2626" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="neutral" name="Neutral" stroke="#64748b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="mixed" name="Mixed" stroke="#9333ea" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <ChartEmptyState />}
        </ChartPanel>

        <div className="xl:col-span-2">
          <ChartPanel title="Department Trend">
            {departmentTrend.length ? (
              <ResponsiveContainer width="100%" height={340}>
                <BarChart data={departmentTrend} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="department" tick={chartText} axisLine={false} tickLine={false} interval={0} />
                  <YAxis tick={chartText} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '0.5rem' }} />
                  <Bar dataKey="complaints" name="Complaints" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <ChartEmptyState />}
          </ChartPanel>
        </div>
      </div>
    </div>
  );
}
