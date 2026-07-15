'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { api } from '@/lib/api'

interface AuthUser {
  id: string
  email: string
  full_name: string
  plan_tier: string
  max_products?: number
  max_olx_accounts?: number
}

interface AuthContextType {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, full_name: string) => Promise<void>
  googleLogin: (credential: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      if (pathname !== '/login') router.push('/login')
      return
    }
    api.getOverview().then(() => {
      const stored = localStorage.getItem('user')
      if (stored) setUser(JSON.parse(stored))
      setLoading(false)
    }).catch(() => {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      setLoading(false)
      if (pathname !== '/login') router.push('/login')
    })
  }, [])

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password)
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
    setUser(res.user)
    router.push('/')
  }

  const register = async (email: string, password: string, full_name: string) => {
    const res = await api.register({ email, password, full_name })
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
    setUser(res.user)
    router.push('/')
  }

  const googleLogin = async (credential: string) => {
    const res = await api.googleAuth(credential)
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
    setUser(res.user)
    router.push('/')
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    router.push('/login')
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, googleLogin, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
