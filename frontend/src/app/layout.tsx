import type { Metadata } from 'next'
import { ThemeProvider } from '@/components/theme-provider'
import { Sidebar } from '@/components/sidebar'
import { Toaster } from 'sonner'
import './globals.css'

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
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-x-hidden p-6 lg:p-8">
              {children}
            </main>
          </div>
          <Toaster position="top-right" richColors />
        </ThemeProvider>
      </body>
    </html>
  )
}
