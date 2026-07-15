'use client'

import { useEffect, useState } from 'react'
import { api, type CalendarEntry, type Performance } from '@/lib/api'
import { Calendar, CheckCircle2, Clock, TrendingUp, Zap } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

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

  return (
    <div className="space-y-6 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Motor de Exposição</h1>
        <p className="text-sm text-zinc-500 mt-1">{calendar.length} anúncio(s) planejado(s) pelo motor inteligente</p>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="premium-card p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20">
              <TrendingUp className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Performance por Horário</h2>
              <p className="text-xs text-zinc-500">Views e chats por hora do dia</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#25252f" />
              <XAxis dataKey="hora" tick={{ fontSize: 11, fill: '#5c5c66' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#5c5c66' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#16161e', border: '1px solid #25252f', borderRadius: '12px', fontSize: '12px' }} />
              <Bar dataKey="views" fill="#6366f1" radius={[4, 4, 0, 0]} name="Visualizações" />
              <Bar dataKey="chats" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Chats" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Calendar */}
      <div className="premium-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20">
            <Calendar className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Calendário de Publicação</h2>
            <p className="text-xs text-zinc-500">Distribuição automática nos melhores horários</p>
          </div>
        </div>

        <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
          {Object.entries(grouped).map(([date, entries]) => (
            <div key={date}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold text-indigo-400 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20">{date}</span>
                <span className="text-xs text-zinc-600">{entries.length} anúncio(s)</span>
              </div>
              <div className="space-y-2">
                {entries.map((entry, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-3">
                    {entry.is_executed ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <Clock className="h-5 w-5 text-amber-400 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {new Date(entry.scheduled_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                        {' — '}
                        {entry.product_title || 'Produto'}
                      </p>
                      <p className="text-xs text-zinc-500 truncate">{entry.variation_title || 'Aguardando variação'}</p>
                    </div>
                    {entry.is_executed && <span className="status-badge active">Publicado</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {calendar.length === 0 && (
            <div className="text-center py-12">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
                <Zap className="h-8 w-8 text-zinc-600" />
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
    <div className="space-y-6">
      <div><div className="skeleton h-8 w-48" /><div className="skeleton h-4 w-64 mt-2" /></div>
      <div className="skeleton h-72 rounded-2xl" />
      <div className="skeleton h-96 rounded-2xl" />
    </div>
  )
}
