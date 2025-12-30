# Palmetto Deployment Guide

This guide walks you through deploying Palmetto to Vercel (frontend) and Railway (backend).

## Prerequisites

- GitHub account with Palmetto repository pushed
- Vercel account (free tier works)
- Railway account (free tier: $5 credit/month)
- Anthropic API key (optional, for natural language queries)

## Architecture Overview

```
Vercel (Frontend)          Railway (Backend)
┌─────────────────┐        ┌──────────────────────┐
│  React + Vite   │◄──────►│  FastAPI + C++ Engine│
│  Static hosting │  API   │  Docker container    │
└─────────────────┘        └──────────────────────┘
```

---

## Part 1: Deploy Backend to Railway

Railway will build the Docker container that includes both the C++ engine and Python backend.

### Step 1: Create Railway Project

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your **Palmetto** repository
5. Railway will detect the Dockerfile automatically

### Step 2: Configure Environment Variables

In the Railway dashboard:

1. Go to your project → **Variables** tab
2. Add these environment variables:

```
ANTHROPIC_API_KEY=sk-ant-xxxxx  # Optional: for NL queries
PORT=8000                         # Railway sets this automatically
CORS_ORIGINS=https://your-app.vercel.app  # Will update after Vercel deploy
```

### Step 3: Deploy

1. Railway will automatically start building the Docker image
2. **Build time: ~15-20 minutes** (compiling OpenCASCADE + C++ engine)
3. Monitor logs in the **Deployments** tab
4. Once deployed, Railway provides a public URL: `https://palmetto-production.up.railway.app`

### Step 4: Test Backend

```bash
# Check health
curl https://your-backend.railway.app/health

# Expected response:
{
  "status": "healthy",
  "engine": "C++ Analysis Situs",
  "engine_available": true,
  "modules_available": 5
}
```

### Step 5: Copy Backend URL

Copy your Railway backend URL (e.g., `https://palmetto-production-xxx.up.railway.app`)
You'll need this for the frontend deployment.

---

## Part 2: Deploy Frontend to Vercel

### Step 1: Update Vercel Configuration

Before deploying, update `frontend/vercel.json` with your Railway backend URL:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-RAILWAY-BACKEND.railway.app/api/:path*"
    }
  ]
}
```

Replace `YOUR-RAILWAY-BACKEND` with your actual Railway URL.

### Step 2: Deploy to Vercel

**Option A: Using Vercel Dashboard**

1. Go to https://vercel.com
2. Click **"Add New Project"**
3. Import your Palmetto repository from GitHub
4. Configure project:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Click **"Deploy"**

**Option B: Using Vercel CLI**

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy from frontend directory
cd frontend
vercel --prod
```

### Step 3: Test Frontend

1. Visit your Vercel URL: `https://your-app.vercel.app`
2. Try uploading a STEP file
3. Check browser console for any errors

---

## Part 3: Connect Frontend and Backend

### Update Backend CORS

Go back to Railway → Variables and update:

```
CORS_ORIGINS=https://your-app.vercel.app
```

Railway will automatically redeploy with the new CORS settings.

### Verify Connection

1. Open your Vercel app: `https://your-app.vercel.app`
2. Open browser DevTools → Network tab
3. Upload a STEP file
4. You should see API calls going to your Railway backend:
   - `POST /api/analyze/upload` → 200 OK
   - `POST /api/analyze/process` → 200 OK

---

## Troubleshooting

### Backend Issues

**"C++ engine not found"**
- Check Railway logs: Railway dashboard → Deployments → View logs
- Ensure Dockerfile build completed successfully
- Build should show: "Building palmetto_engine..."

**"Service Unavailable (503)"**
- Backend is starting up (can take 30-60 seconds after deploy)
- Check Railway logs for errors
- Ensure OpenCASCADE libraries are found: `LD_LIBRARY_PATH` is set

**"Health check failing"**
- Check Railway logs: `tail` command shows startup errors
- Verify port is 8000 or use Railway's `$PORT` variable

### Frontend Issues

**"API calls failing / CORS errors"**
- Update `CORS_ORIGINS` in Railway to match your Vercel domain
- Ensure `vercel.json` rewrites are pointing to correct Railway URL
- Clear browser cache and hard refresh

**"Failed to fetch"**
- Check Network tab: are requests going to Railway or localhost?
- Ensure vercel.json is in `frontend/` directory
- Verify Railway backend is accessible: `curl https://your-backend.railway.app/health`

### Upload Issues

**"File upload times out"**
- Railway free tier has 512MB memory, large files may fail
- Try smaller STEP files (<10MB) first
- Check Railway logs for memory errors

**"Analysis fails after upload"**
- Check Railway logs for C++ engine errors
- Ensure palmetto_engine has execute permissions
- Verify OpenCASCADE libraries are loaded

---

## Cost Estimates

### Railway (Backend)
- **Free tier**: $5 credit/month (~100 hours of usage)
- **Starter plan**: $5/month + usage (~$20-30/month typical)
- **Build time**: ~15 minutes (counts toward usage)
- **Runtime**: Billed per second when active

### Vercel (Frontend)
- **Hobby (Free)**: Unlimited bandwidth, 100GB-hours compute
- **Pro**: $20/month (if you need custom domain + more)

**Total cost for moderate usage**: $0-$5/month (free tiers)

---

## Production Checklist

Before going live:

- [ ] Set `ANTHROPIC_API_KEY` in Railway (for NL queries)
- [ ] Update `CORS_ORIGINS` in Railway to match Vercel domain
- [ ] Update `vercel.json` with Railway backend URL
- [ ] Test file upload end-to-end
- [ ] Test feature recognition works
- [ ] Test natural language queries
- [ ] Add custom domain to Vercel (optional)
- [ ] Set up monitoring/alerts in Railway

---

## Updating Deployments

### Backend Changes

```bash
git add .
git commit -m "Update backend"
git push origin main
```

Railway auto-deploys on push to main branch.

### Frontend Changes

```bash
git add .
git commit -m "Update frontend"
git push origin main
```

Vercel auto-deploys on push to main branch.

### Force Rebuild

**Railway**: Deployments tab → Three dots → Redeploy

**Vercel**: Deployments tab → Three dots → Redeploy

---

## Advanced Configuration

### Custom Domain

**Vercel:**
1. Project Settings → Domains
2. Add your domain
3. Configure DNS records as shown

**Railway:**
1. Project Settings → Domains
2. Generate Railway domain or add custom domain

### Environment-Specific Configs

Create `.env.production` in frontend:

```env
VITE_API_URL=https://your-backend.railway.app
```

### Scaling

**Railway:**
- Settings → Resources → Adjust memory/CPU
- Add horizontal replicas (Pro plan)

**Vercel:**
- Automatically scales with traffic
- No configuration needed

---

## Support

- **Railway Docs**: https://docs.railway.app
- **Vercel Docs**: https://vercel.com/docs
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: Report bugs in your Palmetto repository
