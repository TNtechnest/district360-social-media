export default function SettingsPage() {
  const settings = [
    { label: 'District Profile', value: 'Nagapattinam' },
    { label: 'Region', value: 'Tamil Nadu' },
    { label: 'Authentication', value: 'JWT enabled' },
    { label: 'Notifications', value: 'Email, SMS, WhatsApp' },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">Review district, access, and platform configuration.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">General</h2>
          <div className="mt-4 divide-y divide-gray-200">
            {settings.map((item) => (
              <div key={item.label} className="flex items-center justify-between py-3">
                <span className="text-sm text-gray-500">{item.label}</span>
                <span className="text-sm font-medium text-gray-900">{item.value}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Security</h2>
          <div className="mt-4 space-y-4">
            <label className="flex items-center justify-between rounded-md border border-gray-200 px-4 py-3">
              <span className="text-sm font-medium text-gray-700">Require verified email</span>
              <input type="checkbox" defaultChecked className="h-4 w-4 rounded border-gray-300 text-primary-600" />
            </label>
            <label className="flex items-center justify-between rounded-md border border-gray-200 px-4 py-3">
              <span className="text-sm font-medium text-gray-700">Require verified phone</span>
              <input type="checkbox" defaultChecked className="h-4 w-4 rounded border-gray-300 text-primary-600" />
            </label>
          </div>
        </section>
      </div>
    </div>
  );
}