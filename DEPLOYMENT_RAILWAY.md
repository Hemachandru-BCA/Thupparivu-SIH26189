# Railway Deployment Guide

## Overview

This project is now deployed on Railway with:
- **Frontend**: Vite + React on Railway (static site)
- **Backend**: FastAPI + Python on Railway

## Frontend Deployment

### Step 1: Update Environment Variable
In Railway, set the environment variable:
```
VITE_API_BASE_URL=https://enthusiastic-creativity-production-27af.up.railway.app
```

### Step 2: Deploy to Railway
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. New Project → Import GitHub Repo
3. Select your repository
4. Railway will auto-detect the frontend build configuration
5. Set environment variable `VITE_API_BASE_URL`
6. Deploy

### Build Configuration
Railway automatically uses `nixpacks.toml` for build configuration:
- Build command: `pnpm install && pnpm build`
- Output directory: `dist`

## Backend Deployment

### Step 1: Deploy Python Backend to Railway
1. Go to Railway Dashboard
2. New Project → Import GitHub Repo (same or separate repo)
3. Railway will auto-detect Python from `requirements.txt`
4. Set environment variables:
   - `CORS_ORIGINS` = your frontend Railway URL
   - Any other required variables from `.env.example`

### Step 2: Update CORS Settings
In Railway, set `CORS_ORIGINS` to include your frontend URL. The backend code
**always** merges the local dev origins and the GitHub Pages origins, so the
value below only needs your custom frontend URL:

```
CORS_ORIGINS=https://hemachandru-bca.github.io
```

> **Note:** `https://Hemachandru-BCA.github.io` and `https://hemachandru-bca.github.io`
> are always allowed regardless of `CORS_ORIGINS`, so the GitHub Pages frontend
> will work even if you never set this variable.

## Environment Variables

### Frontend (Railway)
| Variable | Value | Description |
|----------|-------|-------------|
| `VITE_API_BASE_URL` | `https://enthusiastic-creativity-production-27af.up.railway.app` | Your backend URL |

### Backend (Railway)
| Variable | Value | Description |
|----------|-------|-------------|
| `CORS_ORIGINS` | `https://hemachandru-bca.github.io` | Your frontend URL |
| `DATABASE_URL` | Your database URL | Optional |
| `SENTINELGRAPH_LOG_LEVEL` | `INFO` | Logging level |

## Benefits of Railway

1. **No CORS Issues**: Both frontend and backend on Railway have proper CORS handling
2. **Free Tier**: Generous free tier for small projects
3. **Python Support**: First-class Python support with nixpacks
4. **Automatic Deployments**: Git push → automatic deployment
5. **Environment Variables**: Easy environment variable management

## Troubleshooting

### CORS Errors
Make sure `CORS_ORIGINS` on backend includes your frontend URL.

### 404 Errors
Ensure the backend URL in `VITE_API_BASE_URL` matches your Railway backend deployment URL exactly.

### Build Failures
Ensure `pnpm` version in `package.json` matches the installed version.