# MindScan Production Deployment Guide

This document provides complete, production-grade instructions for deploying the **MindScan Multimodal Clinical Screening Platform** (FastAPI ML Backend, PostgreSQL Database, and Static Web Frontend).

---

## 1. Recommended Hosting Architecture

Deploying a machine learning backend (PyTorch, Transformers, Wav2Vec2, MobileViT) together with a web frontend requires an architecture that accommodates ML memory footprints without unnecessary costs.

| Component | Recommended Host | Tier / Cost | Why It Is Chosen |
| :--- | :--- | :--- | :--- |
| **Frontend** | **Vercel** / **Cloudflare Pages** | **100% Free** | Instant global edge CDN, zero-configuration HTTPS, unlimited bandwidth, automatic GitHub CI/CD deployments. |
| **Database** | **Supabase** / **Neon** | **100% Free** | Dedicated managed PostgreSQL 15+, SSL required, automated daily backups, 500MB free storage. |
| **ML Backend (Free)** | **Hugging Face Spaces (Docker)** | **100% Free** | **16 GB RAM + 2 vCPUs completely free**. Ideal for hosting heavy PyTorch and Wav2Vec2 models without OOM errors. |
| **ML Backend (Low Cost)** | **Render.com** (Web Service) | Free (512MB) / Starter ($7/mo, 1GB) | Docker container support, automated Alembic migrations, HTTPS out of the box, zero-maintenance. |
| **Alternative (VPS)** | **Hetzner Cloud** (CX22) | **€4.50 / month** | 2 vCPUs, 4 GB RAM, 40 GB NVMe SSD. Runs the entire `docker-compose.yml` stack with full resources. |

---

## 2. Memory Limits & Sizing Strategy

### Understanding the ML Memory Footprint
- **PyTorch Base Engine**: ~250 MB RAM
- **XLM-RoBERTa / RoBERTa Model**: ~450 MB RAM
- **Wav2Vec2 XLS-R Acoustic Model**: ~800 MB RAM
- **MobileViT Emotion Model**: ~120 MB RAM
- **Total with All Checkpoints Loaded**: **~1.6 GB – 1.8 GB RAM**

### How MindScan Handles Constrained Free Tiers (e.g. Render 512MB)
MindScan has been engineered with **adaptive model fallback**:
1. **Without Heavy Transformer Weights Loaded**: The application uses Indic-aware clinical lexicons for zero-shot text affect, acoustic timing observations, and Haar-cascade visual analysis, consuming only **~320 MB RAM**. This runs comfortably on standard 512MB free tiers.
2. **Single-Worker Concurrency (`WEB_CONCURRENCY=1`)**: In Python ML containers, each Uvicorn worker process duplicates all loaded models in memory. Keeping `WEB_CONCURRENCY=1` prevents memory duplication and stops container out-of-memory (OOM) crashes.
3. **If You Need Full 300M+ Transformer Checkpoints**:
   - **Option 1**: Use **Hugging Face Spaces** (Free 16 GB RAM).
   - **Option 2**: Upgrade Render from Free to **Starter ($7/mo, 1GB RAM)** or **Standard ($12/mo, 2GB RAM)**.
   - **Option 3**: Deploy on a **Hetzner CX22 VPS (€4.50/mo, 4GB RAM)**.

---

## 3. Step-by-Step Deployment Instructions

### Step 1: Create a Managed PostgreSQL Database

