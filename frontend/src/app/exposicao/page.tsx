'use client'

import { useEffect, useState } from 'react'
import { api, type CalendarEntry, type Performance } from '@/lib/api'
import { Calendar, CheckCircle2, Clock, TrendingUp } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

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

  if (loading) return <div className="animate-pulse text-slate-400">Carregando...</div>

  // Group calendar entries by date
  const grouped: Record<string, CalendarEntry[]> = {}
  calendar.forEach(entry => {
    const date = new Date(entry.scheduled_time).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
    if (!grouped[date]) grouped[date] = []
    grouped[date].push(entry)
  })

  // Performance chart data
  const chartData = (performance?.by_hour || []).map(d => ({
    hora: `${d.hour}h`, views: d.views, chats: d.chats,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Motor de Exposição</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Calendário inteligente de publicação — {calendar.length} anúncios planejados
        </p>
      </div>

      {/* Performance chart */}
      {chartData.length > 0 && (
        <div className="card">
          <div className="mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-brand-600" />
            <h2 className="text-lg font-semibold">Performance por Horário</h2>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="hora" tick={{ fontSize: 12 }} stroke="var(--text-secondary)" />
              <YAxis tick={{ fontSize: 12 }} stroke="var(--text-secondary)" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                }}
              />
              <Bar dataKey="views" fill="#6366f1" radius={[4, 4, 0, 0]} name="Visualizações" />
              <Bar dataKey="chats" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Chats" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Calendar */}
      <div className="card">
        <div className="mb-4 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-brand-600" />
          <h2 className="text-lg font-semibold">Calendário de Publicação</h2>
        </div>

        <div className="space-y-3 max-h-[500px] overflow-y-auto">
          {Object.entries(grouped).map(([date, entries]) => (
            <div key={date}>
              <div className="mb-2 flex items-center gap-2">
                <span className="badge badge-blue">{date}</span>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {entries.length} anúncio(s)
                </span>
              </div>
              <div className="space-y-2">
                {entries.map((entry, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border p-3"
                    style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-secondary)' }}>
                    {entry.is_executed ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                    ) : (
                      <Clock className="h-5 w-5 text-amber-500 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {new Date(entry.scheduled_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                        {' — '}
                        {entry.product_title || 'Produto'}
                      </p>
                      <p className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>
                        {entry.variation_title || 'Aguardando variação'}
                      </p>
                    </div>
                    {entry.is_executed && (
                      <span className="badge badge-green">Publicado</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {calendar.length === 0 && (
            <div className="text-center py-8">
              <Calendar className="mx-auto h-10 w-10 mb-3 opacity-30" />
              <p style={{ color: 'var(--text-secondary)' }}>
                Nenhum agendamento. O Motor de Exposição roda à meia-noite.
              </p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                Você também pode forçar o recálculo pelo Dashboard.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
