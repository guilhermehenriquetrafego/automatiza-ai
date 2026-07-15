'use client'

import { useEffect, useState } from 'react'
import { api, type ChatMessage } from '@/lib/api'
import { MessageSquare, Bot, User, CheckCircle2, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMessages()
    const interval = setInterval(loadMessages, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadMessages = async () => {
    try { setMessages(await api.getChatMessages()) }
    catch {}
    finally { setLoading(false) }
  }

  const handleResolve = async (id: string) => {
    try {
      await api.resolveMessage(id)
      toast.success('Conversa resolvida')
      loadMessages()
    } catch { toast.error('Erro ao resolver') }
  }

  if (loading) return <ChatSkeleton />

  const pending = messages.filter(m => m.status === 'human_needed')
  const aiHandled = messages.filter(m => m.status === 'ai_responded')
  const resolved = messages.filter(m => m.status === 'resolved')

  return (
    <div className="space-y-6 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Chat OLX</h1>
        <p className="text-sm text-zinc-500 mt-1">
          {pending.length} pendente(s) · {aiHandled.length} respondido(s) pela IA · {resolved.length} resolvido(s)
        </p>
      </div>

      {/* Pending */}
      {pending.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-red-400 font-medium text-sm">
            <AlertCircle className="h-4 w-4" />
            Precisa da sua atenção
          </div>
          {pending.map(msg => <MessageCard key={msg.id} msg={msg} onResolve={handleResolve} urgent />)}
        </div>
      )}

      {/* AI handled */}
      {aiHandled.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-emerald-400 font-medium text-sm">
            <Bot className="h-4 w-4" />
            Respondido pela IA
          </div>
          {aiHandled.slice(0, 20).map(msg => <MessageCard key={msg.id} msg={msg} onResolve={handleResolve} />)}
        </div>
      )}

      {messages.length === 0 && (
        <div className="premium-card p-12 text-center">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
            <MessageSquare className="h-8 w-8 text-zinc-600" />
          </div>
          <h3 className="text-base font-semibold text-white">Nenhuma mensagem ainda</h3>
          <p className="text-sm text-zinc-500 mt-1 max-w-sm mx-auto">
            O sistema verifica o chat da OLX a cada 2 minutos. Quando chegar uma mensagem, aparece aqui.
          </p>
        </div>
      )}
    </div>
  )
}

function MessageCard({ msg, onResolve, urgent }: { msg: ChatMessage; onResolve: (id: string) => void; urgent?: boolean }) {
  const isIncoming = msg.direction === 'incoming'
  return (
    <div className={`premium-card p-4 ${urgent ? 'border-red-500/30' : ''}`}>
      <div className="flex items-start gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-full flex-shrink-0 ${
          isIncoming ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-emerald-500/10 border border-emerald-500/20'
        }`}>
          {isIncoming ? <User className="h-4 w-4 text-blue-400" /> : <Bot className="h-4 w-4 text-emerald-400" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm font-medium text-white">{msg.buyer_name || 'Comprador'}</p>
            {msg.ai_generated && <span className="status-badge active text-[10px] px-2 py-0.5">IA</span>}
            {msg.status === 'human_needed' && <span className="status-badge error text-[10px] px-2 py-0.5">Urgente</span>}
            <span className="text-[10px] text-zinc-700 ml-auto">
              {new Date(msg.created_date).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <p className="text-sm text-zinc-300">{msg.message_text}</p>
          {msg.status === 'human_needed' && (
            <button onClick={() => onResolve(msg.id)} className="btn-ghost mt-3 text-xs py-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Marcar como resolvido
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ChatSkeleton() {
  return (
    <div className="space-y-6">
      <div><div className="skeleton h-8 w-48" /><div className="skeleton h-4 w-64 mt-2" /></div>
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
      </div>
    </div>
  )
}
