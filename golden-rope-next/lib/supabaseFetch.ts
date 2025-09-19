// Server-side helper to call Supabase REST (PostgREST) with Service Role key.
// IMPORTANT: only import this in Server Components or Route Handlers.
import 'server-only';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY!;

if (!SUPABASE_URL || !SERVICE_KEY) {
  throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_KEY env");
}

const headers = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json'
};

export async function getArticles(limit = 100) {
  const url = `${SUPABASE_URL}/rest/v1/articles?select=*&order=first_seen_at.desc&limit=${limit}`;
  const res = await fetch(url, { headers, cache: 'no-store' });
  if (!res.ok) throw new Error(`Articles fetch failed: ${res.status}`);
  return res.json();
}

export async function getEvents(limit = 200) {
  const url = `${SUPABASE_URL}/rest/v1/events?select=*&order=created_at.desc&limit=${limit}`;
  const res = await fetch(url, { headers, cache: 'no-store' });
  if (!res.ok) throw new Error(`Events fetch failed: ${res.status}`);
  return res.json();
}

export async function getSignals(limit = 400) {
  const url = `${SUPABASE_URL}/rest/v1/signals?select=*&order=generated_at.desc&limit=${limit}`;
  const res = await fetch(url, { headers, cache: 'no-store' });
  if (!res.ok) throw new Error(`Signals fetch failed: ${res.status}`);
  return res.json();
}
