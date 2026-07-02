import type { Metadata } from 'next';
import { AuthProvider } from '@/lib/auth';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'District360 — District Administration Platform',
  description: 'Social media management and grievance tracking for district administrations.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
