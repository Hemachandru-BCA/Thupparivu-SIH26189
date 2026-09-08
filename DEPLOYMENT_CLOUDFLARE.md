# Cloudflare Pages Deployment Guide

## Frontend Setup (Cloudflare Pages)

### Step 1: Update Environment Variable
Update your `frontend/.env.production` with your backend URL:
```
VITE_API_BASE_URL=https://your-backend.onrender.com
```

### Step 2: Build and Deploy
```bash
cd frontend
pnpm build
```

### Step 3: Deploy to Cloudflare Pages
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Workers & Pages → Create → Pages
3. Connect to Git → Select your repository
4. Build configuration:
   - **Build command:** `pnpm build`
   - **Build output directory:** `dist`
5. Environment variables:
   - `VITE_API_BASE_URL` = your backend URL
6. Deploy

## Backend (Keep on Render)

Your Python backend (FastAPI + ML pipeline) should stay on Render:
- `render.yaml` has been removed
- Keep your existing Render deployment
- Update `CORS_ORIGINS` to include your Cloudflare Pages URL

## Environment Variables Needed

### Cloudflare Pages (Frontend)
| Variable | Value | Description |
|----------|-------|-------------|
| `VITE_API_BASE_URL` | `https://your-backend.onrender.com` | Your Render backend URL |

### Render (Backend)
| Variable | Value | Description |
|----------|-------|-------------|
| `CORS_ORIGINS` | `https://your-app.pages.dev` | Your Cloudflare Pages URL |

## Benefits of This Setup

1. **Cloudflare Pages**: Faster global CDN, automatic CORS handling, better performance than GitHub Pages
2. **Render**: Runs Python backend with ML dependencies (spaCy, networkx, etc.)
3. **Separation of concerns**: Frontend and backend can scale independently

## Troubleshooting

### CORS Errors
Make sure `CORS_ORIGINS` on Render includes your Cloudflare Pages URL.

### API 404 Errors
Verify `VITE_API_BASE_URL` points to the correct backend URL.

### Build Failures
Ensure `pnpm` is installed and version matches `package.json` (v10.15.0).
