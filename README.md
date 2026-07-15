# AUTOMATIZA AI

Sistema de Gestão de Exposição de Anúncios OLX para eletrônicos.

## O que é

Não é um robô de postagem. É um **otimizador de exposição** que mantém os anúncios do vendedor sempre no topo da OLX, automaticamente, usando IA para gerar variações únicas e um motor inteligente que decide quando e onde publicar.

## Stack

| Componente | Tecnologia | Hospedagem (Free Tier) |
|---|---|---|
| Backend | Python + FastAPI | Render |
| Filas/Tasks | Celery + Redis | Upstash (Redis) + Render (Worker) |
| Banco | PostgreSQL | Supabase |
| Storage | Cloudflare R2 | Cloudflare (10GB free) |
| Frontend | Next.js + Tailwind | Vercel |
| IA Texto | GPT-4o | OpenAI API |
| IA Imagem | gpt-image-2 (ChatGPT Images 2.0) | OpenAI API |
| Automação | CDP direto (Chrome DevTools Protocol) | Render/Docker |

## Arquitetura

```
┌─────────────────────────────────────────────┐
│                Frontend (Next.js)             │
│          Dashboard dark/light mode            │
└──────────────────┬──────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────┐
│              Backend (FastAPI)                 │
│  - Auth  - Products  - Variations             │
│  - Publications  - Chat  - Dashboard          │
└──────┬──────────┬────────────┬───────────────┘
       │          │            │
┌──────▼──┐ ┌────▼─────┐ ┌────▼──────────┐
│ Celery  │ │ Motor de │ │ Automação CDP │
│ Worker  │ │ Exposição│ │ (Stealth)     │
│         │ │          │ │               │
│ - Sync  │ │ Calendar │ │ - Login OLX   │
│   limits│ │ calc     │ │ - Post ads    │
│ - Chats │ │          │ │ - Read chat   │
│ - Pub.  │ │          │ │ - Scrape perf│
└─────────┘ └──────────┘ └───────────────┘
       │          │            │
┌──────▼──────────▼───────────▼───────────────┐
│           PostgreSQL (Supabase)               │
│  Redis (Upstash)  -  R2 (Cloudflare)         │
└──────────────────────────────────────────────┘
```

## Módulos

### 1. Catálogo de Produtos
O usuário cadastra produtos com fotos, título, descrição, preço, categoria.

### 2. Motor de Variações (IA)
GPT-4o gera variações únicas de título e descrição com diferentes ângulos de SEO.
gpt-image-2 gera imagens únicas do produto (1 por variação).
PostgreSQL pg_trgm garante que nenhuma variação seja muito parecida.

### 3. Motor de Exposição
O coração do sistema. Calcula o calendário ótimo de publicação:
- Soma limites de todas as contas OLX
- Distribui ao longo do mês (esgotando o limite, ex: 250/250)
- Prioriza horários de pico (aprende com histórico)
- Recalibra diariamente e quando limites mudam

### 4. Chat IA
GPT-4o responde mensagens do chat da OLX automaticamente.
Escala para humano quando: negociação abaixo do mínimo, perguntas complexas.

### 5. Automação OLX (CDP)
100% via Chrome DevTools Protocol. Sem API oficial.
- Stealth: canvas noise, WebGL spoofing, mouse Bezier, delays log-normais
- Postagem de anúncios, sync de limites, leitura/escrita de chat
- Persistência de sessão (cookies/localStorage via CDP)

## Planos

| Plano | Preço | Produtos | Contas OLX |
|---|---|---|---|
| Starter | R$97/mês | 10 | 1 |
| Pro | R$197/mês | 30 | 2 |
| Business | R$397/mês | 80 | 5 |
| Enterprise | R$797/mês | 200 | Ilimitado |

## Categorias Suportadas
Celulares e Telefonia, Informática, Games, Áudio, TVs e vídeo, Câmeras e Drones (com subcategorias).

## Setup Local

```bash
# 1. Clone e instale dependências
cd backend
pip install -r requirements.txt

# 2. Configure ambiente
cp .env.example .env
# Edite .env com suas credenciais

# 3. Docker para PostgreSQL + Redis
docker-compose up -d postgres redis

# 4. Rode o backend
uvicorn app.main:app --reload

# 5. Em outro terminal, rode o Celery worker
celery -A app.tasks worker --loglevel=info

# 6. Em outro terminal, rode o Celery beat
celery -A app.tasks beat --loglevel=info
```

## Deploy (Free Tier)

| Serviço | Onde | Como |
|---|---|---|
| Frontend | Vercel | `vercel --prod` na pasta frontend |
| Backend API | Render | Conectar repo, build via Dockerfile |
| Celery Worker | Render | Mesmo Docker, comando diferente |
| Celery Beat | Render | Mesmo Docker, comando diferente |
| PostgreSQL | Supabase | Criar projeto, pegar connection string |
| Redis | Upstash | Criar DB, pegar URL |
| Storage | Cloudflare R2 | Criar bucket, pegar credenciais |
