'use client';

export default function ReportsError({ reset }: { reset: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6">
      <h2 className="text-lg font-semibold text-red-900">Reports failed to load</h2>
      <button type="button" onClick={reset} className="mt-4 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700">Retry</button>
    </div>
  );
}