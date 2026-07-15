# AUTOMATIZA AI — Guia de Deploy

## Visão Geral — 6 Plataformas (todas free tier)

```
┌─────────────────────────────────────────────────────┐
│                    ARQUITETURA DE DEPLOY               │
├──────────┬──────────┬──────────┬──────────┬──────────┤
│ Frontend │ Backend  │ Workers  │ Banco    │ Storage  │
│ Vercel   │ Render   │ Render   │ Supabase │ Cloudflare│
│ (Next.js)│ (FastAPI)│ (Celery) │ (Postgres)│ (R2)    │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│ FREE     │ FREE     │ FREE     │ FREE     │ FREE     │
│ ∞        │ 750h/mês │ 750h/mês │ 500MB    │ 10GB     │
└──────────┴──────────┴──────────┴──────────┴──────────┘

         + OpenAI API (pago, ~$10 para começar)
         + Upstash Redis (free: 10K cmds/dia)
```

---

## 1. Supabase — Banco de Dados (PostgreSQL)

**Por quê?** PostgreSQL gerenciado com free tier de 500MB (suficiente para milhares de registros).

### Passo a passo:
1. Acesse https://supabase.com → crie conta
2. **New Project** → nome: `automatiza-ai` → região: **South America (São Paulo)**
3. Defina uma senha para o banco
4. Aguarde provisionamento (~2 min)
5. Vá em **Settings → Database → Connection string → URI**
6. Copie a URL e troque `postgresql://` por `postgresql+asyncpg://`

### URL final:
```
postgresql+asyncpg://postgres:[SUA_SENHA]@db.[PROJETO].supabase.co:5432/postgres
```

### Extensões necessárias (rode no SQL Editor do Supabase):
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 2. Upstash — Redis (Filas Celery)

**Por quê?** Redis serverless com free tier de 10K comandos/dia. Celery precisa de Redis para agendamento.

### Passo a passo:
1. Acesse https://upstash.com → crie conta (login com GitHub/Google)
2. **Create Database** → nome: `automatiza-redis` → região: `us-east-1`
3. Copie a **Endpoint URL**

### URL final:
```
rediss://default:[SUA_SENHA]@us1-[HOST].upstash.io:6379
```

⚠️ Use `rediss://` (com SSL) — a Upstash exige TLS.

### Usar a mesma URL para:
- `REDIS_URL` — cache geral
- `CELERY_BROKER_URL` — fila de mensagens
- `CELERY_RESULT_BACKEND` — resultados

---

## 3. Cloudflare R2 — Storage de Imagens

**Por quê?** 10GB grátis + egress gratuito (S3 cobra egress, R2 não). Armazena fotos de produtos e imagens geradas pela IA.

### Passo a passo:
1. Acesse https://dash.cloudflare.com → **R2 Object Storage**
2. **Create Bucket** → nome: `automatiza-ai`
3. Vá em **Settings** do bucket → **Public Access** → habilite o domínio `r2.dev`
4. Copie a **Public URL** (algo como `https://pub-[HASH].r2.dev`)
5. **R2 → Manage R2 API Tokens → Create API Token**
   - Permissões: **Object Read & Write**
   - Bucket: `automatiza-ai`
6. Copie: **Account ID**, **Access Key ID**, **Secret Access Key**

### Endpoint:
```
https://[ACCOUNT_ID].r2.cloudflarestorage.com
```

---

## 4. OpenAI — IA (GPT-4o + gpt-image-2)

**Por quê?** Melhor modelo de texto (GPT-4o) e imagem (gpt-image-2) disponíveis.

### Passo a passo:
1. Acesse https://platform.openai.com
2. **API Keys → Create new secret key** → copie a key
3. **Billing → Add payment method** e adicione créditos (mínimo $10)

### Custos estimados:
| Operação | Custo | Por variação |
|---|---|---|
| GPT-4o (título + descrição) | ~$0.003 | ~R$0,015 |
| gpt-image-2 (1 imagem) | ~$0.04 | ~R$0,20 |
| Chat IA (por mensagem) | ~$0.001 | ~R$0,005 |

