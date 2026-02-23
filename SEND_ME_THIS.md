# You send me this — I do everything else

You only do **one thing**: give me the values below (or put them in a file). I take care of all the rest: config, deployment steps, and instructions.

---

## Option A — Easiest: you fill a file, I do the rest

1. In your project folder, copy the file **`.env.example`** and rename the copy to **`.env`**.
2. Open **`.env`** and replace the placeholder values with your real ones (see the list below).
3. Tell me: **"I filled .env"** or **"Done"**.  
   I will then:
   - Check that nothing is missing (with a small script),
   - Give you a short **5-step guide** to put the site online on Render (only clicks, no technical stuff),
   - Do any code or config changes needed.

   To check yourself: run `python check_env.py`. If you use a `.env` file, run first: `python -m pip install python-dotenv`.

**Important:** Do **not** paste real API keys or passwords in a **public** chat. Prefer putting them only in your local **`.env`** file and just tell me *"Done"*. If you send values in chat, use a private or secure channel.

---

## Option B — You send me the values

Send me the following (in a private/secure way if they are real keys). I will fill the config for you and tell you exactly what to click on Render.

---

## The list — what I need from you

Copy this list and replace the `???` with your values. You can leave optional ones empty if you don’t have them.

### Required (site + emails + payments)

| What | Example | Your value |
|------|--------|------------|
| **DATABASE_URL** (PostgreSQL) | `postgresql://user:password@host:5432/fitmatch` | ??? |
| **RESEND_API_KEY** (emails) | `re_xxxxxxxxxxxx` | ??? |
| **SENDER_EMAIL** (emails) | `noreply@fitmatch.fr` | ??? |
| **STRIPE_SECRET_KEY** | `sk_live_xxx` or `sk_test_xxx` | ??? |
| **STRIPE_PUBLIC_KEY** | `pk_live_xxx` or `pk_test_xxx` | ??? |
| **STRIPE_WEBHOOK_SECRET** | `whsec_xxx` (from Stripe webhook) | ??? |

### Optional but useful

| What | Example | Your value |
|------|--------|------------|
| **SUPABASE_URL** | `https://xxxx.supabase.co` | ??? or leave empty |
| **SUPABASE_KEY** (anon key) | `eyJhbG...` | ??? or leave empty |
| **SUPABASE_JWT_SECRET** | from Supabase Project Settings → API | ??? or leave empty |
| **GOOGLE_MAPS_API_KEY** | for map/search | ??? or leave empty |
| **CORS_ORIGINS** (your site URL) | `https://fitmatch.fr,https://www.fitmatch.fr` | ??? or leave empty |
| **SITE_URL** (production URL) | `https://fitmatch.fr` | ??? or leave empty |

### Where to get these

- **DATABASE_URL**: From your PostgreSQL host (Render, Supabase, or any provider). Format: `postgresql://USER:PASSWORD@HOST:5432/DATABASE`
- **Resend**: [resend.com](https://resend.com) → API Keys. **SENDER_EMAIL** must be a domain you verified in Resend.
- **Stripe**: [dashboard.stripe.com](https://dashboard.stripe.com) → Developers → API keys (Secret + Publishable). Webhook: Developers → Webhooks → Add endpoint → URL = `https://YOUR-SITE/api/stripe/webhook` → copy **Signing secret**.
- **Supabase**: Project Settings → API (URL, anon key, JWT secret).
- **CORS_ORIGINS** / **SITE_URL**: Your real site address (e.g. `https://fitmatch.fr`).

---

## After you send this (or fill .env and say "Done")

I will:

1. Make sure your project is ready (env, config).
2. Give you **one short guide**: **DEPLOY_RENDER_5_STEPS.md** — only 5 steps on Render (create account, connect repo, add env vars, deploy). No need to understand anything; just follow the steps.
3. Tell you the exact URL where your site will be (e.g. `https://fitmatch-xxx.onrender.com`) and what to do for your own domain if you have one.

You send me the codes/keys (or fill .env and tell me). I do everything else.
