'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type SocialPost = {
  id: string;
  title?: string;
  content?: string;
  status?: string;
  platform?: string;
};

export default function ContentPage() {
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/social/posts')
      .then(({ data }) => {
        const items = data.data?.items || data.data || [];
        setPosts(Array.isArray(items) ? items : []);
      })
      .catch(() => setPosts([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content</h1>
          <p className="mt-1 text-sm text-gray-500">Draft, review, and publish social media posts.</p>
        </div>
        <button className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">Create Post</button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {loading ? (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">Loading content...</div>
        ) : posts.length ? (
          posts.map((post) => (
            <article key={post.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">{post.title || post.platform || 'Post'}</h2>
                <span className="text-sm text-gray-600">{post.status || 'draft'}</span>
              </div>
              <p className="mt-2 text-sm text-gray-500">{post.content || 'No content preview available.'}</p>
            </article>
          ))
        ) : (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">No content drafts found.</div>
        )}
      </div>
    </div>
  );
}