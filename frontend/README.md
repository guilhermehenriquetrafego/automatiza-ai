# AUTOMATIZA AI Frontend

Dashboard Next.js com dark/light mode para o sistema de gestão de exposição de anúncios OLX.

## Páginas

- **/** — Dashboard (visão geral, stats, botão de recalcular exposição)
- **/produtos** — Catálogo (criar, listar, deletar produtos)
- **/exposicao** — Motor de Exposição (calendário visual, gráfico de performance por horário)
- **/chat** — Chat OLX (mensagens, IA vs humano, auto-refresh a cada 5s)
- **/config** — Configurações (contas OLX, autenticação via CDP)

## Stack

- Next.js 15 + React 19
- Tailwind CSS (dark/light mode)
- Recharts (gráficos)
- Lucide Icons
- Zustand (state)
- Sonner (notificações)

## Deploy (Vercel free tier)

```bash
npm install
npm run build
vercel --prod
```

## Desenvolvimento

```bash
npm install
npm run dev  # http://localhost:3000
```

Configure a URL da API no `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```
