'use client'

import { AuthProvider } from '@/lib/auth-context'
import Sidebar from '@/components/sidebar'
import { Toaster } from 'sonner'

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 min-w-0">
          <div className="max-w-7xl mx-auto p-6 md:p-8">
            {children}
          </div>
        </main>
      </div>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#16161e',
            border: '1px solid #25252f',
            color: '#f5f5f7',
          },
        }}
      />
    </AuthProvider>
  )
}
