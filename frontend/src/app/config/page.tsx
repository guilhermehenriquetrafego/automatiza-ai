'use client'

import { useEffect, useState } from 'react'
import { api, type OlxAccount } from '@/lib/api'
import { Plus, Trash2, Shield, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

export default function ConfigPage() {
  const [accounts, setAccounts] = useState<OlxAccount[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', account_type: 'professional' })

  useEffect(() => { loadAccounts() }, [])

  const loadAccounts = async () => {
    try {
      setAccounts(await api.getAccounts())
    } catch {}
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.addAccount(form)
      toast.success('Conta OLX adicionada! Autenticando via CDP...')
      setShowForm(false)
      setForm({ email: '', password: '', account_type: 'professional' })
      loadAccounts()
    } catch { toast.error('Erro ao adicionar conta') }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Configurações</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Gerencie suas contas OLX
        </p>
      </div>

      {/* OLX Accounts */}
      <div className="card">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-brand-600" />
            <h2 className="text-lg font-semibold">Contas OLX</h2>
          </div>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary">
            <Plus className="h-4 w-4" />
            Adicionar Conta
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleAdd} className="mb-4 space-y-3 rounded-lg border p-4"
            style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-secondary)' }}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Email OLX</label>
                <input className="input" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required placeholder="seu@email.com" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Senha</label>
                <input className="input" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required placeholder="••••••••" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Tipo de Conta</label>
              <select className="input" value={form.account_type} onChange={e => setForm({ ...form, account_type: e.target.value })}>
                <option value="professional">Profissional (paga — limite compartilhado)</option>
                <option value="free">Gratuita (limites por categoria)</option>
              </select>
            </div>
            <button type="submit" className="btn-primary">Adicionar e Autenticar</button>
          </form>
        )}

        <div className="space-y-3">
          {accounts.map(acc => (
            <div key={acc.id} className="flex items-center gap-4 rounded-lg border p-4"
              style={{ borderColor: 'var(--border-color)' }}>
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                acc.is_authenticated ? 'bg-green-100 dark:bg-green-900/40' : 'bg-red-100 dark:bg-red-900/40'
              }`}>
                {acc.is_authenticated ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : <AlertCircle className="h-5 w-5 text-red-500" />}
              </div>
              <div className="flex-1">
                <p className="font-medium text-sm">{acc.email}</p>
                <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  <span className={`badge ${acc.account_type === 'professional' ? 'badge-blue' : 'badge-gray'}`}>
                    {acc.account_type === 'professional' ? 'Profissional' : 'Gratuita'}
                  </span>
                  {acc.is_authenticated ? (
                    <span className="text-green-500">Autenticada</span>
                  ) : (
                    <span className="text-red-500">Precisa re-autenticar</span>
                  )}
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Disponível</p>
                <p className="text-lg font-bold">{acc.remaining_this_month}/{acc.total_monthly_limit}</p>
              </div>
              <button onClick={() => { api.getAccounts(); toast.info('Sincronizando limites...') }} className="btn-secondary p-2">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
          ))}
          {accounts.length === 0 && (
            <div className="text-center py-8">
              <Shield className="mx-auto h-10 w-10 mb-3 opacity-30" />
              <p style={{ color: 'var(--text-secondary)' }}>Nenhuma conta OLX conectada.</p>
            </div>
          )}
        </div>
      </div>

      {/* System info */}
      <div className="card">
        <h2 className="mb-3 text-lg font-semibold">Sobre o Sistema</h2>
        <div className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <div className="flex justify-between"><span>Automação</span><span className="font-mono">CDP (Chrome DevTools Protocol)</span></div>
          <div className="flex justify-between"><span>IA Texto</span><span className="font-mono">GPT-4o</span></div>
          <div className="flex justify-between"><span>IA Imagem</span><span className="font-mono">gpt-image-2</span></div>
          <div className="flex justify-between"><span>Modo</span><span className="font-mono">Stealth (indetectável)</span></div>
        </div>
      </div>
    </div>
  )
}
