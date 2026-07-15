'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTheme } from '@/components/theme-provider'
import { useAuth } from '@/lib/auth-context'
import {
  LayoutDashboard, Package, Calendar, MessageSquare, Settings,
  Sun, Moon, Zap, ChevronRight, LogOut
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/produtos', label: 'Catálogo', icon: Package },
  { href: '/exposicao', label: 'Exposição', icon: Calendar },
  { href: '/chat', label: 'Chat', icon: MessageSquare },
  { href: '/config', label: 'Config', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { theme, toggle } = useTheme()
  const { user, logout } = useAuth()

  // Don't render sidebar on login page
  if (pathname === '/login') return null

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r"
      style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-secondary)' }}>
      
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600">
          <Zap className="h-6 w-6 text-white" fill="white" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            AUTOMATIZA AI
          </p>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Gestão de Exposição
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                active ? 'bg-brand-600 text-white' : 'hover:bg-brand-50 dark:hover:bg-slate-800'
              )}
              style={!active ? { color: 'var(--text-secondary)' } : {}}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
              {active && <ChevronRight className="ml-auto h-4 w-4" />}
            </Link>
          )
        })}
      </nav>

      {/* Theme toggle + user info */}
      <div className="border-t px-3 py-4 space-y-2" style={{ borderColor: 'var(--border-color)' }}>
        {/* User info */}
        {user && (
          <div className="flex items-center gap-3 rounded-lg px-3 py-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-white text-sm font-bold">
              {user.full_name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {user.full_name}
              </p>
              <p className="truncate text-xs capitalize" style={{ color: 'var(--text-secondary)' }}>
                Plano {user.plan_tier}
              </p>
            </div>
          </div>
        )}
        
        <button
          onClick={toggle}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium hover:bg-brand-50 dark:hover:bg-slate-800 transition-colors"
          style={{ color: 'var(--text-secondary)' }}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          {theme === 'dark' ? 'Modo Claro' : 'Modo Escuro'}
        </button>

        {user && (
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-slate-800 transition-colors"
          >
            <LogOut className="h-5 w-5" />
            Sair
          </button>
        )}
      </div>
    </aside>
  )
}
