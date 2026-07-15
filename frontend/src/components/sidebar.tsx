'use client'

import { useAuth } from '@/lib/auth-context'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { LayoutDashboard, Package, Calendar, Radio, MessageSquare, Settings, LogOut, Menu, X, Zap } from 'lucide-react'

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/produtos', label: 'Catálogo', icon: Package },
  { href: '/exposicao', label: 'Exposição', icon: Calendar },
  { href: '/cdp-live', label: 'CDP Live', icon: Radio, badge: 'live' },
  { href: '/chat', label: 'Chat OLX', icon: MessageSquare },
  { href: '/config', label: 'Config', icon: Settings },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div className="relative">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 shadow-lg shadow-indigo-500/30">
            <Zap className="h-5 w-5 text-white" fill="white" />
          </div>
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-white">AUTOMATIZA<span className="text-indigo-400"> AI</span></h1>
          <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Gestão de Exposição</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || (item.href !== '/' && pathname?.startsWith(item.href))
          const Icon = item.icon
          return (
            <a
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                active
                  ? 'bg-indigo-500/10 text-indigo-400'
                  : 'text-zinc-500 hover:bg-zinc-800/50 hover:text-zinc-300'
              }`}
            >
              <Icon className={`h-4.5 w-4.5 ${active ? 'text-indigo-400' : 'text-zinc-600 group-hover:text-zinc-400'}`} strokeWidth={active ? 2.5 : 2} />
              <span>{item.label}</span>
              {item.badge === 'live' && (
                <span className="ml-auto flex items-center gap-1.5">
                  <span className="live-dot" />
                </span>
              )}
            </a>
          )
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-zinc-800/60">
        <div className="flex items-center gap-3 rounded-xl px-3 py-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/20 to-indigo-600/20 text-sm font-semibold text-indigo-300 border border-indigo-500/20">
            {user?.full_name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white truncate">{user?.full_name || 'Usuário'}</p>
            <p className="text-[10px] text-zinc-600 truncate">{user?.email}</p>
          </div>
          <button onClick={logout} className="text-zinc-600 hover:text-red-400 transition" title="Sair">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </>
  )

  return (
    <>
      {/* Desktop */}
      <aside className="hidden md:flex flex-col w-64 min-h-screen border-r border-zinc-800/60 bg-[#0d0d12] sticky top-0">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-4 border-b border-zinc-800/60 bg-[#0d0d12] sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600">
            <Zap className="h-4 w-4 text-white" fill="white" />
          </div>
          <span className="text-sm font-bold">AUTOMATIZA<span className="text-indigo-400"> AI</span></span>
        </div>
        <button onClick={() => setMobileOpen(!mobileOpen)} className="text-zinc-400">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)}>
          <div className="w-64 h-full bg-[#0d0d12] border-r border-zinc-800/60 flex flex-col" onClick={e => e.stopPropagation()}>
            <SidebarContent />
          </div>
        </div>
      )}
    </>
  )
}
