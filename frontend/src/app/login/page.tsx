'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/lib/auth-context'
import { toast } from 'sonner'
import { Loader2, Zap, ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const { login, register, googleLogin } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const googleBtnRef = useRef<HTMLDivElement>(null)
  const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleBtnRef.current) return
    const checkGoogle = () => {
      if (window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleResponse,
        })
        window.google.accounts.id.renderButton(googleBtnRef.current!, {
          theme: 'outline', size: 'large', width: '100%', text: 'continue_with', shape: 'rounded', locale: 'pt-BR',
        })
      } else {
        setTimeout(checkGoogle, 100)
      }
    }

    if (!document.querySelector('script[src*="accounts.google.com/gsi/client"]')) {
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = checkGoogle
      document.head.appendChild(script)
    } else {
      checkGoogle()
    }
  }, [GOOGLE_CLIENT_ID])

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
    <div className="flex min-h-screen items-center justify-center px-4 relative overflow-hidden bg-[#0a0a0f]">
      {/* Ambient glow */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/4 h-[300px] w-[300px] sm:h-[500px] sm:w-[500px] -translate-x-1/2 rounded-full bg-indigo-500/8 blur-[120px]" />
        <div className="absolute right-1/4 bottom-1/4 h-[200px] w-[200px] sm:h-[300px] sm:w-[300px] rounded-full bg-purple-500/5 blur-[100px]" />
      </div>

      {/* Grid pattern */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
        backgroundSize: '40px 40px'
      }} />

      <div className="relative z-10 w-full max-w-[420px]">
        {/* Logo */}
        <div className="mb-10 text-center">
          <div className="mb-4 inline-flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 shadow-xl shadow-indigo-500/30">
            <Zap className="h-6 w-6 sm:h-7 sm:w-7 text-white" fill="white" />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">AUTOMATIZA<span className="text-indigo-400"> AI</span></h1>
          <p className="mt-2 text-xs sm:text-sm text-zinc-500">Gestão inteligente de exposição de anúncios OLX</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-zinc-800/80 bg-[#13131a]/80 backdrop-blur-xl p-6 sm:p-8">
          {/* Mode toggle */}
          <div className="mb-6 flex gap-1 rounded-xl bg-zinc-900/60 p-1 border border-zinc-800/50">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                  mode === m
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {m === 'login' ? 'Entrar' : 'Criar conta'}
              </button>
            ))}
          </div>

          {/* Google button */}
          {GOOGLE_CLIENT_ID ? (
            <div className="mb-5">
              <div ref={googleBtnRef} className="w-full flex justify-center [&_iframe]:!w-full [&_div]:!w-full" />
              {googleLoading && (
                <p className="mt-2 text-center text-xs text-zinc-500">Conectando com Google...</p>
              )}
              <div className="my-5 flex items-center gap-3">
                <div className="h-px flex-1 bg-zinc-800" />
                <span className="text-xs text-zinc-600">ou com email</span>
                <div className="h-px flex-1 bg-zinc-800" />
              </div>
            </div>
          ) : null}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div className="fade-in">
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Nome completo</label>
                <input
                  type="text" required value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="premium-input [touch-action:manipulation]"
                  placeholder="Como devemos te chamar?"
                />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">Email</label>
              <input
                type="email" autoComplete="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="premium-input [touch-action:manipulation]"
                placeholder="voce@email.com"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">Senha</label>
              <input
                type="password" required minLength={6} value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="premium-input [touch-action:manipulation]"
                placeholder="Mínimo 6 caracteres"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-accent w-full justify-center">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {mode === 'login' ? 'Entrar' : 'Criar conta'}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          <p className="mt-5 text-center text-[11px] text-zinc-600">
            Ao continuar, você concorda com os Termos de Uso e a Política de Privacidade.
          </p>
        </div>
      </div>
    </div>
  )
}

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
