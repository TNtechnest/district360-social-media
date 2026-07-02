'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type MediaItem = {
  id: string;
  file_name?: string;
  mime_type?: string;
  size_bytes?: number;
  created_at?: string | null;
};

export default function MediaPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/social/media')
      .then(({ data }) => {
        const media = data.data?.items || data.data || [];
        setItems(Array.isArray(media) ? media : []);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Media Library</h1>
          <p className="mt-1 text-sm text-gray-500">Store and manage media assets for posts and campaigns.</p>
        </div>
        <button className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">Upload Media</button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {loading ? (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">Loading media...</div>
        ) : items.length ? (
          items.map((item) => (
            <div key={item.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex h-28 items-center justify-center rounded-md bg-gray-100 text-sm text-gray-500">Preview</div>
              <h2 className="truncate font-semibold text-gray-900">{item.file_name || 'Media item'}</h2>
              <p className="mt-1 text-sm text-gray-500">{item.mime_type || 'Unknown type'}</p>
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">No media items found.</div>
        )}
      </div>
    </div>
  );
}