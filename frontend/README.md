# frontend

SPA em React + TypeScript, construído com Vite. Usa **TanStack Router** para roteamento (com guards de autenticação via `beforeLoad`) e **TanStack Query** para chamadas à API e mutations.

Em produção, o build (`dist/`) é servido pelo próprio FastAPI — ver `src/presentation/api/app.py`. Em desenvolvimento, o Vite roda em `:5173` e faz proxy das rotas da API para o backend em `:8000` (configurado em `vite.config.ts`).

```
frontend/
├── index.html
├── vite.config.ts      → proxy de API em dev, alias @ → src/
└── src/
    ├── api/            → client HTTP, tipos espelhando os DTOs do backend, endpoints
    ├── auth/            → AuthContext (token + usuário em localStorage)
    ├── components/      → Toast, AgentStepsPanel
    ├── hooks/            → useJobStream (SSE de jobs assíncronos)
    ├── pages/            → telas (Login, AppLayout, Drug/Interactions/Prescription)
    ├── styles/global.css → portado do protótipo estático original
    ├── router.tsx        → árvore de rotas TanStack Router (code-based)
    ├── App.tsx           → injeta o AuthContext no contexto do router
    └── main.tsx          → providers (QueryClient, Toast, Auth) + render
```

## Rodando

```bash
npm install
npm run dev      # http://localhost:5173, proxy para o backend em :8000
npm run build    # gera frontend/dist, servido pelo FastAPI
```

Defina `VITE_API_PROXY_TARGET` se o backend não estiver em `http://localhost:8000`.

## api/

| Arquivo | Conteúdo |
|---|---|
| `types.ts` | Tipos TS espelhando `src/application/use_cases/dtos.py` e `src/domain/entities/*.py` |
| `client.ts` | `apiFetch` — injeta `Authorization: Bearer <token>`, trata 401 (dispara logout) |
| `endpoints.ts` | Funções tipadas por domínio (`authApi`, `analysisApi`, `jobsApi`) |

## Sync vs. async

`/interactions` e `/prescription-review` respondem de duas formas dependendo do volume (mesma regra do backend, ver `src/README.md`):

- **Resultado direto** (≤3 itens) — a mutation resolve com o resultado.
- **202 + `job_id`** (>3 itens) — `isJobEnqueueResponse()` detecta o formato e `useJobStream` assume o acompanhamento via SSE (`/jobs/{id}/events`) até `status: completed`, buscando o resultado final em `/jobs/{id}/result`.

`EventSource` nativo não permite enviar o header `Authorization`, então `useJobStream` usa `fetch` com `ReadableStream` para ler o stream SSE manualmente.

## auth/AuthContext

Guarda `token` e `user` em `localStorage` (`pharma_token`, `pharma_user`). `setUnauthorizedHandler` (em `api/client.ts`) é conectado ao `logout()` do contexto, então qualquer 401 da API desloga o usuário automaticamente.

## router.tsx

Rotas definidas via API code-based do TanStack Router (sem plugin de file-based routing):

- `/login` — bloqueada para quem já está autenticado (`beforeLoad` redireciona para `/drug`)
- rota-shell `app-shell` — exige autenticação (`beforeLoad` redireciona para `/login`), renderiza `AppLayout`
  - `/drug`, `/interactions`, `/prescription` — filhas do shell

O contexto do router (`RouterContext.auth`) é injetado em `App.tsx` a partir do `AuthContext`, permitindo que os guards leiam o estado de autenticação atual.

## pages/AppLayout

Topbar com navegação entre as 3 análises + painel direito fixo com os `agent_steps` retornados pelo backend. O estado dos steps é compartilhado com as páginas filhas via `useAgentSteps()` (contexto React local ao layout, não global).
