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
    const interval = setInterval(loadMessages, 5000) // Auto-refresh
    return () => clearInterval(interval)
  }, [])

  const loadMessages = async () => {
    try {
      const data = await api.getChatMessages()
      setMessages(data)
    } catch {} finally { setLoading(false) }
  }

  const handleResolve = async (id: string) => {
    try {
      await api.resolveMessage(id)
      toast.success('Conversa resolvida')
      loadMessages()
    } catch { toast.error('Erro ao resolver') }
  }

  if (loading) return <div className="animate-pulse text-slate-400">Carregando...</div>

  const pending = messages.filter(m => m.status === 'human_needed')
  const aiHandled = messages.filter(m => m.status === 'ai_responded')
  const resolved = messages.filter(m => m.status === 'resolved')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Chat OLX</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {pending.length} pendente(s) • {aiHandled.length} respondido(s) pela IA • {resolved.length} resolvido(s)
        </p>
      </div>

      {/* Pending — need human attention */}
      {pending.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-red-500 font-semibold text-sm">
            <AlertCircle className="h-4 w-4" />
            Precisa da sua atenção
          </div>
          {pending.map(msg => (
            <MessageCard key={msg.id} msg={msg} onResolve={handleResolve} urgent />
          ))}
        </div>
      )}

      {/* AI handled */}
      {aiHandled.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-green-500 font-semibold text-sm">
            <Bot className="h-4 w-4" />
            Respondido pela IA
          </div>
          {aiHandled.slice(0, 20).map(msg => (
            <MessageCard key={msg.id} msg={msg} onResolve={handleResolve} />
          ))}
        </div>
      )}

      {messages.length === 0 && (
        <div className="card text-center py-12">
          <MessageSquare className="mx-auto h-12 w-12 mb-4 opacity-30" />
          <p style={{ color: 'var(--text-secondary)' }}>Nenhuma mensagem ainda.</p>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            O sistema verifica o chat da OLX a cada 2 minutos.
          </p>
        </div>
      )}
    </div>
  )
}

function MessageCard({ msg, onResolve, urgent }: { msg: ChatMessage; onResolve: (id: string) => void; urgent?: boolean }) {
  const isIncoming = msg.direction === 'incoming'
  return (
    <div className={`card ${urgent ? 'border-red-300 dark:border-red-800' : ''}`}>
      <div className="flex items-start gap-3">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full flex-shrink-0 ${
          isIncoming ? 'bg-blue-100 dark:bg-blue-900/40' : 'bg-green-100 dark:bg-green-900/40'
        }`}>
          {isIncoming ? <User className="h-4 w-4 text-blue-500" /> : <Bot className="h-4 w-4 text-green-500" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">{msg.buyer_name || 'Comprador'}</p>
            {msg.ai_generated && <span className="badge badge-green text-xs">IA</span>}
            {msg.status === 'human_needed' && <span className="badge badge-red text-xs">Ação necessária</span>}
            <span className="text-xs ml-auto" style={{ color: 'var(--text-secondary)' }}>
              {new Date(msg.created_date).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-primary)' }}>
            {msg.message_text}
          </p>
          {msg.status === 'human_needed' && (
            <button onClick={() => onResolve(msg.id)} className="btn-secondary mt-3 text-xs py-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Marcar como resolvido
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
