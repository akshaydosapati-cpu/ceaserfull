# CEASER Frontend API Configuration

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://ceaser-backend-production.onrender.com
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

The frontend API layer uses `NEXT_PUBLIC_API_URL` first, then falls back to `NEXT_PUBLIC_CEASER_API_URL`, then `https://ceaser-backend-production.onrender.com`.
