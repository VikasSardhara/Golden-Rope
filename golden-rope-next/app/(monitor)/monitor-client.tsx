"use client";

import { useEffect, useMemo, useState } from "react";
import { supabaseBrowser } from "@/lib/supabaseClient";
import { Article, Event, Signal } from "@/lib/types";

type Initial = {
  hours: number;
  ticker: string;
  types: string[];
  articles: Article[];
  events: Event[];
  signals: Signal[];
};

function withinHours(iso?: string | null, hours = 48) {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() <= hours * 3600_000;
}

export default function MonitorClient({ initial }: { initial: Initial }) {
  const [hours] = useState(initial.hours);
  const [ticker] = useState(initial.ticker);
  const [types] = useState(initial.types);

  const [articles, setArticles] = useState<Article[]>(initial.articles);
  const [events, setEvents] = useState<Event[]>(initial.events);
  const [signals, setSignals] = useState<Signal[]>(initial.signals);

  const supa = useMemo(() => supabaseBrowser(), []);

  // Realtime: ARTICLES inserts
  useEffect(() => {
    const ch = supa
      .channel("rt-articles")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "articles" },
        (payload) => {
          const a = payload.new as Article;
          // filter against window + ticker contains (title/summary)
          if (!withinHours(a.first_seen_at, hours)) return;
          if (ticker) {
            const t = ticker.toLowerCase();
            if (
              !a.title?.toLowerCase().includes(t) &&
              !(a.summary ?? "").toLowerCase().includes(t)
            ) return;
          }
          setArticles((cur) =>
            [a, ...cur].slice(0, 200)
          );
        }
      )
      .subscribe();
    return () => { supa.removeChannel(ch); };
  }, [supa, hours, ticker]);

  // Realtime: EVENTS inserts/updates
  useEffect(() => {
    const ch = supa
      .channel("rt-events")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "events" },
        (payload) => {
          const e = (payload.new || payload.record) as Event;
          if (!withinHours(e.created_at, hours)) return;
          if (ticker && !e.primary_ticker?.toUpperCase().includes(ticker)) return;
          if (types.length && !types.includes(e.event_type)) return;

          setEvents((cur) => {
            const idx = cur.findIndex((x) => x.event_id === e.event_id);
            if (idx === -1) return [e, ...cur].slice(0, 400);
            const copy = cur.slice(); copy[idx] = e; return copy;
          });
        }
      )
      .subscribe();
    return () => { supa.removeChannel(ch); };
  }, [supa, hours, ticker, types]);

  // Realtime: SIGNALS inserts (derive event_type lazily by optimistic join if needed)
  useEffect(() => {
    const ch = supa
      .channel("rt-signals")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "signals" },
        (payload) => {
          const s = payload.new as Signal;
          if (!withinHours(s.generated_at, hours)) return;
          if (ticker && !s.ticker?.toUpperCase().includes(ticker)) return;
          // Best-effort derive event_type from current event list
          const ev = events.find((e) => e.event_id === s.event_id);
          const s2 = { ...s, event_type: ev?.event_type };
          if (types.length && s2.event_type && !types.includes(s2.event_type)) return;

          setSignals((cur) => [s2, ...cur].slice(0, 400));
        }
      )
      .subscribe();
    return () => { supa.removeChannel(ch); };
  }, [supa, hours, ticker, types, events]);

  return (
    <main className="wrap">
      <header className="kpis">
        <div className="chip">Signals: {signals.length}</div>
        <div className="chip">Events: {events.length}</div>
        <div className="chip">Articles: {articles.length}</div>
        <div className="muted">Window: last {hours}h {ticker ? `• Ticker: ${ticker}` : ""}</div>
      </header>

      <section>
        <h2>Signals</h2>
        <div className="grid">
          {signals.map((s) => (
            <div className="card" key={s.signal_id}>
              <div className="row">
                <strong>{s.ticker}</strong>
                <span className="pill">{s.horizon}</span>
              </div>
              <div className="muted">{new Date(s.generated_at).toLocaleString()} • {s.event_type ?? "—"}</div>
              <div className="row">
                <div>Pred: {(s.predicted_return ?? 0).toFixed(4)}</div>
                <div>Dir: {s.direction}</div>
                <div>σ: {(s.uncertainty ?? 0).toFixed(4)}</div>
              </div>
            </div>
          ))}
          {!signals.length && <div className="empty">No signals in window.</div>}
        </div>
      </section>

      <section>
        <h2>Events</h2>
        <table className="table">
          <thead>
            <tr><th>When</th><th>Ticker</th><th>Type</th><th>Sentiment</th><th>Conf</th><th>Headline</th></tr>
          </thead>
          <tbody>
            {events.map(e => (
              <tr key={e.event_id}>
                <td>{new Date(e.created_at).toLocaleString()}</td>
                <td>{e.primary_ticker}</td>
                <td>{e.event_type}</td>
                <td>{e.sentiment?.toFixed(2) ?? "—"}</td>
                <td>{e.confidence?.toFixed(2) ?? "—"}</td>
                <td>{e.extracted?.headline ?? "—"}</td>
              </tr>
            ))}
            {!events.length && (
              <tr><td colSpan={6} className="empty">No events in window.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Articles</h2>
        <table className="table">
          <thead>
            <tr><th>Seen</th><th>Source</th><th>Title</th><th>Lang</th></tr>
          </thead>
          <tbody>
            {articles.map(a => (
              <tr key={a.article_id}>
                <td>{new Date(a.first_seen_at).toLocaleString()}</td>
                <td>{a.source}</td>
                <td><a href={a.url} target="_blank" rel="noreferrer">{a.title}</a></td>
                <td>{a.language ?? "—"}</td>
              </tr>
            ))}
            {!articles.length && (
              <tr><td colSpan={4} className="empty">No articles in window.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <style jsx>{`
        .wrap { padding: 16px; color: #e5e7eb; background: #0b1220; min-height: 100vh; }
        .kpis { display:flex; gap:12px; align-items:center; margin-bottom:8px; }
        .chip { background:#111827; border:1px solid #1f2937; padding:6px 10px; border-radius:999px; }
        .muted { color:#94a3b8; }
        .grid { display:grid; gap:12px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
        .card { background:#0f172a; border:1px solid #1f2937; border-radius:12px; padding:12px; }
        .row { display:flex; justify-content:space-between; align-items:center; margin:6px 0; gap:8px; }
        .pill { border:1px solid #334155; padding:2px 8px; border-radius:999px; color:#cbd5e1; }
        .table { width:100%; border-collapse: collapse; margin-top:8px; }
        .table th, .table td { border-bottom:1px solid #1f2937; padding:8px; text-align:left; }
        h2 { margin:18px 0 6px; }
        .empty { color:#94a3b8; padding:8px; }
      `}</style>
    </main>
  );
}