#### Using Supabase (Recommended Free PostgreSQL)
1. Go to [supabase.com](https://supabase.com) and click **Start your project** (Sign in with GitHub).
2. Click **New Project**:
   - **Name**: `mindscan-prod`
   - **Database Password**: Generate a secure password and save it in a password manager.
   - **Region**: Choose the closest region to your users (e.g., `East US` or `South Asia (Mumbai)`).
3. Click **Create new project** and wait ~2 minutes for provisioning.
4. In the left sidebar, click **Project Settings** (gear icon) -> **Database**.
5. Scroll down to **Connection String** -> select the **URI** tab.
6. Copy the URI. It will look like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
   *(Replace `[YOUR-PASSWORD]` with your actual password).*

---

### Step 2: Prepare GitHub Repository

Verify that sensitive files are ignored before pushing:
```bash
# Check git status to ensure .env, database files, and media are ignored
git status
```
Verify that `.gitignore` contains:
```
.env
*.db
*.sqlite3
venv/
node_modules/
```
Commit and push your project to your GitHub repository:
```bash
git add .
git commit -m "Prepare production configuration, Dockerfiles, and Alembic migrations"
git push origin main
```

---

### Step 3: Deploy the Backend (Render.com)

1. Log in to [render.com](https://render.com) using your GitHub account.
2. In the top navigation, click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository** -> click **Next**.
4. Connect your GitHub repository (`depression_detection`).
5. Configure the service:
   - **Name**: `mindscan-backend`
   - **Region**: Same region as your database (e.g., `Oregon (US West)` or `Frankfurt (EU Central)`).
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime / Environment**: **Docker**
   - **Dockerfile Path**: `./Dockerfile`
   - **Instance Type**: **Free** (or Starter $7/mo for heavy checkpoints).
6. Expand the **Advanced** section -> click **Add Environment Variable** and enter the following:

| Variable Name | Production Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables production security policies |
| `DEBUG` | `False` | Disables verbose debug modes & docs |
| `DATABASE_URL` | *Your Supabase/Neon PostgreSQL URI* | Direct connection string to PostgreSQL |
| `SECRET_KEY` | *Generated 32+ character random string* | Used for signing JWT auth tokens |
| `ADMIN_REGISTRATION_CODE` | *Secure random string* | Server-side code required to create Admin accounts |
| `CLINICIAN_REGISTRATION_CODE` | *Secure random string* | Optional code for auto-approved Clinicians |
| `GOOGLE_CLIENT_ID` | *Your Google Cloud OAuth Client ID* | Google Single Sign-On |
| `GOOGLE_CLIENT_SECRET` | *Your Google Cloud OAuth Client Secret* | Google Single Sign-On |
| `GOOGLE_REDIRECT_URI` | `https://your-frontend.vercel.app/login.html` | Match your frontend login URL |
| `FRONTEND_URL` | `https://your-frontend.vercel.app` | Base URL of frontend |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Allowed origins (no trailing slashes) |
| `WEB_CONCURRENCY` | `1` | Single worker for memory efficiency |
| `LOG_LEVEL` | `INFO` | Structured logging verbosity |

7. Click **Create Web Service**.
8. Render will build the Docker container, run `alembic upgrade head` via `entrypoint.sh` to initialize the database schema, and launch Uvicorn.
9. Once deployed, copy your backend URL:
   `https://mindscan-backend.onrender.com`
10. Test health check in your browser:
    `https://mindscan-backend.onrender.com/health`
    You should receive a `{"status": "healthy", "database": "connected", ...}` JSON response.

---

### Step 4: Deploy the Frontend (Vercel)

1. Log in to [vercel.com](https://vercel.com) using your GitHub account.
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository (`depression_detection`).
4. In the Project Configuration:
   - **Framework Preset**: **Other**
   - **Root Directory**: Click Edit, select `frontend`, and click **Continue**.
   - **Build & Output Settings**: Leave empty (frontend is pure static vanilla HTML/CSS/JS).
5. Click **Deploy**.
6. Within 15 seconds, Vercel will provide your live URL:
   `https://mindscan-frontend.vercel.app`
7. In `frontend/script.js` and `frontend/login.js`, verify that API calls point to your live backend URL (or pass through the reverse proxy).

---

### Step 5: Update Google Cloud OAuth Credentials

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Navigate to **APIs & Services** -> **Credentials**.
3. Click on your **OAuth 2.0 Client ID** (Web application).
4. Under **Authorized JavaScript origins**, click **Add URI** and add:
   - `https://mindscan-frontend.vercel.app`
   - `https://mindscan-backend.onrender.com`
5. Under **Authorized redirect URIs**, click **Add URI** and add:
   - `https://mindscan-frontend.vercel.app/login.html`
6. Click **Save**.

---

## 4. Local Production-Like Testing (Docker Compose)

Before deploying to the cloud, you can test the entire production stack locally:

```bash
# 1. Start all services (PostgreSQL, Backend with Alembic, Frontend with Nginx)
docker compose up --build

# 2. Verify running containers
docker compose ps

# 3. Test endpoints:
# Frontend: http://localhost:3000
# Backend Health: http://localhost:8000/health
# Admin Login: http://localhost:3000/login.html

# 4. Stop containers when done
docker compose down
```

---

## 5. Rollback Procedure

If a deployed version experiences unexpected issues, follow this rapid rollback procedure:

### Frontend Rollback (Vercel)
1. Go to the **Deployments** tab on your Vercel Dashboard.
2. Find the previous stable deployment.
3. Click the three dots (`...`) on the right side -> **Instant Rollback**.
4. The previous version goes live in under 5 seconds.

### Backend Rollback (Render.com)
1. Go to your Web Service dashboard on Render.
2. Click **Events** or **Deploys**.
3. Select the previous successful deployment and click **Rollback to this deploy**.

### Database Migration Rollback (Alembic)
If a newly applied database schema migration needs to be rolled back:
```bash
# Connect to your backend terminal or run locally with production DATABASE_URL:
alembic downgrade -1
```

---

## 6. Production Launch Checklist

- [ ] `.env` is listed in `.gitignore` and has **NOT** been committed to git.
- [ ] `DEBUG=False` is set in production environment variables.
- [ ] Managed PostgreSQL database is provisioned and connection string verified.
- [ ] Alembic migrations run cleanly on startup (`alembic upgrade head`).
- [ ] Default demo administrator account verified (`admin@mindscan.health`).
- [ ] `ADMIN_REGISTRATION_CODE` is set to a long random secret in `.env`.
- [ ] Google OAuth Client ID and Redirect URIs match the live frontend domain.
- [ ] Production CORS origins list contains only authorized frontend domains.
- [ ] Health check endpoint `/health` returns HTTP 200 with `"database": "connected"`.
- [ ] Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`) verified on live HTTP responses.
- [ ] `WEB_CONCURRENCY` is set to `1` to protect container memory limits.
