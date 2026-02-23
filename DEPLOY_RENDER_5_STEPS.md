# Put your site online on Render — 5 steps (I did the rest)

You already gave me the keys (or filled `.env`). Here you only **click** on Render. No need to understand; just follow.

---

## Step 1 — Create account and repo

1. Go to **[render.com](https://render.com)** and sign up (e.g. with GitHub).
2. Your FitMatch code must be on **GitHub**. If it’s only on your PC, create a repo on GitHub and push your project (or tell me and I’ll give you the exact git commands).

---

## Step 2 — Create a PostgreSQL database (on Render)

1. In Render dashboard: **New +** → **PostgreSQL**.
2. Name: e.g. `fitmatch-db`, Region: choose closest to you.
3. Click **Create Database**.
4. When it’s ready, open the database → **Info** (or **Connections**) and copy **Internal Database URL** (or **External** if you’ll run the app elsewhere).  
   It looks like: `postgresql://user:password@host/database`
5. Put this URL in your **`.env`** as **`DATABASE_URL`** (if you didn’t already). You’ll also paste it in Step 4.

---

## Step 3 — Create the Web Service (your site)

1. **New +** → **Web Service**.
2. **Connect** your GitHub account if asked, then select the **FitMatch repository**.
3. Configure:
   - **Name:** `fitmatch-web` (or any name).
   - **Region:** same as your database.
   - **Branch:** `main` (or your default branch).
   - **Runtime:** **Python 3**.
   - **Build Command:**  
     `pip install -r requirements.txt`
   - **Start Command:**  
     `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Do **not** click Deploy yet. Go to **Step 4**.

---

## Step 4 — Add environment variables (your keys)

1. In the same Web Service, open the **Environment** tab (or **Environment Variables**).
2. Click **Add Environment Variable** and add **each** of these (copy the **name** and the **value** from your `.env`):

| Name | Where to get the value |
|------|-------------------------|
| `DATABASE_URL` | From Step 2 (PostgreSQL URL) |
| `RESEND_API_KEY` | Your `.env` |
| `SENDER_EMAIL` | Your `.env` |
| `STRIPE_SECRET_KEY` | Your `.env` |
| `STRIPE_PUBLIC_KEY` | Your `.env` |
| `STRIPE_WEBHOOK_SECRET` | Your `.env` |
| `PYTHON_VERSION` | Type: `3.12.8` |

If you have them, also add:

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET`
- `CORS_ORIGINS` (e.g. `https://fitmatch.fr,https://www.fitmatch.fr`)
- `SITE_URL` (e.g. `https://fitmatch.fr` or your Render URL)
- `GOOGLE_MAPS_API_KEY`

3. Save.

---

## Step 5 — Deploy

1. Click **Create Web Service** (or **Deploy** if you already created it).
2. Wait for the build to finish (a few minutes). If the build fails, tell me the error message and I’ll fix it.
3. When it’s green, Render shows a URL like: **`https://fitmatch-web-xxxx.onrender.com`**. That is your site.

Open that URL in your browser: your site is online.

---

## Optional — Reminders (24h / 2h emails)

To send reminder emails automatically:

1. **New +** → **Background Worker**.
2. Same repo, same branch.
3. **Build Command:** `pip install -r requirements.txt`  
   **Start Command:** `python worker.py`
4. In **Environment**, add the **same** variables as the Web Service: `DATABASE_URL`, `RESEND_API_KEY`, `SENDER_EMAIL`, and `PYTHON_VERSION` = `3.12.8`.
5. Create the worker. It will run 24/7 and send the reminders.

---

## Stripe webhook (so payments work)

1. In Stripe: **Developers** → **Webhooks** → **Add endpoint**.
2. URL: `https://YOUR-RENDER-URL.onrender.com/api/stripe/webhook`  
   (replace with your real Render URL from Step 5.)
3. Select events: `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`.
4. Copy the **Signing secret** (`whsec_...`) and add it in Render **Environment** as `STRIPE_WEBHOOK_SECRET` (then redeploy if the service was already created).

---

## Summary

- **You:** create account, connect repo, create DB, create Web Service, paste env vars, deploy. Optional: Background Worker + Stripe webhook.
- **I did:** code, config, and this guide. When you send me the keys (or fill `.env` and say "Done"), everything else is ready.

If any step fails, send me the error or a screenshot and I’ll tell you exactly what to change.
