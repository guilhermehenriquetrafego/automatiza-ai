#!/bin/bash
# ============================================================
# AUTOMATIZA AI — Setup & Deploy Script
# ============================================================
# Este script te guia pelo processo de setup de cada serviço.
# Roda interativamente — te pergunta as credenciais e configura tudo.
# ============================================================

set -e

PROJECT_NAME="automatiza-ai"
echo "🚀 AUTOMATIZA AI — Setup & Deploy"
echo ""

# ============================================================
# 1. SUPABASE — Banco de Dados (PostgreSQL)
# ============================================================
setup_supabase() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "1/5  SUPABASE — PostgreSQL (Free: 500MB)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Passos:"
  echo "  1. Acesse https://supabase.com e crie conta"
  echo "  2. New Project → escolha um nome e região (South America - São Paulo)"
  echo "  3. Aguarde provisionamento (~2 min)"
  echo "  4. Settings → Database → Connection string"
  echo "  5. Copie a URI no formato:"
  echo "     postgresql+asyncpg://postgres:[SUA_SENHA]@db.[PROJETO].supabase.co:5432/postgres"
  echo ""
  echo "⚠️  Troque 'postgresql://' por 'postgresql+asyncpg://' no início"
  echo ""
  read -p "Cole a connection string aqui: " SUPABASE_URL
  echo ""
}

# ============================================================
# 2. UPSTASH — Redis (Filas Celery)
# ============================================================
setup_upstash() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "2/5  UPSTASH — Redis (Free: 10K cmds/dia)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Passos:"
  echo "  1. Acesse https://upstash.com e crie conta (pode usar GitHub/Google)"
  echo "  2. Create Database → nome: automatiza-redis"
  echo "  3. Region: us-east-1 (ou a mais próxima)"
  echo "  4. Após criar, copie a 'Endpoint URL' e a senha"
  echo ""
  echo "  A URL será algo como:"
  echo "  rediss://default:[SUA_SENHA]@us1-[SEU-HOST].upstash.io:6379"
  echo ""
  echo "⚠️  Use 'rediss://' (com SSL) não 'redis://'"
  echo ""
  read -p "Cole a Redis URL aqui: " UPSTASH_URL
  echo ""
}

# ============================================================
# 3. CLOUDFLARE R2 — Storage de Imagens
# ============================================================
setup_r2() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "3/5  CLOUDFLARE R2 — Storage (Free: 10GB)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Passos:"
  echo "  1. Acesse https://dash.cloudflare.com → R2 Object Storage"
  echo "  2. Create Bucket → nome: automatiza-ai"
  echo "  3. Settings → Public access → habilite o domínio público (r2.dev)"
  echo "  4. R2 → Manage R2 API Tokens → Create API Token"
  echo "  5. Permissões: Object Read & Write, no bucket automatiza-ai"
  echo "  6. Copie: Account ID, Access Key ID, Secret Access Key"
  echo ""
  read -p "Account ID: " R2_ACCOUNT_ID
  read -p "Access Key ID: " R2_ACCESS_KEY
  read -p "Secret Access Key: " R2_SECRET_KEY
  read -p "Public URL (r2.dev): " R2_PUBLIC_URL
  echo ""
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
  echo "Endpoint gerado: $R2_ENDPOINT"
  echo ""
}

# ============================================================
# 4. OPENAI — IA (GPT-4o + gpt-image-2)
# ============================================================
setup_openai() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "4/5  OPENAI — GPT-4o + gpt-image-2"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Passos:"
  echo "  1. Acesse https://platform.openai.com"
  echo "  2. API Keys → Create new secret key"
  echo "  3. Adicione créditos (mínimo $10 para começar)"
  echo ""
  echo "  ⚠️  GPT-4o custa ~$2.50/1M tokens input, $10/1M output"
  echo "  ⚠️  gpt-image-2 custa ~$0.04 por imagem gerada"
  echo ""
  read -p "Cole sua OpenAI API Key: " OPENAI_KEY
  echo ""
}

