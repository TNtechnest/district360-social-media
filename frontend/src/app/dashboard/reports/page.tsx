'use client';

import { useEffect, useState } from 'react';
import { Download, FileSpreadsheet, FileText } from 'lucide-react';
import { api } from '@/lib/api';

type Report = {
  id: string;
  report_type?: string;
  title?: string;
  status?: string;
  created_at?: string | null;
};

type ExportItem = {
  name: string;
  filename: string;
  endpoint: string;
  type: 'excel' | 'pdf';
};

const EXPORTS: ExportItem[] = [
  {
    name: 'Comments Report',
    filename: 'comments_report.xlsx',
    endpoint: '/reports/export/comments/excel',
    type: 'excel',
  },
  {
    name: 'Complaints Report',
    filename: 'complaints_report.xlsx',
    endpoint: '/reports/export/complaints/excel',
    type: 'excel',
  },
  {
    name: 'Monthly Social Report',
    filename: 'monthly_social_report.pdf',
    endpoint: '/reports/export/monthly-social/pdf',
    type: 'pdf',
  },
];

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/reports')
      .then(({ data }) => {
        const items = data.data?.items || data.data || [];
        setReports(Array.isArray(items) ? items : []);
      })
      .catch(() => setReports([]))
      .finally(() => setLoading(false));
  }, []);

  const downloadReport = async (item: ExportItem) => {
    try {
      setDownloading(item.filename);
      setError('');
      const response = await api.getBlob(item.endpoint);
      saveBlob(response.data, item.filename);
    } catch {
      setError(`${item.name} could not be downloaded.`);
    } finally {
      setDownloading('');
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
          <p className="mt-1 text-sm text-gray-500">Generate and download operational reports.</p>
        </div>
        <button className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">Generate Report</button>
      </div>

      {error ? (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {EXPORTS.map((item) => {
          const Icon = item.type === 'excel' ? FileSpreadsheet : FileText;
          const isDownloading = downloading === item.filename;
          return (
            <div key={item.filename} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-50 text-primary-600">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-gray-900">{item.name}</h2>
                    <p className="mt-1 text-sm text-gray-500">{item.filename}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => downloadReport(item)}
                  disabled={Boolean(downloading)}
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                  title={`Download ${item.filename}`}
                >
                  <Download className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              {isDownloading ? <p className="mt-3 text-sm text-primary-700">Preparing download...</p> : null}
            </div>
          );
        })}
      </div>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Recent Reports</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {loading ? (
            <div className="px-6 py-6 text-sm text-gray-500">Loading reports...</div>
          ) : reports.length ? (
            reports.map((report) => (
              <div key={report.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{report.title || report.report_type || 'Report'}</p>
                  <p className="text-sm text-gray-500">{report.created_at || '-'}</p>
                </div>
                <span className="text-sm text-gray-600">{report.status || 'ready'}</span>
              </div>
            ))
          ) : (
            <div className="px-6 py-6 text-sm text-gray-500">No reports generated yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
