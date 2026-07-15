'use client'

import { useEffect, useState } from 'react'
import { api, type CdpSession, type CdpActivity, type ScheduledAction, type OlxAccount } from '@/lib/api'
import { Activity, Clock, CheckCircle2, AlertCircle, Loader2, Zap, Calendar, Cpu, Wifi, Monitor, Play, RefreshCw, KeyRound, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'

export default function CdpLivePage() {
  const [sessions, setSessions] = useState<CdpSession[]>([])
  const [activity, setActivity] = useState<CdpActivity[]>([])
  const [scheduled, setScheduled] = useState<ScheduledAction[]>([])
  const [accounts, setAccounts] = useState<OlxAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'live' | 'scheduled' | 'history'>('live')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showPasswordModal, setShowPasswordModal] = useState<string | null>(null)
  const [olxPassword, setOlxPassword] = useState('')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sessRes, actRes, schRes, accRes] = await Promise.all([
          api.getCdpSessions().catch(() => []),
          api.getCdpActivity().catch(() => []),
          api.getCdpSchedule().catch(() => []),
          api.getAccounts().catch(() => []),
        ])
        setSessions(sessRes)
        setActivity(actRes)
        setScheduled(schRes)
        setAccounts(accRes)
      } catch {}
      finally { setLoading(false) }
    }

    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleLogin = async (accountId: string) => {
    setShowPasswordModal(accountId)
    setOlxPassword('')
  }

  const confirmLogin = async () => {
    if (!showPasswordModal || !olxPassword) return
    const accountId = showPasswordModal
    setActionLoading(`${accountId}-login`)
    setShowPasswordModal(null)
    try {
      const res = await api.triggerCdpAction({ account_id: accountId, action: 'login', password: olxPassword })
      toast.success(res.message || 'Login CDP iniciado')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Erro ao iniciar login')
    } finally {
      setActionLoading(null)
      setOlxPassword('')
    }
  }

  const handleSync = async (accountId: string) => {
    setActionLoading(`${accountId}-sync_limits`)
    try {
      const res = await api.triggerCdpAction({ account_id: accountId, action: 'sync_limits' })
      toast.success(res.message || 'Sync iniciado')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Erro ao iniciar sync')
    } finally {
      setActionLoading(null)
    }
  }

  const statusColors: Record<string, string> = {
    idle: 'idle', connecting: 'pending', logging_in: 'pending',
    posting: 'pending', syncing: 'pending', success: 'active', error: 'error',
  }

  if (loading) return <CdpSkeleton />

  return (
    <div className="space-y-6 fade-in pb-20 md:pb-0">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">CDP Live</h1>
          <p className="text-sm text-zinc-500 mt-1">Monitoramento em tempo real da automação</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <span className="live-dot" />
          <span className="text-[10px] sm:text-xs font-medium text-emerald-400">Ao vivo</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="premium-card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="h-4 w-4 text-indigo-400" />
            <span className="text-xs text-zinc-500">Sessões ativas</span>
          </div>
          <p className="text-xl font-bold text-white">{sessions.filter(s => !['idle', 'success', 'error'].includes(s.status)).length}</p>
        </div>
        <div className="premium-card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-zinc-500">Eventos hoje</span>
          </div>
          <p className="text-xl font-bold text-white">{activity.length}</p>
        </div>
        <div className="premium-card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="h-4 w-4 text-amber-400" />
            <span className="text-xs text-zinc-500">Agendados</span>
          </div>
          <p className="text-xl font-bold text-white">{scheduled.length}</p>
        </div>
        <div className="premium-card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-2">
            <Wifi className="h-4 w-4 text-blue-400" />
            <span className="text-xs text-zinc-500">CDP Status</span>
          </div>
          <p className="text-sm font-bold text-emerald-400">Conectado</p>
        </div>
      </div>

      {/* Action buttons */}
      {accounts.length > 0 && (
        <div className="premium-card p-4 sm:p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex-shrink-0">
              <Zap className="h-4 w-4 text-indigo-400" fill="currentColor" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Disparar Ação CDP</h2>
              <p className="text-xs text-zinc-500">Login real e sync de limites via Chrome DevTools Protocol</p>
            </div>
          </div>
          <div className="space-y-3">
            {accounts.map(acc => (
              <div key={acc.id} className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-3">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className={`flex h-9 w-9 items-center justify-center rounded-full flex-shrink-0 ${
                    acc.is_authenticated ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'
                  }`}>
                    {acc.is_authenticated ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <AlertCircle className="h-4 w-4 text-red-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{acc.email}</p>
                    <p className="text-xs text-zinc-500">
                      {acc.is_authenticated ? 'Autenticada' : 'Não autenticada'} · {acc.account_type === 'professional' ? 'Profissional' : 'Gratuita'}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  <button
                    onClick={() => handleLogin(acc.id)}
                    disabled={actionLoading === `${acc.id}-login`}
                    className="btn-ghost text-xs py-1.5 px-3 flex-1 sm:flex-none justify-center"
                  >
                    {actionLoading === `${acc.id}-login` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    Login
                  </button>
                  <button
                    onClick={() => handleSync(acc.id)}
                    disabled={actionLoading === `${acc.id}-sync_limits`}
                    className="btn-ghost text-xs py-1.5 px-3 flex-1 sm:flex-none justify-center"
                  >
                    {actionLoading === `${acc.id}-sync_limits` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    Sync
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Password modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowPasswordModal(null)}>
          <div className="premium-card p-5 sm:p-6 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex-shrink-0">
                <KeyRound className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Senha da OLX</h3>
                <p className="text-xs text-zinc-500">Digite a senha da conta OLX para login via CDP</p>
              </div>
            </div>
            <input
              type="password"
              autoFocus
              value={olxPassword}
              onChange={e => setOlxPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && confirmLogin()}
              className="premium-input mb-4"
              placeholder="Senha da conta OLX"
            />
            <div className="flex gap-2">
              <button onClick={() => setShowPasswordModal(null)} className="btn-ghost flex-1 justify-center text-sm">Cancelar</button>
              <button onClick={confirmLogin} disabled={!olxPassword} className="btn-accent flex-1 justify-center text-sm">
                Iniciar Login
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-zinc-900/60 p-1 border border-zinc-800/50 w-full sm:w-fit">
        {(['live', 'scheduled', 'history'] as const).map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={`flex-1 sm:flex-initial text-center px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
              activeTab === t ? 'bg-indigo-600 text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}>
            {t === 'live' ? 'Ao Vivo' : t === 'scheduled' ? 'Agendados' : 'Histórico'}
          </button>
        ))}
      </div>

      {/* Live sessions */}
      {activeTab === 'live' && (
        <div className="space-y-4">
          {sessions.length === 0 ? (
            <div className="premium-card p-8 sm:p-12 text-center">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
                <Monitor className="h-8 w-8 text-zinc-600" />
              </div>
              <h3 className="text-base font-semibold text-white">Nenhuma sessão CDP ativa</h3>
              <p className="text-sm text-zinc-500 mt-1 max-w-sm mx-auto">
                Dispare um Login ou Sync acima. Quando a automação iniciar, você verá cada passo acontecer aqui em tempo real.
              </p>
            </div>
          ) : (
            sessions.slice().reverse().map(sess => (
              <div key={sess.id} className="premium-card p-3 sm:p-4 md:p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl border flex-shrink-0 ${
                      sess.status === 'success' ? 'bg-emerald-500/10 border-emerald-500/20' :
                      sess.status === 'error' ? 'bg-red-500/10 border-red-500/20' :
                      'bg-indigo-500/10 border-indigo-500/20'
                    }`}>
                      {sess.status === 'success' ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> :
                       sess.status === 'error' ? <AlertCircle className="h-5 w-5 text-red-400" /> :
                       <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{sess.account_email}</p>
                      <p className="text-xs text-zinc-500 truncate">{sess.current_action}</p>
                    </div>
                  </div>
                  <span className={`status-badge text-[10px] sm:text-xs w-fit ${statusColors[sess.status] || 'idle'}`}>
                    {sess.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="space-y-2 pl-2">
                  {sess.steps?.map((step, i) => (
                    <div key={i} className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 text-xs sm:text-sm slide-in border-b border-zinc-800/30 sm:border-b-0 pb-2 sm:pb-0 last:border-b-0">
                      <div className="flex items-center gap-2 sm:mt-1.5">
                        <div className={`h-2 w-2 rounded-full flex-shrink-0 ${
                          step.status === 'success' ? 'bg-emerald-500' :
                          step.status === 'error' ? 'bg-red-500' :
                          step.status === 'running' ? 'bg-indigo-500 animate-pulse' : 'bg-zinc-700'
                        }`} />
                        <span className="text-[10px] text-zinc-700 sm:hidden">
                          {new Date(step.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-zinc-300 leading-relaxed">{step.message}</p>
                      </div>
                      <span className="text-[10px] text-zinc-700 flex-shrink-0 hidden sm:inline">
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
            <div className="premium-card p-8 sm:p-12 text-center">
              <Calendar className="mx-auto h-10 w-10 text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">Nenhuma publicação agendada.</p>
              <p className="text-xs text-zinc-700 mt-1">O Motor de Exposição agenda automaticamente nos melhores horários.</p>
            </div>
          ) : (
            scheduled.map((s, i) => (
              <div key={s.id} className="premium-card p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 slide-in" style={{ animationDelay: `${i * 50}ms` }}>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20 flex-shrink-0">
                    <Clock className="h-5 w-5 text-amber-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{s.product_title}</p>
                    <p className="text-xs text-zinc-500 truncate">{s.account_email} · {s.variation_title || 'Variação padrão'}</p>
                  </div>
                </div>
                <div className="text-left sm:text-right border-t border-zinc-800/50 sm:border-t-0 pt-2 sm:pt-0">
                  <p className="text-xs sm:text-sm font-medium text-white">
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
            <div className="premium-card p-8 sm:p-12 text-center">
              <Activity className="mx-auto h-10 w-10 text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">Sem atividade ainda.</p>
            </div>
          ) : (
            activity.map((a, i) => (
              <div key={i} className="premium-card p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs sm:text-sm">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${
                    a.status === 'success' ? 'bg-emerald-500' :
                    a.status === 'error' ? 'bg-red-500' : 'bg-indigo-500'
                  }`} />
                  <div className="min-w-0">
                    <span className="text-zinc-300 font-medium">{a.action}</span>
                    <span className="text-zinc-600 mx-2">·</span>
                    <span className="text-zinc-500 truncate">{a.account_email}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-4 border-t border-zinc-800/30 sm:border-t-0 pt-1.5 sm:pt-0">
                  {a.message && <span className="text-xs text-zinc-600 truncate max-w-[200px] sm:max-w-xs">{a.message}</span>}
                  <span className="text-[10px] text-zinc-700 flex-shrink-0 ml-auto">
                    {new Date(a.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
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
      <div className="skeleton h-32 rounded-2xl" />
      <div className="skeleton h-10 w-96 rounded-xl" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => <div key={i} className="skeleton h-32 rounded-2xl" />)}
      </div>
    </div>
  )
}
