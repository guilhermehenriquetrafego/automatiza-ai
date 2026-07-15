'use client'

import { useEffect, useState } from 'react'
import { api, type Overview } from '@/lib/api'
import { Package, Eye, MessageSquare, Radio, ArrowUpRight, Activity, Zap } from 'lucide-react'

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getOverview()
      .then(setOverview)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <DashboardSkeleton />

  const stats = [
    { label: 'Produtos Ativos', value: `${overview?.active_products ?? 0}/${overview?.max_products ?? 10}`, icon: Package, color: 'indigo', sub: 'catálogo' },
    { label: 'Contas OLX', value: `${overview?.olx_accounts ?? 0}/${overview?.max_accounts ?? 1}`, icon: Radio, color: 'emerald', sub: 'conectadas' },
    { label: 'Anúncios Online', value: overview?.publications?.online ?? 0, icon: Eye, color: 'blue', sub: 'publicados' },
    { label: 'Chats Pendentes', value: overview?.pending_chats ?? 0, icon: MessageSquare, color: 'amber', sub: 'aguardando' },
  ]

  const colorMap: Record<string, string> = {
    indigo: 'from-indigo-500/15 to-indigo-600/5 text-indigo-400 border-indigo-500/20',
    emerald: 'from-emerald-500/15 to-emerald-600/5 text-emerald-400 border-emerald-500/20',
    blue: 'from-blue-500/15 to-blue-600/5 text-blue-400 border-blue-500/20',
    amber: 'from-amber-500/15 to-amber-600/5 text-amber-400 border-amber-500/20',
  }

  const usedPct = overview
    ? Math.min(((overview.active_products * 8) / Math.max(overview.total_remaining_ads || 1, 1)) * 100, 100)
    : 0
  const usedPctRounded = Math.round(usedPct)

  return (
    <div className="space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-1">Visão geral do seu sistema de exposição</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className="live-dot" />
          <span className="text-xs font-medium text-emerald-400">Sistema ativo</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="premium-card p-5 group">
              <div className="flex items-start justify-between mb-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${colorMap[stat.color]} border`}>
                  <Icon className="h-5 w-5" strokeWidth={2.2} />
                </div>
                <ArrowUpRight className="h-4 w-4 text-zinc-700 group-hover:text-zinc-500 transition" />
              </div>
              <p className="text-2xl font-bold text-white">{stat.value}</p>
              <p className="text-xs text-zinc-500 mt-1">{stat.label}</p>
              <p className="text-[10px] text-zinc-700 mt-0.5">{stat.sub}</p>
            </div>
          )
        })}
      </div>

      <div className="premium-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20">
            <Zap className="h-5 w-5 text-indigo-400" fill="currentColor" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Motor de Exposição</h2>
            <p className="text-xs text-zinc-500">Status do motor inteligente de publicação</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">Anúncios restantes</p>
            <p className="text-xl font-bold text-white">{overview?.total_remaining_ads ?? 0}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">Agendados</p>
            <p className="text-xl font-bold text-amber-400">{overview?.publications?.scheduled ?? 0}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">Postando agora</p>
            <p className="text-xl font-bold text-blue-400">{overview?.publications?.posting ?? 0}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-zinc-500">Falhas</p>
            <p className="text-xl font-bold text-red-400">{overview?.publications?.failed ?? 0}</p>
          </div>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-zinc-500">Limite mensal utilizado</span>
            <span className="text-zinc-400 font-medium">{usedPctRounded}%</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-800/60 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400" style={{ width: `${usedPct}%` }} />
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <a href="/produtos" className="premium-card p-5 group hover:border-indigo-500/30 transition">
          <Package className="h-5 w-5 text-indigo-400 mb-3" />
          <p className="text-sm font-medium text-white">Gerenciar catálogo</p>
          <p className="text-xs text-zinc-500 mt-1">Adicione e organize seus produtos</p>
        </a>
        <a href="/cdp-live" className="premium-card p-5 group hover:border-indigo-500/30 transition">
          <Activity className="h-5 w-5 text-emerald-400 mb-3" />
          <p className="text-sm font-medium text-white">Monitorar CDP</p>
          <p className="text-xs text-zinc-500 mt-1">Veja a automação rodando ao vivo</p>
        </a>
        <a href="/config" className="premium-card p-5 group hover:border-indigo-500/30 transition">
          <Radio className="h-5 w-5 text-amber-400 mb-3" />
          <p className="text-sm font-medium text-white">Conectar OLX</p>
          <p className="text-xs text-zinc-500 mt-1">Adicione suas contas OLX</p>
        </a>
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="skeleton h-8 w-48" />
          <div className="skeleton h-4 w-64 mt-2" />
        </div>
        <div className="skeleton h-8 w-32 rounded-full" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-28 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton h-48 rounded-2xl" />
      <div className="grid md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton h-24 rounded-2xl" />
        ))}
      </div>
    </div>
  )
}
