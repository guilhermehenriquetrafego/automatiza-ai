'use client'

import { useEffect, useState } from 'react'
import { api, type Product, type CreateProductReq } from '@/lib/api'
import { Package, Plus, Trash2, X, Search, Tag } from 'lucide-react'
import { toast } from 'sonner'

const CATEGORIES = [
  { value: 'celulares_e_telefonia', label: 'Celulares e Telefonia' },
  { value: 'informatica', label: 'Informática' },
  { value: 'games', label: 'Games' },
  { value: 'audio', label: 'Áudio' },
  { value: 'tvs_e_video', label: 'TVs e Vídeo' },
  { value: 'cameras_e_drones', label: 'Câmeras e Drones' },
]

const CONDITIONS = [
  { value: 'novo', label: 'Novo' },
  { value: 'seminovo', label: 'Seminovo' },
  { value: 'usado', label: 'Usado' },
]

export default function ProdutosPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState<CreateProductReq>({
    title: '', description: '', price: 0, min_price: 0,
    category: 'celulares_e_telefonia', brand: '', model: '', condition: 'novo',
  })

  useEffect(() => { loadProducts() }, [])

  const loadProducts = async () => {
    try { setProducts(await api.getProducts()) }
    catch {}
    finally { setLoading(false) }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createProduct(form)
      toast.success('Produto adicionado! Gerando variações com IA...')
      setShowForm(false)
      setForm({ title: '', description: '', price: 0, min_price: 0, category: 'celulares_e_telefonia', brand: '', model: '', condition: 'novo' })
      loadProducts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar produto')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteProduct(id)
      toast.success('Produto removido')
      loadProducts()
    } catch { toast.error('Erro ao remover') }
  }

  const filtered = products.filter(p =>
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    p.brand?.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) return <CatalogSkeleton />

  return (
    <div className="space-y-6 fade-in pb-20 md:pb-0">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white">Catálogo</h1>
          <p className="text-xs sm:text-sm text-zinc-500 mt-1">{products.length} produto(s) cadastrado(s)</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-accent w-full sm:w-auto">
          <Plus className="h-4 w-4" />
          Adicionar Produto
        </button>
      </div>

      {/* Search */}
      <div className="relative w-full sm:w-auto sm:max-w-xs">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-600" />
        <input
          className="premium-input pl-12 w-full"
          placeholder="Buscar por título ou marca..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Products list / cards */}
      {filtered.length === 0 ? (
        <div className="premium-card p-8 sm:p-12 text-center">
          <div className="inline-flex h-12 w-12 sm:h-16 sm:w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
            <Package className="h-6 w-6 sm:h-8 sm:w-8 text-zinc-600" />
          </div>
          <h3 className="text-sm sm:text-base font-semibold text-white">Nenhum produto ainda</h3>
          <p className="text-xs sm:text-sm text-zinc-500 mt-1 max-w-xs mx-auto">
            Adicione seu primeiro produto. O sistema gerará variações únicas automaticamente.
          </p>
          <button onClick={() => setShowForm(true)} className="btn-accent mt-5 mx-auto w-full sm:w-auto">
            <Plus className="h-4 w-4" />
            Adicionar primeiro produto
          </button>
        </div>
      ) : (
        /* The requested changes require a mobile layout for cards / table. 
           The original was a responsive grid of card elements. Let's make it fully mobile-optimized,
           supporting smaller image placeholders and inline category badges, adhering to instructions. */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p, i) => (
            <div key={p.id} className="premium-card p-4 sm:p-5 slide-in" style={{ animationDelay: `${i * 50}ms` }}>
              <div className="flex items-start justify-between mb-3 gap-2">
                <div className="flex items-center gap-2">
                  <span className="status-badge idle inline-flex items-center text-[10px] sm:text-xs">
                    <Tag className="h-3 w-3 mr-1" />
                    {CATEGORIES.find(c => c.value === p.category)?.label || p.category}
                  </span>
                </div>
                <button onClick={() => handleDelete(p.id)} className="text-zinc-700 hover:text-red-400 transition p-1">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="flex gap-3 mb-3">
                {/* Visual placeholder representing the Product image responsive size */}
                <div className="h-12 w-12 sm:h-16 sm:w-16 flex-shrink-0 bg-zinc-800/50 rounded-xl flex items-center justify-center border border-zinc-800">
                  <Package className="h-6 w-6 sm:h-8 sm:w-8 text-zinc-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-white text-xs sm:text-sm mb-1 line-clamp-2">{p.title}</h3>
                  <p className="text-xs text-zinc-500 line-clamp-2">{p.description}</p>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-zinc-800/60 pt-3">
                <div>
                  <p className="text-base sm:text-lg font-bold text-white">R$ {p.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p>
                  {p.min_price && p.min_price > 0 && (
                    <p className="text-[10px] text-zinc-600">Mín: R$ {p.min_price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-zinc-600">{p.brand || '—'}</p>
                  <p className="text-[10px] text-zinc-700">{p.condition}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setShowForm(false)}>
          <div className="w-full sm:max-w-lg h-full sm:h-auto rounded-none sm:rounded-2xl premium-card p-6 overflow-y-auto fade-in flex flex-col justify-between sm:justify-start" onClick={e => e.stopPropagation()}>
            <div>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-base sm:text-lg font-semibold text-white">Novo Produto</h2>
                <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white p-1">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Título do anúncio</label>
                  <input className="premium-input w-full" required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="iPhone 15 Pro Max 256GB" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Descrição</label>
                  <textarea className="premium-input w-full min-h-[80px] resize-none" required value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Descreva o produto em detalhes..." />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-zinc-400">Preço (R$)</label>
                    <input type="number" step="0.01" className="premium-input w-full" required value={form.price || ''} onChange={e => setForm({ ...form, price: parseFloat(e.target.value) })} placeholder="8999.90" />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-zinc-400">Preço mínimo (R$)</label>
                    <input type="number" step="0.01" className="premium-input w-full" value={form.min_price || ''} onChange={e => setForm({ ...form, min_price: parseFloat(e.target.value) })} placeholder="8500" />
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Categoria</label>
                  <select className="premium-input w-full" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                    {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-zinc-400">Marca</label>
                    <input className="premium-input w-full" value={form.brand || ''} onChange={e => setForm({ ...form, brand: e.target.value })} placeholder="Apple" />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-zinc-400">Modelo</label>
                    <input className="premium-input w-full" value={form.model || ''} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="iPhone 15 Pro Max" />
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Condição</label>
                  <select className="premium-input w-full" value={form.condition} onChange={e => setForm({ ...form, condition: e.target.value })}>
                    {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
                <div className="flex gap-3 pt-4 border-t border-zinc-800/40">
                  <button type="button" onClick={() => setShowForm(false)} className="btn-ghost flex-1 justify-center py-3 sm:py-2">Cancelar</button>
                  <button type="submit" className="btn-accent flex-1 justify-center py-3 sm:py-2">
                    <Plus className="h-4 w-4" />
                    Adicionar
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function CatalogSkeleton() {
  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div className="flex flex-col sm:flex-row justify-between gap-4">
        <div><div className="skeleton h-8 w-40" /><div className="skeleton h-4 w-32 mt-2" /></div>
        <div className="skeleton h-10 w-40 rounded-xl" />
      </div>
      <div className="skeleton h-12 rounded-xl w-full sm:max-w-xs" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}
      </div>
    </div>
  )
}