**Custo por produto (8 variações):** ~$0.34 (~R$1,70)
**Custo mensal para 30 produtos:** ~$10/mês (~R$50)

---

## 5. Render — Backend (API + Workers)

**Por quê?** Free tier com 750h/mês. Roda Docker nativamente (precisamos do Chrome para CDP).

### ⚠️ Limitação do Free Tier:
- Serviços free "sleep" após 15 min de inatividade
- Primeira request depois de sleep demora ~30s pra responder (cold start)
- Para produção real, considere o plano **Starter** ($7/mês) que não dorme

### Criar 3 serviços:

#### SERVIÇO 1: API (Web Service)
```
Type:          Web Service
Root:          backend
Build:         pip install -r requirements.txt
Start:         uvicorn app.main:app --host 0.0.0.0 --port $PORT
Plan:          Free
```

#### SERVIÇO 2: Celery Worker (Background Worker)
```
Type:          Background Worker
Root:          backend
Build:         pip install -r requirements.txt
Start:         celery -A app.tasks worker --loglevel=info --concurrency=2
Plan:          Free
```

#### SERVIÇO 3: Celery Beat (Scheduler)
```
Type:          Background Worker
Root:          backend
Build:         pip install -r requirements.txt
Start:         celery -A app.tasks beat --loglevel=info
Plan:          Free
```

### Environment Variables (em TODOS os 3 serviços):
```
DATABASE_URL=postgresql+asyncpg://postgres:[SENHA]@db.[PROJETO].supabase.co:5432/postgres
REDIS_URL=rediss://default:[SENHA]@[HOST].upstash.io:6379
CELERY_BROKER_URL=rediss://default:[SENHA]@[HOST].upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:[SENHA]@[HOST].upstash.io:6379
OPENAI_API_KEY=sk-...
OPENAI_TEXT_MODEL=gpt-4o
OPENAI_IMAGE_MODEL=gpt-image-2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=automatiza-ai
R2_ENDPOINT_URL=https://[ID].r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-[HASH].r2.dev
SECRET_KEY=[gerar com: openssl rand -hex 32]
CDP_HEADLESS=true
ENVIRONMENT=production
```

---

## 6. Vercel — Frontend

**Por quê?** Free tier ilimitado para Next.js. Deploy automático via Git.

### Passo a passo:
1. Acesse https://vercel.com → **New Project**
2. Importe o mesmo repositório
3. **Root Directory:** `frontend`
4. **Framework Preset:** Next.js
5. **Environment Variables:**
   ```
   NEXT_PUBLIC_API_URL=https://[seu-backend].onrender.com/api/v1
   ```
6. **Deploy!**

---

## Resumo de Custos

| Serviço | Free Tier | Pago (quando crescer) |
|---|---|---|
| Supabase | 500MB, 50 conexões | $25/mês (8GB) |
| Upstash | 10K cmds/dia | $10/mês (unlimited) |
| Cloudflare R2 | 10GB | $0.015/GB/mês |
| Render (3 serviços) | 750h/mês | $21/mês (3× Starter) |
| Vercel | Ilimitado | $20/mês (Pro) |
| OpenAI | Pago desde início | ~$10-30/mês |
| **Total início** | **~$10/mês** | **~$86/mês** |

---

## Checklist de Deploy

- [ ] 1. Criar conta no Supabase + copiar DATABASE_URL
- [ ] 2. Rodar SQL: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- [ ] 3. Criar conta no Upstash + copiar Redis URL
- [ ] 4. Criar bucket no Cloudflare R2 + gerar API token
- [ ] 5. Criar API key na OpenAI + adicionar $10 créditos
- [ ] 6. Subir código para GitHub/GitLab
- [ ] 7. Render: criar API (Web Service) + adicionar env vars
- [ ] 8. Render: criar Celery Worker + mesmas env vars
- [ ] 9. Render: criar Celery Beat + mesmas env vars
- [ ] 10. Vercel: importar repo, apontar para /frontend, add NEXT_PUBLIC_API_URL
- [ ] 11. Testar: `curl https://[api].onrender.com/health` → {"status":"healthy"}
- [ ] 12. Testar: abrir frontend na Vercel, criar conta, cadastrar produto
