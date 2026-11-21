# TenderBee Production Deployment Guide: Vercel & Render

This repository is pre-configured for full-stack production deployment:
- **Frontend (Next.js 16 App Router)**: Deployed on **Vercel**
- **Backend (Django 5 + DRF + WhiteNoise + Celery)**: Deployed on **Render**
- **Database**: External **Neon PostgreSQL** (or Render PostgreSQL)
- **Object Storage**: **Backblaze B2** (or AWS S3 / Cloudflare R2 / Server disk)

---

## Architecture at a Glance

```text
[ Browser / Client ]
         |
         v
[ Vercel: Next.js Frontend ] (https://tenderbee.vercel.app)
         |  (Same-origin API proxy: /api/backend/...)
         v
[ Render: Django Backend ] (https://tenderbee-backend.onrender.com)
     |                |                 |
     v                v                 v
[ Neon PostgreSQL ] [ Redis / Celery ] [ Backblaze B2 ]
```

---

## Part 1: Deploy Backend on Render

You can deploy the backend to Render using either **Option A (1-Click Blueprint - Recommended)** or **Option B (Manual Dashboard)**.

### Option A: Render Blueprint (Recommended)
1. Push this repository to GitHub or GitLab.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** -> **Blueprint**.
4. Connect your TenderBee repository.
5. Render will detect [`render.yaml`](file:///c:/Users/chand/OneDrive/Desktop/P.L/Tenderbee/render.yaml) and configure:
   - **`tenderbee-backend`** (Web Service)
   - **`tenderbee-worker`** (Celery background worker)
6. Supply the required environment variables prompted by Render (see Environment Variables table below).
7. Click **Apply**.

---

### Option B: Manual Web Service Setup on Render
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Select your Git repository.
4. Fill in the service configuration:
   - **Name**: `tenderbee-backend`
   - **Language / Runtime**: `Python`
   - **Root Directory**: `backend`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
   - **Health Check Path**: `/api/health/`
5. Under **Advanced** -> **Environment Variables**, add:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.3` | Python runtime version |
| `DJANGO_DEBUG` | `False` | Disables debug mode in production |
| `DJANGO_SECRET_KEY` | *(Click "Generate" or paste 50+ chars)* | Django cryptographic key |
| `DATABASE_URL` | `postgresql://user:pass@ep-pooler.neon.tech/tenderbee?sslmode=require` | Pooled Postgres connection |
| `DIRECT_URL` | `postgresql://user:pass@ep-direct.neon.tech/tenderbee?sslmode=require` | Session connection for migrations |
| `ALLOWED_HOSTS` | `.onrender.com` | Allowed hostnames (Render auto-detects `RENDER_EXTERNAL_HOSTNAME`) |
| `CORS_ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` | Vercel domain |
| `CSRF_TRUSTED_ORIGINS` | `https://your-frontend.vercel.app` | Vercel domain for Django CSRF |
| `SECURE_SSL_REDIRECT` | `True` | Forces HTTPS |
| `STORAGE_BACKEND` | `b2` *(or `disk`)* | Document storage provider |
| `B2_ENDPOINT_URL` | `https://s3.us-east-005.backblazeb2.com` | Backblaze S3 API endpoint |
| `B2_APPLICATION_KEY_ID` | *(Your B2 Key ID)* | Backblaze key ID |
| `B2_APPLICATION_KEY` | *(Your B2 Application Key)* | Backblaze app key |
| `B2_BUCKET_NAME` | `tenderbee-docs` | S3 bucket name |
| `TINYFISH_API_KEY` | *(Optional)* | TinyFish API key |
| `LLM_API_KEY` | *(Optional)* | LLM integration key |
| `REDIS_URL` | *(Optional)* | Redis URL (if running Celery) |

6. Click **Create Web Service**.
7. Once deployed, copy your Render service URL (e.g., `https://tenderbee-backend.onrender.com`).

---

## Part 2: Deploy Frontend on Vercel

1. Log in to [Vercel](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import your TenderBee repository.
4. In the **Configure Project** screen:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click **Edit** and choose `frontend`
     *(Note: If you leave Root Directory as `./`, the included root `vercel.json` will build the frontend automatically).*
5. Expand **Environment Variables** and add:

| Key | Value | Description |
| :--- | :--- | :--- |
| `BACKEND_URL` | `https://tenderbee-backend.onrender.com` | Your live Render backend URL *(no trailing slash)* |
| `INTERNAL_BACKEND_URL` | `https://tenderbee-backend.onrender.com` | Backup alias for proxy route |
| `NODE_ENV` | `production` | Production mode |

6. Click **Deploy**.
7. Vercel will install dependencies, compile the TypeScript App Router, and output your live deployment URL (e.g., `https://tenderbee.vercel.app`).

---

## Part 3: Link Vercel & Render (Final Step)

After both services are deployed, update the CORS settings on Render so the backend accepts requests from your live Vercel domain:

1. Open your **Render Dashboard** -> `tenderbee-backend` -> **Environment**.
2. Update:
   - `CORS_ALLOWED_ORIGINS`: `https://your-app.vercel.app,http://localhost:3000`
   - `CSRF_TRUSTED_ORIGINS`: `https://your-app.vercel.app`
3. Click **Save Changes**. Render will automatically redeploy with the updated origins.

---

## Key Features Included

- **WhiteNoise Static Asset Serving**: Django admin and API schema assets are automatically collected and served with gzip/brotli compression without needing an S3 bucket or Nginx for static assets.
- **Secure Reverse Proxy SSL Handling**: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` ensures cookies, HTTPS redirection, and session tokens function correctly behind Render's reverse proxy.
- **Automated Next.js Backend Proxy**: All client calls route through `/api/backend/...` on the Next.js server, completely preventing browser mixed-content and CORS cross-domain cookie issues.
- **Dynamic Preview URLs**: Built-in wildcard support for `*.vercel.app` and `*.onrender.com` ensures Vercel Preview Deployments work seamlessly without manual origin reconfiguration.
