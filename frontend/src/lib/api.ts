/** API client for AUTOMATIZA AI backend */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://automatiza-ai-api.onrender.com/api/v1'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('token')
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    redirect: 'follow',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Helper for collection endpoints that need trailing slash
async function fetchCollection<T>(path: string, options?: RequestInit): Promise<T> {
  return fetchAPI<T>(path.endsWith('/') ? path : path + '/', options)
}

export const api = {
  // Dashboard
  getOverview: () => fetchAPI<Overview>('/dashboard/overview'),
  getPerformance: () => fetchAPI<Performance>('/dashboard/performance'),
  getCalendar: () => fetchAPI<CalendarEntry[]>('/dashboard/exposure-calendar'),

  // Products
  getProducts: () => fetchCollection<Product[]>('/products'),
  createProduct: (data: CreateProductReq) =>
    fetchCollection<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),
  deleteProduct: (id: string) => fetchAPI(`/products/${id}`, { method: 'DELETE' }),

  // Accounts
  getAccounts: () => fetchCollection<OlxAccount[]>('/accounts'),
  addAccount: (data: { email: string; password: string }) =>
    fetchCollection<OlxAccount>('/accounts', { method: 'POST', body: JSON.stringify(data) }),

  // Publications
  getPublications: () => fetchCollection<Publication[]>('/publications'),
  recalculate: () => fetchAPI('/publications/recalculate', { method: 'POST' }),

  // Chat
  getChatMessages: () => fetchAPI<ChatMessage[]>('/chat/messages'),
  resolveMessage: (id: string) => fetchAPI(`/chat/${id}/resolve`, { method: 'PUT' }),

  // CDP Live
  getCdpSessions: () => fetchAPI<CdpSession[]>('/cdp-live/sessions'),
  getCdpActivity: () => fetchAPI<CdpActivity[]>('/cdp-live/activity'),
  getCdpSchedule: () => fetchAPI<ScheduledAction[]>('/cdp-live/schedule'),
  triggerCdpAction: (data: { account_id: string; action: string; password?: string }) =>
    fetchAPI<{ status: string; message: string }>('/cdp-live/trigger', { method: 'POST', body: JSON.stringify(data) }),

  // Auth
  login: (email: string, password: string) =>
    fetchAPI<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (data: { email: string; password: string; full_name: string }) =>
    fetchAPI<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  googleAuth: (credential: string) =>
    fetchAPI<AuthResponse>('/auth/google', { method: 'POST', body: JSON.stringify({ credential }) }),
}

// Types
export interface Overview {
  active_products: number
  max_products: number
  olx_accounts: number
  max_accounts: number
  total_remaining_ads: number
  publications: { online: number; scheduled: number; posting: number; failed: number }
  pending_chats: number
  plan: string
}

export interface Performance {
  by_hour: { hour: number; views: number; chats: number; clicks: number; favorites: number }[]
  by_weekday: { weekday: number; views: number; chats: number }[]
}

export interface CalendarEntry {
  scheduled_time: string
  product_title: string | null
  variation_title: string | null
  is_executed: boolean
  priority: number
}

export interface Product {
  id: string
  title: string
  description: string
  price: number
  min_price: number | null
  category: string
  subcategory: string | null
  brand: string | null
  model: string | null
  condition: string
  is_active: boolean
  image_count: number
}

export interface CreateProductReq {
  title: string
  description: string
  price: number
  min_price?: number
  category: string
  subcategory?: string
  brand?: string
  model?: string
  condition?: string
  specs?: Record<string, unknown>
}

export interface OlxAccount {
  id: string
  email: string
  account_type: string
  is_authenticated: boolean
  needs_reauth: boolean
  total_monthly_limit: number
  used_this_month: number
  remaining_this_month: number
  last_limit_sync: string | null
}

export interface Publication {
  id: string
  product_title: string | null
  variation_title: string | null
  status: string
  scheduled_for: string | null
  posted_at: string | null
  olx_ad_url: string | null
  error_message: string | null
}

export interface ChatMessage {
  id: string
  direction: string
  message_text: string
  buyer_name: string | null
  ai_generated: boolean
  status: string
  created_date: string
}

export interface AuthResponse {
  token: string
  user: { id: string; email: string; full_name: string; plan_tier: string; max_products?: number; max_olx_accounts?: number }
}

export interface CdpSession {
  id: string
  account_email: string
  status: string
  current_action: string
  started_at: string
  last_updated: string
  steps: { timestamp: string; action: string; status: string; message: string }[]
  olx_ad_url: string | null
}

export interface CdpActivity {
  timestamp: string
  session_id: string
  account_email: string
  action: string
  status: string
  message: string
}

export interface ScheduledAction {
  id: string
  scheduled_time: string
  account_email: string
  product_title: string
  action_type: string
  variation_title: string | null
}
