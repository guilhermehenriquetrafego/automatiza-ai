'use client'

import { useEffect, useState, useRef } from 'react'
import { api } from '@/lib/api'
import { Radio, Activity, Clock, CheckCircle2, AlertCircle, Loader2, Zap, Calendar, Cpu, Wifi, Monitor } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://automatiza-ai-api.onrender.com/api/v1'

interface CdpStep {
  timestamp: string
  action: string
  status: 'pending' | 'running' | 'success' | 'error'
  message: string
}

interface CdpSession {
  id: string
  account_email: string
  status: string
  current_action: string
  started_at: string
  last_updated: string
  steps: CdpStep[]
  olx_ad_url: string | null
}

interface CdpActivity {
  timestamp: string
  session_id: string
  account_email: string
  action: string
  status: string
  message: string
}

interface ScheduledAction {
  id: string
  scheduled_time: string
  account_email: string
  product_title: string
  action_type: string
  variation_title: string | null
}

export default function CdpLivePage() {
  const [sessions, setSessions] = useState<CdpSession[]>([])
  const [activity, setActivity] = useState<CdpActivity[]>([])
  const [scheduled, setScheduled] = useState<ScheduledAction[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'live' | 'scheduled' | 'history'>('live')

  useEffect(() => {
    const fetchData = async () => {
      const token = localStorage.getItem('token')
      if (!token) return

      try {
        const headers = { Authorization: `Bearer ${token}` }

        // Fetch sessions
        const sessRes = await fetch(`${API_URL}/cdp-live/sessions`, { headers })
        const sessData = sessRes.ok ? await sessRes.json() : []

        // Fetch activity
        const actRes = await fetch(`${API_URL}/cdp-live/activity`, { headers })
        const actData = actRes.ok ? await actRes.json() : []

        // Fetch schedule
        const schRes = await fetch(`${API_URL}/cdp-live/schedule`, { headers })
        const schData = schRes.ok ? await schRes.json() : []

        setSessions(sessData)
        setActivity(actData)
        setScheduled(schData)
      } catch {}
      finally { setLoading(false) }
    }

    fetchData()
    const interval = setInterval(fetchData, 3000) // Live update every 3s
    return () => clearInterval(interval)
  }, [])

  const statusColors: Record<string, string> = {
    idle: 'idle',
    connecting: 'pending',
    logging_in: 'pending',
    posting: 'pending',
    syncing: 'pending',
    success: 'active',
    error: 'error',
  }

  if (loading) return <CdpSkeleton />

  return (
    <div className="space-y-6 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">CDP Live</h1>
          <p className="text-sm text-zinc-500 mt-1">Monitoramento em tempo real da automação</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className="live-dot" />
          <span className="text-xs font-medium text-emerald-400">Ao vivo</span>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="premium-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="h-4 w-4 text-indigo-400" />
            <span className="text-xs text-zinc-500">Sessões ativas</span>
          </div>
          <p className="text-xl font-bold text-white">{sessions.filter(s => !['idle', 'success', 'error'].includes(s.status)).length}</p>
        </div>
        <div className="premium-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-zinc-500">Eventos hoje</span>
          </div>
          <p className="text-xl font-bold text-white">{activity.length}</p>
        </div>
        <div className="premium-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="h-4 w-4 text-amber-400" />
            <span className="text-xs text-zinc-500">Agendados</span>
          </div>
          <p className="text-xl font-bold text-white">{scheduled.length}</p>
        </div>
        <div className="premium-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Wifi className="h-4 w-4 text-blue-400" />
            <span className="text-xs text-zinc-500">CDP Status</span>
          </div>
          <p className="text-sm font-bold text-emerald-400">Conectado</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-zinc-900/60 p-1 border border-zinc-800/50 w-fit">
        {(['live', 'scheduled', 'history'] as const).map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === t ? 'bg-indigo-600 text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {t === 'live' ? 'Ao Vivo' : t === 'scheduled' ? 'Agendados' : 'Histórico'}
          </button>
        ))}
      </div>

      {/* Live sessions */}
      {activeTab === 'live' && (
        <div className="space-y-4">
          {sessions.length === 0 ? (
            <div className="premium-card p-12 text-center">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
                <Monitor className="h-8 w-8 text-zinc-600" />
              </div>
              <h3 className="text-base font-semibold text-white">Nenhuma sessão CDP ativa</h3>
              <p className="text-sm text-zinc-500 mt-1 max-w-sm mx-auto">
                Quando o sistema iniciar uma automação (login, postagem, sync de limites), você verá tudo acontecer aqui em tempo real.
              </p>
            </div>
          ) : (
            sessions.map(sess => (
              <div key={sess.id} className="premium-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${
                      sess.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20' :
                      sess.status === 'error' ? 'bg-red-500/10 border-red-500/20' :
                      'bg-indigo-500/10 border-indigo-500/20'
                    }`}>
                      {sess.status === 'success' ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> :
                       sess.status === 'error' ? <AlertCircle className="h-5 w-5 text-red-400" /> :
                       <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{sess.account_email}</p>
                      <p className="text-xs text-zinc-500">{sess.current_action}</p>
                    </div>
                  </div>
                  <span className={`status-badge ${statusColors[sess.status] || 'idle'}`}>
                    {sess.status.replace('_', ' ')}
                  </span>
                </div>

                {/* Steps timeline */}
                <div className="space-y-2 pl-2">
                  {sess.steps?.map((step, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <div className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${
                        step.status === 'success' ? 'bg-emerald-500' :
                        step.status === 'error' ? 'bg-red-500' :
                        step.status === 'running' ? 'bg-indigo-500 animate-pulse' :
                        'bg-zinc-700'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-zinc-300">{step.action}</p>
                        {step.message && <p className="text-xs text-zinc-600">{step.message}</p>}
                      </div>
                      <span className="text-[10px] text-zinc-700 flex-shrink-0">
                        {new Date(step.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </div>
                  ))}
                </div>

                {sess.olx_ad_url && (
                  <a href={sess.olx_ad_url} target="_blank" className="mt-3 block text-xs text-indigo-400 hover:underline truncate">
                    {sess.olx_ad_url}
                  </a>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Scheduled */}
      {activeTab === 'scheduled' && (
        <div className="space-y-3">
          {scheduled.length === 0 ? (
            <div className="premium-card p-12 text-center">
              <Calendar className="mx-auto h-10 w-10 text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">Nenhuma publicação agendada.</p>
              <p className="text-xs text-zinc-700 mt-1">O Motor de Exposição agenda automaticamente nos melhores horários.</p>
            </div>
          ) : (
            scheduled.map((s, i) => (
              <div key={s.id} className="premium-card p-4 flex items-center gap-4 slide-in" style={{ animationDelay: `${i * 50}ms` }}>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <Clock className="h-5 w-5 text-amber-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{s.product_title}</p>
                  <p className="text-xs text-zinc-500">{s.account_email} · {s.variation_title || 'Variação padrão'}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-white">
                    {new Date(s.scheduled_time).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {new Date(s.scheduled_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* History */}
      {activeTab === 'history' && (
        <div className="space-y-2">
          {activity.length === 0 ? (
            <div className="premium-card p-12 text-center">
              <Activity className="mx-auto h-10 w-10 text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">Sem atividade ainda.</p>
            </div>
          ) : (
            activity.map((a, i) => (
              <div key={i} className="premium-card p-3 flex items-center gap-3 text-sm">
                <div className={`h-2 w-2 rounded-full flex-shrink-0 ${
                  a.status === 'success' ? 'bg-emerald-500' :
                  a.status === 'error' ? 'bg-red-500' : 'bg-indigo-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <span className="text-zinc-300">{a.action}</span>
                  <span className="text-zinc-600 mx-2">·</span>
                  <span className="text-zinc-500">{a.account_email}</span>
                </div>
                {a.message && <span className="text-xs text-zinc-600 truncate">{a.message}</span>}
                <span className="text-[10px] text-zinc-700 flex-shrink-0">
                  {new Date(a.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function CdpSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div><div className="skeleton h-8 w-32" /><div className="skeleton h-4 w-48 mt-2" /></div>
        <div className="skeleton h-8 w-24 rounded-full" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-20 rounded-2xl" />)}
      </div>
      <div className="skeleton h-10 w-96 rounded-xl" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => <div key={i} className="skeleton h-32 rounded-2xl" />)}
      </div>
    </div>
  )
}
