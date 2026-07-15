'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/lib/auth-context'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

export default function LoginPage() {
  const { login, register, googleLogin } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const googleBtnRef = useRef<HTMLDivElement>(null)

  // Google Client ID — set this in your environment variables
  const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

  useEffect(() => {
    // Only load Google script if we have a client ID
    if (!GOOGLE_CLIENT_ID || !googleBtnRef.current) return

    // Check if script already loaded
    if (document.querySelector('script[src*="accounts.google.com/gsi/client"]')) {
      initGoogleButton()
      return
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = initGoogleButton
    document.head.appendChild(script)

    return () => {
      // Cleanup
      window.google = undefined as any
    }
  }, [GOOGLE_CLIENT_ID, mode])

  const initGoogleButton = () => {
    if (!window.google || !googleBtnRef.current) return

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleResponse,
      auto_select: false,
      cancel_on_tap_outside: true,
    })

    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'outline',
      size: 'large',
      width: '100%',
      text: 'continue_with',
      shape: 'rounded',
      locale: 'pt-BR',
    })
  }

  const handleGoogleResponse = async (response: { credential: string }) => {
    setGoogleLoading(true)
    try {
      await googleLogin(response.credential)
      toast.success('Bem-vindo!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao entrar com Google')
    } finally {
      setGoogleLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
        toast.success('Bem-vindo de volta!')
      } else {
        await register(email, password, fullName)
        toast.success('Conta criada com sucesso!')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao autenticar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
      {/* Glow effect */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mb-3 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/30">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">AUTOMATIZA AI</h1>
          <p className="mt-1 text-sm text-slate-400">Gestão de Exposição de Anúncios OLX</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-8 backdrop-blur-xl">
          {/* Tabs */}
          <div className="mb-6 flex gap-2 rounded-xl bg-slate-900/50 p-1">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
                mode === 'login'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Entrar
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
                mode === 'register'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Criar Conta
            </button>
          </div>

          {/* Google Sign In */}
          {GOOGLE_CLIENT_ID && (
            <div className="mb-5">
              <div ref={googleBtnRef} className="gsi-container w-full" />
              {googleLoading && (
                <div className="mt-2 flex items-center justify-center gap-2 text-sm text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Entrando com Google...
                </div>
              )}
              {/* Divider */}
              <div className="my-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-slate-700/50" />
                <span className="text-xs text-slate-500">ou</span>
                <div className="h-px flex-1 bg-slate-700/50" />
              </div>
            </div>
          )}

          {/* Fallback Google button (when no Client ID configured) */}
          {!GOOGLE_CLIENT_ID && (
            <div className="mb-5">
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-center text-xs text-amber-400">
                Login com Google em breve. Use email e senha por enquanto.
              </div>
              <div className="my-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-slate-700/50" />
                <span className="text-xs text-slate-500">ou</span>
                <div className="h-px flex-1 bg-slate-700/50" />
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  Nome completo
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-lg border border-slate-600/50 bg-slate-900/50 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Seu nome"
                />
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-600/50 bg-slate-900/50 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="seu@email.com"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">
                Senha
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-600/50 bg-slate-900/50 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-500 to-indigo-600 px-4 py-2.5 font-medium text-white transition hover:from-blue-600 hover:to-indigo-700 disabled:opacity-50"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {mode === 'login' ? 'Entrar' : 'Criar conta'}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-slate-500">
            Ao continuar, você concorda com os Termos de Uso e a Política de Privacidade.
          </p>
        </div>
      </div>
    </div>
  )
}

// Type declaration for Google Identity Services
declare global {
  interface Window {
    google: {
      accounts: {
        id: {
          initialize: (config: any) => void
          renderButton: (parent: HTMLElement, options: any) => void
          prompt: () => void
        }
      }
    }
  }
}
