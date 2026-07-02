export default function AnalyticsLoading() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-primary-500" />
      <p className="ml-4 text-gray-600">Loading analytics...</p>
    </div>
  );
}