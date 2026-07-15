'use client'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { AuthProvider } from '@/lib/auth-context'
import Sidebar from '@/components/sidebar'
import { Toaster } from 'sonner'
import { Loader2 } from 'lucide-react'

export default function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isAuthPage = pathname === '/login'
  const [mounted, setMounted] = useState(false)
  const [hasToken, setHasToken] = useState(false)

  useEffect(() => {
    setMounted(true)
    if (typeof window !== 'undefined') {
      setHasToken(!!localStorage.getItem('token'))
    }
  }, [pathname])

  // While checking hydration/auth state, render a centered loading spinner if not on the login page
  if (!isAuthPage) {
    if (!mounted || !hasToken) {
      return (
        <AuthProvider>
          <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f]">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
          </div>
          <Toaster position="top-right" toastOptions={{ style: { background: '#16161e', border: '1px solid #25252f', color: '#f5f5f7' } }} />
        </AuthProvider>
      )
    }
  }

  return (
    <AuthProvider>
      {isAuthPage ? (
        <div className="min-h-screen bg-[#0a0a0f]">{children}</div>
      ) : (
        <div className="flex min-h-screen bg-[#0a0a0f]">
          <Sidebar />
          <main className="flex-1 min-w-0">
            <div className="max-w-7xl mx-auto p-4 sm:p-6 md:p-8">{children}</div>
          </main>
        </div>
      )}
      <Toaster position="top-right" toastOptions={{ style: { background: '#16161e', border: '1px solid #25252f', color: '#f5f5f7' } }} />
    </AuthProvider>
  )
}
