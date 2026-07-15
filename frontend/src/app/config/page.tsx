'use client'

import { useEffect, useState } from 'react'
import { api, type OlxAccount } from '@/lib/api'
import { Plus, Trash2, Shield, RefreshCw, AlertCircle, CheckCircle2, Loader2, Radio, Zap, X, Cpu, Wifi } from 'lucide-react'
import { toast } from 'sonner'

export default function ConfigPage() {
  const [accounts, setAccounts] = useState<OlxAccount[]>([])
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [form, setForm] = useState({ email: '', password: '' })

  useEffect(() => { loadAccounts() }, [])

  const loadAccounts = async () => {
    try { setAccounts(await api.getAccounts()) }
    catch {}
    finally { setLoading(false) }
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setConnecting(true)
    try {
      await api.addAccount({ email: form.email, password: form.password, account_type: 'free' })
      toast.success('Conta OLX adicionada! Conectando via CDP...')
      setShowForm(false)
      setForm({ email: '', password: '' })
      loadAccounts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao adicionar conta')
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="space-y-6 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Configurações</h1>
        <p className="text-sm text-zinc-500 mt-1">Gerencie suas contas OLX e sistema</p>
      </div>

      {/* OLX Accounts */}
      <div className="premium-card p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20">
              <Shield className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Contas OLX</h2>
              <p className="text-xs text-zinc-500">{accounts.length} conta(s) conectada(s)</p>
            </div>
          </div>
          <button onClick={() => setShowForm(true)} className="btn-accent">
            <Plus className="h-4 w-4" />
            Conectar OLX
          </button>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => <div key={i} className="skeleton h-16 rounded-xl" />)}
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-10">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
              <Radio className="h-8 w-8 text-zinc-600" />
            </div>
            <p className="text-sm text-zinc-500">Nenhuma conta OLX conectada.</p>
            <p className="text-xs text-zinc-700 mt-1">Adicione com apenas email e senha — o sistema detecta o tipo automaticamente.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {accounts.map(acc => (
              <div key={acc.id} className="flex items-center gap-4 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-4">
                <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                  acc.is_authenticated ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'
                }`}>
                  {acc.is_authenticated ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <AlertCircle className="h-5 w-5 text-red-400" />}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">{acc.email}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`status-badge ${acc.account_type === 'professional' ? 'active' : 'idle'}`}>
                      {acc.account_type === 'professional' ? 'Profissional' : 'Gratuita'}
                    </span>
                    {acc.is_authenticated ? (
                      <span className="text-xs text-emerald-400">Autenticada</span>
                    ) : (
                      <span className="text-xs text-amber-400">Conectando via CDP...</span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-600">Disponível</p>
                  <p className="text-lg font-bold text-white">{acc.remaining_this_month}<span className="text-sm text-zinc-600">/{acc.total_monthly_limit}</span></p>
                </div>
                <button onClick={() => { loadAccounts(); toast.info('Sincronizando...') }} className="btn-ghost p-2">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* System info */}
      <div className="premium-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-800/50 border border-zinc-700">
            <Cpu className="h-5 w-5 text-zinc-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Sobre o Sistema</h2>
            <p className="text-xs text-zinc-500">Tecnologia por trás do AUTOMATIZA AI</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <InfoItem label="Automação" value="CDP" sub="Chrome DevTools Protocol" icon={Zap} color="indigo" />
          <InfoItem label="IA Texto" value="GPT-4o" sub="Variações de título/descrição" icon={Cpu} color="blue" />
          <InfoItem label="IA Imagem" value="gpt-image-2" sub="Imagens únicas" icon={Zap} color="emerald" />
          <InfoItem label="Modo" value="Stealth" sub="Indetectável" icon={Wifi} color="amber" />
        </div>
      </div>

      {/* Add Account Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setShowForm(false)}>
          <div className="w-full max-w-md premium-card p-6 fade-in" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                  <Shield className="h-5 w-5 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">Conectar OLX</h2>
                  <p className="text-xs text-zinc-500">Login automático via CDP</p>
                </div>
              </div>
              <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Email da OLX</label>
                <input className="premium-input" required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="seu@email.com" />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Senha da OLX</label>
                <input className="premium-input" required type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="••••••••" />
              </div>
              <div className="rounded-xl bg-indigo-500/5 border border-indigo-500/15 p-3">
                <p className="text-xs text-zinc-400">
                  <Shield className="inline h-3.5 w-3.5 text-indigo-400 mr-1" />
                  O sistema fará login automaticamente via CDP, detectará se a conta é profissional ou gratuita, e sincronizará os limites — tudo sozinho.
                </p>
              </div>
              <button type="submit" disabled={connecting} className="btn-accent w-full justify-center">
                {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                {connecting ? 'Conectando...' : 'Conectar conta'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function InfoItem({ label, value, sub, icon: Icon, color }: { label: string; value: string; sub: string; icon: any; color: string }) {
  const colors: Record<string, string> = {
    indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  }
  return (
    <div className="flex items-center gap-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-3">
      <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${colors[color]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs text-zinc-500">{label}</p>
        <p className="text-sm font-semibold text-white">{value}</p>
        <p className="text-[10px] text-zinc-600">{sub}</p>
      </div>
    </div>
  )
}
