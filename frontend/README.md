# Graph Intelligence

Graph Intelligence is a React/Vite analyst workspace for exploring a relationship graph and its surrounding investigation data.

## Install

From the workspace root:

```bash
pnpm install
```

## Environment

- `VITE_API_BASE_URL` (optional): absolute or relative base URL for the FastAPI service. When empty, the app uses relative `/api` requests through the workspace proxy.

## Development

```bash
pnpm --filter @workspace/graph-intelligence run dev
```

The managed preview workflow supplies the port and base path automatically.

## Production build

```bash
pnpm --filter @workspace/graph-intelligence run build
pnpm --filter @workspace/graph-intelligence run serve
```

## Expected API endpoints

The frontend centralizes requests around:

- `GET /api/healthz`
- `GET /api/graph/overview`
- `GET /api/graph/network?center=&depth=`
- `GET /api/graph/search?q=`
- `GET /api/graph/path?from=&to=`
- `GET /api/graph/analytics/centrality`
- `GET /api/graph/communities`
- `GET /api/graph/timeline`

Responses are normalized in the frontend data-access layer so minor backend response-shape differences do not leak into page components. If an endpoint is unavailable, the UI reports that state rather than silently substituting investigation data.

## Project structure

- `src/api/` — centralized API client, response normalization, and query hooks
- `src/components/` — shared shell, panels, graph, tables, and status UI
- `src/pages/` — routed dashboard and analysis workspaces
- `src/lib/` — formatters and display constants
- `src/index.css` — application theme and global styles
