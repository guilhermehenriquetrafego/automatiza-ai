'use client'

import { useEffect, useState } from 'react'
import { api, type Product } from '@/lib/api'
import { Plus, Trash2, Package } from 'lucide-react'
import { toast } from 'sonner'

const CATEGORIES = [
  { value: 'celulares_telefonia', label: 'Celulares e Telefonia' },
  { value: 'informatica', label: 'Informática' },
  { value: 'games', label: 'Games' },
  { value: 'audio', label: 'Áudio' },
  { value: 'tvs_e_video', label: 'TVs e Vídeo' },
  { value: 'cameras_e_drones', label: 'Câmeras e Drones' },
]

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  CATEGORIES.map(c => [c.value, c.label])
)

export default function ProdutosPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  // Form state
  const [form, setForm] = useState({
    title: '', description: '', price: '', min_price: '',
    category: 'celulares_telefonia', brand: '', model: '', condition: 'novo',
  })

  useEffect(() => {
    loadProducts()
  }, [])

  const loadProducts = async () => {
    try {
      const data = await api.getProducts()
      setProducts(data)
    } catch { toast.error('Erro ao carregar produtos') }
    finally { setLoading(false) }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createProduct({
        title: form.title, description: form.description,
        price: parseFloat(form.price),
        min_price: form.min_price ? parseFloat(form.min_price) : undefined,
        category: form.category, brand: form.brand || undefined,
        model: form.model || undefined, condition: form.condition,
      })
      toast.success('Produto criado! Gerando variações com IA...')
      setShowForm(false)
      setForm({ title: '', description: '', price: '', min_price: '', category: 'celulares_telefonia', brand: '', model: '', condition: 'novo' })
      loadProducts()
    } catch { toast.error('Erro ao criar produto') }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Desativar este produto?')) return
    try {
      await api.deleteProduct(id)
      toast.success('Produto desativado')
      loadProducts()
    } catch { toast.error('Erro ao desativar') }
  }

  if (loading) return <div className="animate-pulse text-slate-400">Carregando...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {products.length} produto(s) cadastrado(s)
          </p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="h-4 w-4" />
          Novo Produto
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="card space-y-4">
          <h2 className="text-lg font-semibold">Novo Produto</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Título</label>
              <input className="input" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required placeholder="iPhone 15 Pro Max 256GB" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Preço (R$)</label>
              <input className="input" type="number" step="0.01" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} required placeholder="4999" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Preço Mínimo (R$)</label>
              <input className="input" type="number" step="0.01" value={form.min_price} onChange={e => setForm({ ...form, min_price: e.target.value })} placeholder="4500" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Categoria</label>
              <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Marca</label>
              <input className="input" value={form.brand} onChange={e => setForm({ ...form, brand: e.target.value })} placeholder="Apple" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Modelo</label>
              <input className="input" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="iPhone 15 Pro Max" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Descrição</label>
            <textarea className="input min-h-[100px]" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required placeholder="Descrição do produto..." />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary">Criar e Gerar Variações</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      )}

      {/* Product list */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products.map(p => (
          <div key={p.id} className="card group">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="mb-2 flex items-center gap-2">
                  <span className="badge badge-blue">{CATEGORY_LABELS[p.category] || p.category}</span>
                  <span className="badge badge-gray capitalize">{p.condition}</span>
                </div>
                <h3 className="font-semibold text-sm">{p.title}</h3>
                <p className="mt-1 text-xs line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                  {p.description}
                </p>
                <div className="mt-3 flex items-center justify-between">
                  <p className="text-lg font-bold text-brand-600">
                    R$ {p.price.toFixed(2)}
                  </p>
                  <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    <Package className="h-3.5 w-3.5" />
                    {p.image_count} img
                  </div>
                </div>
              </div>
              <button onClick={() => handleDelete(p.id)} className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg">
                <Trash2 className="h-4 w-4 text-red-500" />
              </button>
            </div>
          </div>
        ))}
        {products.length === 0 && (
          <div className="col-span-full card text-center py-12">
            <Package className="mx-auto h-12 w-12 mb-4 opacity-30" />
            <p style={{ color: 'var(--text-secondary)' }}>Nenhum produto cadastrado ainda.</p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              Clique em "Novo Produto" para começar.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
