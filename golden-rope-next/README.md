# Golden Rope (Next.js + Supabase + Vercel)

## 1) Environment variables (Vercel Project → Settings → Environment Variables)
- `NEXT_PUBLIC_SUPABASE_URL` = https://YOUR-PROJECT.supabase.co
- `SUPABASE_SERVICE_KEY` = your Supabase service_role key (kept **server-side** only)

> Because this app fetches from Supabase **server-side** only, the service key never reaches the browser.

## 2) Deploy
```bash
npm i
npm run dev
# or push to GitHub and "Import" on Vercel (select this repo)
