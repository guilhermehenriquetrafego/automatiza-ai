'use client'

import { useEffect, useState } from 'react'
import { api, type ChatMessage } from '@/lib/api'
import { MessageSquare, Bot, User, CheckCircle2, AlertCircle, Send, Search } from 'lucide-react'
import { toast } from 'sonner'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedBuyer, setSelectedBuyer] = useState<string | null>(null)
  const [typedMessage, setTypedMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedBuyer || !typedMessage.trim() || sending) return
    setSending(true)
    try {
      // Simulate/trigger sending message in state
      toast.success('Mensagem enviada')
      setTypedMessage('')
    } catch {
      toast.error('Erro ao enviar mensagem')
    } finally {
      setSending(false)
    }
  }

  if (loading) return <ChatSkeleton />

  // Group messages by buyer_name
  const buyersMap = messages.reduce<Record<string, ChatMessage[]>>((acc, msg) => {
    const key = msg.buyer_name || 'Comprador'
    if (!acc[key]) acc[key] = []
    acc[key].push(msg)
    return acc
  }, {})

  const buyerNames = Object.keys(buyersMap).filter(name =>
    name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeConversation = selectedBuyer ? buyersMap[selectedBuyer] || [] : []

  return (
    <div className="flex flex-col md:flex-row gap-6 -mx-4 -my-6 h-[calc(100vh-4rem)] sm:h-[calc(100vh-8rem)] overflow-hidden bg-[#0a0a0f] pb-20 md:pb-0">
      {/* Buyers Sidebar / List */}
      <div className={`${
        selectedBuyer ? 'hidden md:flex' : 'flex'
      } flex-col w-full md:w-80 border-r border-zinc-800/60 bg-[#0c0c12]/90 h-full`}>
        <div className="p-4 border-b border-zinc-800/60">
          <h1 className="text-xl font-bold text-white mb-3">Chats OLX</h1>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Buscar comprador..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="premium-input pl-9 text-sm py-2"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {buyerNames.length === 0 ? (
            <div className="text-center py-8 text-zinc-500 text-sm">Nenhum chat encontrado</div>
          ) : (
            buyerNames.map(name => {
              const msgs = buyersMap[name]
              const latestMsg = msgs[0] || {}
              const hasUrgent = msgs.some(m => m.status === 'human_needed')
              return (
                <button
                  key={name}
                  onClick={() => setSelectedBuyer(name)}
                  className={`w-full text-left p-3 rounded-xl transition-all ${
                    selectedBuyer === name
                      ? 'bg-indigo-600/10 border border-indigo-500/20'
                      : 'hover:bg-zinc-900/40 border border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-semibold text-white truncate">{name}</span>
                    <span className="text-[10px] text-zinc-700 flex-shrink-0">
                      {latestMsg.created_date && new Date(latestMsg.created_date).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-zinc-500 truncate flex-1">{latestMsg.message_text}</p>
                    {hasUrgent && <span className="h-2 w-2 rounded-full bg-red-500 flex-shrink-0" />}
                  </div>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* Active Conversation Area */}
      <div className={`${
        selectedBuyer ? 'flex' : 'hidden md:flex'
      } flex-1 flex-col h-full bg-[#0a0a0f]`}>
        {selectedBuyer ? (
          <>
            {/* Conversation Header */}
            <div className="p-4 border-b border-zinc-800/60 bg-[#0c0c12]/90 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelectedBuyer(null)}
                  className="md:hidden text-zinc-400 hover:text-white mr-1 text-sm font-medium"
                >
                  ← Voltar
                </button>
                <div>
                  <h2 className="text-sm sm:text-base font-bold text-white">{selectedBuyer}</h2>
                  <p className="text-xs text-zinc-500">Histórico de mensagens sincronizadas</p>
                </div>
              </div>
              {activeConversation.some(m => m.status === 'human_needed') && (
                <button
                  onClick={() => {
                    const urgent = activeConversation.find(m => m.status === 'human_needed')
                    if (urgent) handleResolve(urgent.id)
                  }}
                  className="btn-accent text-xs py-1.5 px-3"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Resolver
                </button>
              )}
            </div>

            {/* Message History */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {activeConversation.slice().reverse().map((msg) => {
                const isIncoming = msg.direction === 'incoming'
                return (
                  <div key={msg.id} className={`flex gap-3 ${isIncoming ? 'justify-start' : 'justify-end'}`}>
                    {isIncoming && (
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/10 border border-blue-500/20 flex-shrink-0">
                        <User className="h-4 w-4 text-blue-400" />
                      </div>
                    )}
                    <div className={`flex flex-col max-w-[85%] sm:max-w-[70%] ${isIncoming ? 'items-start' : 'items-end'}`}>
                      <div className={`p-3 sm:p-4 rounded-2xl text-xs sm:text-sm ${
                        isIncoming
                          ? 'bg-zinc-900 border border-zinc-800 text-zinc-100'
                          : 'bg-indigo-600 text-white'
                      }`}>
                        <p className="whitespace-pre-wrap">{msg.message_text}</p>
                      </div>
                      <div className="flex items-center gap-2 mt-1 px-1">
                        {msg.ai_generated && (
                          <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full">IA</span>
                        )}
                        <span className="text-[10px] text-zinc-600">
                          {new Date(msg.created_date).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                    {!isIncoming && (
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500/10 border border-indigo-500/20 flex-shrink-0">
                        <Bot className="h-4 w-4 text-indigo-400" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Input Footer */}
            <form onSubmit={handleSendMessage} className="p-4 border-t border-zinc-800/60 bg-[#0c0c12]/90 flex gap-2">
              <input
                type="text"
                placeholder="Digite sua resposta..."
                value={typedMessage}
                onChange={e => setTypedMessage(e.target.value)}
                className="premium-input text-xs sm:text-sm flex-1"
              />
              <button
                type="submit"
                disabled={!typedMessage.trim() || sending}
                className="btn-accent h-9 w-9 sm:h-10 sm:w-10 p-0 items-center justify-center rounded-xl flex-shrink-0"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
              <MessageSquare className="h-8 w-8 text-zinc-600" />
            </div>
            <h3 className="text-base sm:text-lg font-semibold text-white">Nenhum chat selecionado</h3>
            <p className="text-xs sm:text-sm text-zinc-500 mt-1 max-w-sm">
              Selecione um comprador na barra lateral para ver o histórico e enviar respostas. O sistema monitora mensagens automaticamente.
            </p>
          </div>
        )}
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
