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
    <div className="space-y-6 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Catálogo</h1>
          <p className="text-sm text-zinc-500 mt-1">{products.length} produto(s) cadastrado(s)</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-accent">
          <Plus className="h-4 w-4" />
          Adicionar Produto
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-600" />
        <input
          className="premium-input pl-12"
          placeholder="Buscar por título ou marca..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Products grid */}
      {filtered.length === 0 ? (
        <div className="premium-card p-12 text-center">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-800/50 mb-4">
            <Package className="h-8 w-8 text-zinc-600" />
          </div>
          <h3 className="text-base font-semibold text-white">Nenhum produto ainda</h3>
          <p className="text-sm text-zinc-500 mt-1 max-w-xs mx-auto">
            Adicione seu primeiro produto. O sistema gerará variações únicas automaticamente.
          </p>
          <button onClick={() => setShowForm(true)} className="btn-accent mt-5 mx-auto">
            <Plus className="h-4 w-4" />
            Adicionar primeiro produto
          </button>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p, i) => (
            <div key={p.id} className="premium-card p-5 slide-in" style={{ animationDelay: `${i * 50}ms` }}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="status-badge idle">
                    <Tag className="h-3 w-3" />
                    {CATEGORIES.find(c => c.value === p.category)?.label || p.category}
                  </span>
                </div>
                <button onClick={() => handleDelete(p.id)} className="text-zinc-700 hover:text-red-400 transition">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <h3 className="font-semibold text-white text-sm mb-1 line-clamp-2">{p.title}</h3>
              <p className="text-xs text-zinc-500 line-clamp-2 mb-3">{p.description}</p>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-bold text-white">R$ {p.price.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p>
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
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setShowForm(false)}>
          <div className="w-full max-w-lg premium-card p-6 max-h-[90vh] overflow-y-auto fade-in" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-white">Novo Produto</h2>
              <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Título do anúncio</label>
                <input className="premium-input" required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="iPhone 15 Pro Max 256GB" />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Descrição</label>
                <textarea className="premium-input min-h-[80px] resize-none" required value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Descreva o produto em detalhes..." />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Preço (R$)</label>
                  <input type="number" step="0.01" className="premium-input" required value={form.price || ''} onChange={e => setForm({ ...form, price: parseFloat(e.target.value) })} placeholder="8999.90" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Preço mínimo (R$)</label>
                  <input type="number" step="0.01" className="premium-input" value={form.min_price || ''} onChange={e => setForm({ ...form, min_price: parseFloat(e.target.value) })} placeholder="8500" />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Categoria</label>
                <select className="premium-input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Marca</label>
                  <input className="premium-input" value={form.brand || ''} onChange={e => setForm({ ...form, brand: e.target.value })} placeholder="Apple" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-zinc-400">Modelo</label>
                  <input className="premium-input" value={form.model || ''} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="iPhone 15 Pro Max" />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-zinc-400">Condição</label>
                <select className="premium-input" value={form.condition} onChange={e => setForm({ ...form, condition: e.target.value })}>
                  {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="btn-ghost flex-1 justify-center">Cancelar</button>
                <button type="submit" className="btn-accent flex-1 justify-center">
                  <Plus className="h-4 w-4" />
                  Adicionar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function CatalogSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div><div className="skeleton h-8 w-40" /><div className="skeleton h-4 w-32 mt-2" /></div>
        <div className="skeleton h-10 w-40 rounded-xl" />
      </div>
      <div className="skeleton h-12 rounded-xl" />
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}
      </div>
    </div>
  )
}
