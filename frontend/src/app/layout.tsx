import type { Metadata } from 'next'
import { ThemeProvider } from '@/components/theme-provider'
import { Sidebar } from '@/components/sidebar'
import { Toaster } from 'sonner'
import './globals.css'
import { AuthProvider } from '@/lib/auth-context'

export const metadata: Metadata = {
  title: 'AUTOMATIZA AI',
  description: 'Sistema de Gestão de Exposição de Anúncios OLX',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const theme = localStorage.getItem('theme') || 'dark';
                if (theme === 'dark') document.documentElement.classList.add('dark');
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>
            <SidebarWrapper />
            <main className="flex-1 overflow-x-hidden p-6 lg:p-8 lg:ml-64">
              {children}
            </main>
          </AuthProvider>
          <Toaster position="top-right" richColors />
        </ThemeProvider>
      </body>
    </html>
  )
}

// Wrapper to include sidebar (it returns null on login page)
function SidebarWrapper() {
  return <Sidebar />
}
