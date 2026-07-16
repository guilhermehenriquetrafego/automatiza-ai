'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/lib/auth-context'
import { toast } from 'sonner'
import { Loader2, Zap, ArrowRight, Sparkles } from 'lucide-react'

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
        <div className="absolute left-1/2 top-1/4 h-[350px] w-[350px] sm:h-[600px] sm:w-[600px] -translate-x-1/2 rounded-full bg-indigo-600/10 blur-[130px] animate-pulse-subtle" />
        <div className="absolute right-1/4 bottom-1/4 h-[250px] w-[250px] sm:h-[400px] sm:w-[400px] rounded-full bg-purple-500/8 blur-[110px]" />
      </div>

      {/* Grid pattern */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.04]" style={{
        backgroundImage: 'linear-gradient(#6366f1 1px, transparent 1px), linear-gradient(90deg, #6366f1 1px, transparent 1px)',
        backgroundSize: '48px 48px'
      }} />

      <div className="relative z-10 w-full max-w-[420px] animate-slide-up">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-indigo-700 shadow-xl shadow-indigo-500/25 relative group">
            <div className="absolute inset-0 rounded-2xl bg-indigo-400 blur-md opacity-20 group-hover:opacity-40 transition-opacity" />
            <Zap className="h-7 w-7 text-white relative z-10" fill="white" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center justify-center gap-1">
            <span className="gradient-text">AUTOMATIZA</span>
            <span className="text-indigo-400 font-black relative">
              AI
              <span className="absolute -top-1 -right-4 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </span>
            </span>
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-zinc-400/80 font-medium">Gestão inteligente de exposição de anúncios OLX</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-zinc-800/80 bg-[#13131a]/70 backdrop-blur-md p-6 sm:p-8 shadow-premium relative">
          {/* Subtle top light effect */}
          <div className="absolute top-0 inset-x-1/4 h-px bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent" />
          
          {/* Mode toggle */}
          <div className="mb-6 flex gap-1 rounded-xl bg-zinc-950/60 p-1.5 border border-zinc-800/40">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-lg py-2.5 text-xs sm:text-sm font-semibold transition-all ${
                  mode === m
                    ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-600/15'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {m === 'login' ? 'Entrar' : 'Criar conta'}
              </button>
            ))}
          </div>

          {/* Google button */}
          {GOOGLE_CLIENT_ID ? (
            <div className="mb-5">
              <div ref={googleBtnRef} className="w-full flex justify-center [&_iframe]:!w-full [&_div]:!w-full border border-zinc-800 rounded-lg overflow-hidden hover:border-zinc-700 transition" />
              {googleLoading && (
                <p className="mt-2 text-center text-xs text-zinc-500 animate-pulse">Conectando com Google...</p>
              )}
              <div className="my-5 flex items-center gap-3">
                <div className="h-px flex-1 bg-zinc-800/80" />
                <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">ou com email</span>
                <div className="h-px flex-1 bg-zinc-800/80" />
              </div>
            </div>
          ) : null}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div className="animate-fade-in">
                <label className="mb-1.5 block text-xs font-semibold text-zinc-400/90">Nome completo</label>
                <input
                  type="text" required value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="premium-input [touch-action:manipulation]"
                  placeholder="Como devemos te chamar?"
                />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-400/90">Email</label>
              <input
                type="email" autoComplete="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="premium-input [touch-action:manipulation]"
                placeholder="voce@email.com"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-400/90">Senha</label>
              <input
                type="password" required minLength={6} value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="premium-input [touch-action:manipulation]"
                placeholder="Mínimo 6 caracteres"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-accent w-full justify-center mt-6 py-3 font-bold group">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <span>{mode === 'login' ? 'Entrar na Plataforma' : 'Criar minha Conta'}</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-[11px] text-zinc-500 leading-relaxed">
            Ao continuar, você concorda com nossos <a href="#" className="hover:text-indigo-400 transition underline">Termos de Uso</a> e <a href="#" className="hover:text-indigo-400 transition underline">Política de Privacidade</a>.
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
