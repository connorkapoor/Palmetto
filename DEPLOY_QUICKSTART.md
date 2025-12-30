# Quick Deployment Guide

Deploy Palmetto in 10 minutes.

## 1. Deploy Backend (Railway)

```bash
# Railway will auto-detect Dockerfile
1. Go to https://railway.app
2. New Project → Deploy from GitHub → Select Palmetto
3. Wait 15-20 minutes for build
4. Copy your Railway URL: https://palmetto-xxx.railway.app
```

**Add environment variable:**
```
CORS_ORIGINS=*  # Temporarily allow all (update after Vercel deploy)
```

## 2. Update Frontend Config

Edit `frontend/vercel.json`:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-RAILWAY-URL.railway.app/api/:path*"
    }
  ]
}
```

Commit and push:
```bash
git add frontend/vercel.json
git commit -m "Update backend URL"
git push origin main
```

## 3. Deploy Frontend (Vercel)

```bash
1. Go to https://vercel.com
2. New Project → Import from GitHub → Palmetto
3. Root Directory: frontend
4. Deploy
5. Copy your Vercel URL: https://palmetto-xxx.vercel.app
```

## 4. Update CORS

Go back to Railway:
```
CORS_ORIGINS=https://your-vercel-url.vercel.app
```

Railway auto-redeploys.

## 5. Test

Visit your Vercel URL and upload a STEP file!

---

## Troubleshooting

**Backend won't start:**
- Check Railway logs for build errors
- Build takes 15-20 minutes (compiling OpenCASCADE)

**Frontend can't connect:**
- Check vercel.json has correct Railway URL
- Update CORS_ORIGINS in Railway

**Upload fails:**
- Railway free tier: 512MB memory
- Try smaller files first (<10MB)

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.