# ============================================================
# 5. RENDER — Backend + Celery Workers
# ============================================================
setup_render() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "5/5  RENDER — Backend API + Workers"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Render free tier: 750h/mês (suficiente para 1 web service + 1 worker)"
  echo ""
  echo "Você vai criar 3 serviços no Render:"
  echo ""
  echo "━━━ SERVIÇO 1: API (Web Service) ━━━"
  echo "  1. https://render.com → New → Web Service"
  echo "  2. Conecte seu repositório Git"
  echo "  3. Root Directory: backend"
  echo "  4. Build Command: pip install -r requirements.txt"
  echo "  5. Start Command: uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
  echo "  6. Plan: Free"
  echo ""
  echo "━━━ SERVIÇO 2: Celery Worker (Background Worker) ━━━"
  echo "  1. New → Background Worker"
  echo "  2. Mesmo repo, Root: backend"
  echo "  3. Start Command: celery -A app.tasks worker --loglevel=info --concurrency=2"
  echo "  4. Plan: Free"
  echo ""
  echo "━━━ SERVIÇO 3: Celery Beat (Scheduler) ━━━"
  echo "  1. New → Background Worker"
  echo "  2. Mesmo repo, Root: backend"
  echo "  3. Start Command: celery -A app.tasks beat --loglevel=info"
  echo "  4. Plan: Free"
  echo ""
  echo "Em TODOS os serviços, adicione Environment Variables:"
  echo "  DATABASE_URL, REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND,"
  echo "  OPENAI_API_KEY, R2_*, SECRET_KEY"
  echo ""
}

# ============================================================
# 6. VERCEL — Frontend
# ============================================================
setup_vercel() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "BÔNUS: VERCEL — Frontend"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Passos:"
  echo "  1. https://vercel.com → New Project"
  echo "  2. Importe o mesmo repositório"
  echo "  3. Root Directory: frontend"
  echo "  4. Framework Preset: Next.js"
  echo "  5. Add Environment Variable:"
  echo "     NEXT_PUBLIC_API_URL=https://[seu-backend].onrender.com/api/v1"
  echo "  6. Deploy!"
  echo ""
}

# ============================================================
# GERAR .env
# ============================================================
generate_env() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Gerando arquivo .env..."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  
  ENV_FILE="backend/.env"
  
  cat > "$ENV_FILE" << EOF
# AUTOMATIZA AI — Environment Variables
# Generated by setup script

ENVIRONMENT=production

# Supabase
DATABASE_URL=${SUPABASE_URL}

# Upstash Redis (use a mesma URL for all 3, ou crie 3 DBs separadas)
REDIS_URL=${UPSTASH_URL}
CELERY_BROKER_URL=${UPSTASH_URL}
CELERY_RESULT_BACKEND=${UPSTASH_URL}

# OpenAI
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_TEXT_MODEL=gpt-4o
OPENAI_IMAGE_MODEL=gpt-image-2

# Cloudflare R2
R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
R2_ACCESS_KEY_ID=${R2_ACCESS_KEY}
R2_SECRET_ACCESS_KEY=${R2_SECRET_KEY}
R2_BUCKET_NAME=automatiza-ai
R2_ENDPOINT_URL=${R2_ENDPOINT}
R2_PUBLIC_URL=${R2_PUBLIC_URL}

# Security
SECRET_KEY=$(openssl rand -hex 32)

# CDP
CDP_HEADLESS=true
EOF

  echo "✅ Arquivo $ENV_FILE gerado!"
  echo ""
  echo "⚠️  NÃO faça commit deste arquivo (já está no .gitignore)"
  echo ""
}

# ============================================================
# EXECUTAR
# ============================================================
setup_supabase
setup_upstash
setup_r2
setup_openai
setup_render
setup_vercel
generate_env

echo ""
echo "🎉 Setup completo!"
echo ""
echo "Resumo do que você precisa fazer agora:"
echo "  1. Suba o código para um repositório Git (GitHub/GitLab)"
echo "  2. No Render: crie 3 serviços (API, Worker, Beat) e adicione as env vars"
echo "  3. Na Vercel: importe o repo e configure NEXT_PUBLIC_API_URL"
echo "  4. Teste: acesse https://[seu-app].vercel.app"
echo ""
