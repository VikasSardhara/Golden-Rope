export const dynamic = "force-dynamic";

import { supabaseServer } from "@/lib/supabaseServer";
import { Article, Event, Signal } from "@/lib/types";
import MonitorClient from "./monitor-client";

function hoursAgoISO(hours: number) {
  return new Date(Date.now() - hours * 3600_000).toISOString();
}

export default async function Page({
  searchParams,
}: { searchParams: Record<string, string | string[] | undefined> }) {
  const hours = Number(searchParams.hours ?? 48);
  const ticker = ((searchParams.ticker as string) || "").toUpperCase();
  const types = ((searchParams.types as string) || "CEO_CHANGE")
    .split(",")
    .filter(Boolean);

  const since = hoursAgoISO(hours);
  const supa = supabaseServer();

  // ARTICLES (first_seen_at)
  let { data: articles, error: aErr } = await supa
    .from("articles")
    .select("article_id, first_seen_at, source, title, url, language, summary")
    .gte("first_seen_at", since)
    .order("first_seen_at", { ascending: false })
    .limit(200);

  if (aErr) console.error(aErr);
  // optional: when ticker is present, filter title/summary contains (case-insensitive)
  if (ticker) {
    const t = ticker.toLowerCase();
    articles = (articles || []).filter(
      a =>
        a.title?.toLowerCase().includes(t) ||
        (a.summary ?? "").toLowerCase().includes(t)
    );
  }

  // EVENTS (created_at)
  const { data: events, error: eErr } = await supa
    .from("events")
    .select(
      "event_id, created_at, occurred_at, event_type, primary_ticker, sentiment, confidence, extracted"
    )
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(400);
  if (eErr) console.error(eErr);

  const eventsFiltered: Event[] = (events || []).filter(e => {
    const tickOk = !ticker || e.primary_ticker?.toUpperCase().includes(ticker);
    const typeOk = !types.length || types.includes(e.event_type);
    return tickOk && typeOk;
  });

  // SIGNALS (generated_at) + derive event_type by joining events
  const { data: signalsRaw, error: sErr } = await supa
    .from("signals")
    .select(
      "signal_id, generated_at, event_id, ticker, horizon, predicted_return, uncertainty, direction, model_version"
    )
    .gte("generated_at", since)
    .order("generated_at", { ascending: false })
    .limit(400);
  if (sErr) console.error(sErr);

  const evMap = new Map(events?.map(e => [e.event_id, e.event_type]) || []);
  const signals: Signal[] = (signalsRaw || [])
    .map(s => ({ ...s, event_type: evMap.get(s.event_id) }))
    .filter(s => {
      const tickOk = !ticker || s.ticker?.toUpperCase().includes(ticker);
      const typeOk = !types.length || (s.event_type && types.includes(s.event_type));
      return tickOk && typeOk;
    });

  return (
    <MonitorClient
      initial={{
        hours,
        ticker,
        types,
        articles: articles || [],
        events: eventsFiltered,
        signals,
      }}
    />
  );
}
