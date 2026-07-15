'use client'

import { useEffect, useState } from 'react'
import { api, type CalendarEntry, type Performance } from '@/lib/api'
import { Calendar, CheckCircle2, Clock, TrendingUp, Zap, BarChart3, MessageSquare, Eye } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export default function ExposicaoPage() {
  const [calendar, setCalendar] = useState<CalendarEntry[]>([])
  const [performance, setPerformance] = useState<Performance | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getCalendar(), api.getPerformance()])
      .then(([cal, perf]) => { setCalendar(cal); setPerformance(perf) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <ExposicaoSkeleton />

  const grouped: Record<string, CalendarEntry[]> = {}
  calendar.forEach(entry => {
    const date = new Date(entry.scheduled_time).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
    if (!grouped[date]) grouped[date] = []
    grouped[date].push(entry)
  })

  const chartData = (performance?.by_hour || []).map(d => ({
    hora: `${d.hour}h`, views: d.views, chats: d.chats,
  }))

  const totalViews = performance?.by_hour?.reduce((sum, item) => sum + item.views, 0) || 0
  const totalChats = performance?.by_hour?.reduce((sum, item) => sum + item.chats, 0) || 0

  return (
    <div className="space-y-6 fade-in pb-20 md:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-white">Motor de Exposição</h1>
        <p className="text-xs sm:text-sm text-zinc-500">{calendar.length} anúncio(s) planejado(s) pelo motor inteligente</p>
      </div>

      {/* Stats Cards (same pattern as dashboard: grid-cols-2 lg:grid-cols-4, smaller text on mobile) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="premium-card p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 flex-shrink-0">
            <Eye className="h-5 w-5 text-indigo-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] sm:text-xs font-medium text-zinc-500 truncate">Total Visualizações</p>
            <p className="text-sm sm:text-lg font-bold text-white mt-0.5 truncate">
              {totalViews.toLocaleString('pt-BR')}
            </p>
          </div>
        </div>

        <div className="premium-card p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20 flex-shrink-0">
            <MessageSquare className="h-5 w-5 text-amber-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] sm:text-xs font-medium text-zinc-500 truncate">Total Chats</p>
            <p className="text-sm sm:text-lg font-bold text-white mt-0.5 truncate">
              {totalChats.toLocaleString('pt-BR')}
            </p>
          </div>
        </div>

        <div className="premium-card p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 flex-shrink-0">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] sm:text-xs font-medium text-zinc-500 truncate">Taxa de Resposta</p>
            <p className="text-sm sm:text-lg font-bold text-white mt-0.5 truncate">
              {totalViews ? `${((totalChats / totalViews) * 100).toFixed(1)}%` : '0%'}
            </p>
          </div>
        </div>

        <div className="premium-card p-4 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-rose-500/10 flex items-center justify-center border border-rose-500/20 flex-shrink-0">
            <BarChart3 className="h-5 w-5 text-rose-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] sm:text-xs font-medium text-zinc-500 truncate">Média / Hora</p>
            <p className="text-sm sm:text-lg font-bold text-white mt-0.5 truncate">
              {performance?.by_hour?.length ? (totalViews / performance.by_hour.length).toFixed(1) : '0'}
            </p>
          </div>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="premium-card p-4 sm:p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                <TrendingUp className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h2 className="text-sm sm:text-base font-semibold text-white">Performance por Horário</h2>
                <p className="text-xs text-zinc-500">Views e chats por hora do dia</p>
              </div>
            </div>
          </div>
          
          <div className="h-[200px] sm:h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#25252f" />
                <XAxis dataKey="hora" tick={{ fontSize: 10, fill: '#5c5c66' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#5c5c66' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#16161e', border: '1px solid #25252f', borderRadius: '12px', fontSize: '11px' }} />
                <Legend 
                  verticalAlign="top" 
                  height={36} 
                  iconType="circle" 
                  iconSize={8}
                  wrapperStyle={{ fontSize: '11px', paddingBottom: '10px' }} 
                />
                <Bar dataKey="views" fill="#6366f1" radius={[4, 4, 0, 0]} name="Visualizações" />
                <Bar dataKey="chats" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Chats" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Calendar */}
      <div className="premium-card p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20">
              <Calendar className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-semibold text-white">Calendário de Publicação</h2>
              <p className="text-xs text-zinc-500">Distribuição automática nos melhores horários</p>
            </div>
          </div>
        </div>

        <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
          {Object.entries(grouped).map(([date, entries]) => (
            <div key={date} className="space-y-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-indigo-400 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20">{date}</span>
                <span className="text-xs text-zinc-600">{entries.length} anúncio(s)</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {entries.map((entry, i) => (
                  <div key={i} className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-3 justify-between">
                    <div className="flex items-start gap-3 min-w-0">
                      {entry.is_executed ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0 mt-0.5 sm:mt-0" />
                      ) : (
                        <Clock className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5 sm:mt-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs sm:text-sm font-medium text-white truncate">
                          {new Date(entry.scheduled_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                          {' — '}
                          {entry.product_title || 'Produto'}
                        </p>
                        <p className="text-[11px] sm:text-xs text-zinc-500 truncate mt-0.5">{entry.variation_title || 'Aguardando variação'}</p>
                      </div>
                    </div>
                    {entry.is_executed && (
                      <span className="status-badge active self-start sm:self-auto text-[10px] sm:text-xs mt-1 sm:mt-0">Publicado</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {calendar.length === 0 && (
            <div className="text-center py-12">
              <div className="inline-flex h-12 w-12 sm:h-16 sm:w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
                <Zap className="h-6 w-6 sm:h-8 sm:w-8 text-zinc-600" />
              </div>
              <p className="text-sm text-zinc-500">Nenhum agendamento ainda.</p>
              <p className="text-xs text-zinc-700 mt-1">O motor roda automaticamente nos melhores horários.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ExposicaoSkeleton() {
  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div className="flex flex-col sm:flex-row justify-between gap-4">
        <div><div className="skeleton h-8 w-48" /><div className="skeleton h-4 w-64 mt-2" /></div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
      </div>
      <div className="skeleton h-72 rounded-2xl" />
      <div className="skeleton h-96 rounded-2xl" />
    </div>
  )
}
