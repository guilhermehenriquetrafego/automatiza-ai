'use client'

import { useAuth } from '@/lib/auth-context'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import { LayoutDashboard, Package, Calendar, Radio, MessageSquare, Settings, LogOut, Menu, X, Zap } from 'lucide-react'
import { toast } from 'sonner'

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
  const [showConfirmLogout, setShowConfirmLogout] = useState(false)

  // Close drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [mobileOpen])

  const handleLogoutClick = () => {
    setShowConfirmLogout(true)
  }

  const confirmLogout = async () => {
    try {
      await logout()
      toast.success('Desconectado com sucesso!')
    } catch {
      toast.error('Erro ao sair.')
    } finally {
      setShowConfirmLogout(false)
    }
  }

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div className="relative">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-indigo-700 shadow-lg shadow-indigo-500/20 relative group">
            <Zap className="h-5 w-5 text-white relative z-10" fill="white" />
            <span className="absolute inset-0 bg-indigo-500 blur-sm rounded-xl opacity-30 animate-pulse-subtle" />
          </div>
        </div>
        <div>
          <h1 className="text-sm font-extrabold tracking-tight text-white">AUTOMATIZA<span className="text-indigo-400"> AI</span></h1>
          <p className="text-[9px] text-indigo-400/80 font-bold uppercase tracking-wider">Gestão de Exposição</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-1.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || (item.href !== '/' && pathname?.startsWith(item.href))
          const Icon = item.icon
          return (
            <a
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`group relative flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-300 ${
                active
                  ? 'bg-gradient-to-r from-indigo-600/15 to-indigo-600/5 text-indigo-300 border-l-[3px] border-indigo-500 rounded-l-none'
                  : 'text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200'
              }`}
            >
              {/* Animated indicator for active item */}
              {active && (
                <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-indigo-500 shadow-glow-indigo animate-pulse" />
              )}
              
              <Icon className={`h-4.5 w-4.5 shrink-0 transition-transform group-hover:scale-105 duration-300 ${active ? 'text-indigo-400' : 'text-zinc-500 group-hover:text-zinc-300'}`} strokeWidth={active ? 2.5 : 2} />
              <span className={active ? 'font-semibold' : ''}>{item.label}</span>
              {item.badge === 'live' && (
                <span className="ml-auto flex items-center gap-1.5 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <span className="live-dot" />
                  <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider">Live</span>
                </span>
              )}

              {/* Tooltip on collapse (Can be fully expanded via CSS if wanted, but adds standard native title as fallback) */}
              <span className="sr-only">{item.label}</span>
            </a>
          )
        })}
      </nav>

      {/* User Info / Logout with Modal */}
      <div className="px-3 py-4 border-t border-zinc-800/50 safe-bottom">
        {showConfirmLogout ? (
          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-3 animate-scale-in">
            <p className="text-[11px] text-zinc-300 font-semibold mb-2.5 text-center">Deseja realmente sair?</p>
            <div className="flex gap-2">
              <button
                onClick={confirmLogout}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white rounded-lg py-1.5 text-xs font-semibold transition"
              >
                Sair
              </button>
              <button
                onClick={() => setShowConfirmLogout(false)}
                className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg py-1.5 text-xs font-semibold transition"
              >
                Voltar
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-xl px-3 py-2 bg-zinc-950/40 border border-zinc-900/50 hover:border-zinc-800/50 transition duration-300">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/30 to-indigo-600/30 text-sm font-bold text-indigo-300 border border-indigo-500/20 shrink-0 shadow-inner">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-zinc-100 truncate">{user?.full_name || 'Usuário'}</p>
              <p className="text-[10px] text-zinc-500 truncate">{user?.email}</p>
            </div>
            <button 
              onClick={handleLogoutClick} 
              className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition rounded-lg p-2 -mr-1" 
              title="Sair do sistema"
            >
              <LogOut className="h-4.5 w-4.5" />
            </button>
          </div>
        )}
      </div>
    </>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 min-h-screen border-r border-zinc-800/60 bg-[#0d0d12] sticky top-0 shadow-lg">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-zinc-800/60 bg-[#0d0d12]/95 backdrop-blur-md sticky top-0 z-40 safe-top">
        <a href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 relative">
            <Zap className="h-4 w-4 text-white" fill="white" />
            <span className="absolute inset-0 bg-indigo-500 blur-xs rounded-lg opacity-20" />
          </div>
          <span className="text-sm font-extrabold tracking-tight">AUTOMATIZA<span className="text-indigo-400"> AI</span></span>
        </a>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-zinc-400 hover:text-white p-2 -mr-2 touch-manipulation"
          aria-label={mobileOpen ? 'Fechar menu' : 'Abrir menu'}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 overlay-enter" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-md" />
          <div
            className="relative w-[280px] max-w-[85vw] h-full bg-[#0d0d12] border-r border-zinc-800/60 flex flex-col drawer-enter safe-top shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Close button inside drawer */}
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute top-3 right-3 text-zinc-500 hover:text-white p-1.5 z-10 hover:bg-zinc-800/50 rounded-lg transition"
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent />
          </div>
        </div>
      )}
    </>
  )
}
