'use client'

import { createContext, useContext, useState, useEffect } from 'react'

type Theme = 'light' | 'dark'
type ThemeContextType = { theme: Theme; toggle: () => void }

const ThemeContext = createContext<ThemeContextType>({ theme: 'dark', toggle: () => {} })

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>('dark')

  useEffect(() => {
    const saved = (typeof window !== 'undefined' && localStorage.getItem('theme')) as Theme || 'dark'
    setTheme(saved)
  }, [])

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('theme', next)
    if (next === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
