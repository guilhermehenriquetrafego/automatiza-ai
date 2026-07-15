'use client'

import { useEffect, useState } from 'react'
import { api, type Overview } from '@/lib/api'
import {
  Package, Zap, TrendingUp, MessageSquare, AlertCircle,
  ArrowUpRight, Calendar, RefreshCw
} from 'lucide-react'
import { toast } from 'sonner'

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getOverview().then(setOverview).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleRecalculate = async () => {
    try {
      await api.recalculate()
      toast.success('Motor de Exposição recalculando...')
    } catch {
      toast.error('Erro ao recalcular')
    }
  }

  if (loading) return <div className="animate-pulse text-slate-400">Carregando...</div>

  const stats = [
    { label: 'Produtos Ativos', value: `${overview?.active_products || 0}/${overview?.max_products || 0}`, icon: Package, color: 'text-blue-500' },
    { label: 'Anúncios Disponíveis', value: overview?.total_remaining_ads || 0, icon: Zap, color: 'text-amber-500' },
    { label: 'Anúncios Online', value: overview?.publications.online || 0, icon: TrendingUp, color: 'text-green-500' },
    { label: 'Chats Pendentes', value: overview?.pending_chats || 0, icon: MessageSquare, color: 'text-red-500' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Visão geral do seu sistema de exposição
          </p>
        </div>
        <button onClick={handleRecalculate} className="btn-secondary">
          <RefreshCw className="h-4 w-4" />
          Recalcular Exposição
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {stat.label}
                </p>
                <p className="mt-1 text-3xl font-bold">{stat.value}</p>
              </div>
              <div className={`rounded-xl bg-opacity-10 p-3 ${stat.color}`}>
                <stat.icon className={`h-6 w-6 ${stat.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Publications by status */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold">Anúncios por Status</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatusCard label="Online" value={overview?.publications.online || 0} color="green" />
          <StatusCard label="Agendados" value={overview?.publications.scheduled || 0} color="blue" />
          <StatusCard label="Postando" value={overview?.publications.posting || 0} color="yellow" />
          <StatusCard label="Falhas" value={overview?.publications.failed || 0} color="red" />
        </div>
      </div>

      {/* Plan info */}
      <div className="card flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600">
            <Calendar className="h-6 w-6 text-white" />
          </div>
          <div>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Plano Atual</p>
            <p className="text-lg font-bold capitalize">{overview?.plan || 'starter'}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Contas OLX</p>
          <p className="text-lg font-bold">{overview?.olx_accounts || 0}/{overview?.max_accounts || 0}</p>
        </div>
      </div>
    </div>
  )
}

function StatusCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    green: 'badge-green', blue: 'badge-blue', yellow: 'badge-yellow', red: 'badge-red'
  }
  return (
    <div className="flex flex-col gap-2">
      <span className={`badge ${colorMap[color]} w-fit`}>{label}</span>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}
