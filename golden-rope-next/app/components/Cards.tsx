"use client";

function pct(x?: number | null) {
  if (typeof x !== "number") return "—";
  return `${(x * 100).toFixed(2)}%`;
}
function withinHours(iso?: string | null, hours = 24) {
  if (!iso) return false;
  const t = new Date(iso);
  return Date.now() - t.getTime() <= hours * 3600 * 1000;
}

export function SignalCard({ s }: { s: any }) {
  const tone =
    typeof s.impact === "number" ? (s.impact > 0 ? "up" : s.impact < 0 ? "down" : "neutral") : "neutral";
  return (
    <div className="card" style={{ borderRadius: 12 }}>
      <div className="card-row">
        <div className="card-title">
          <span style={{ fontWeight: 600 }}>{s.title ?? s.type ?? "Signal"}</span>
        </div>
        <span
          className="badge"
          style={{
            background: tone === "up" ? "#e7f7ef" : tone === "down" ? "#fde8e8" : "#eef2f7",
            color: tone === "up" ? "#0f9255" : tone === "down" ? "#b42318" : "#334155",
          }}
        >
          {pct(s.impact)}
        </span>
      </div>
      <div className="muted">
        <span className="badge">{s.type ?? "—"}</span> • <span>{s.ticker ?? "—"}</span>
        {withinHours(s.generated_at ?? s.ts, 24) && <span style={{ marginLeft: 8, color: "#0f9255" }}>new</span>}
      </div>
    </div>
  );
}

export function EventCard({ e }: { e: any }) {
  const when = e.when || e.event_time || e.created_at;
  const d = when ? new Date(when) : null;
  return (
    <div className="card" style={{ borderRadius: 12 }}>
      <div className="card-row">
        <div className="card-title">
          <span style={{ fontWeight: 600 }}>{e.type ?? "Event"}</span>
        </div>
        <span className="badge">{d ? d.toLocaleString() : "—"}</span>
      </div>
      <div className="muted">
        <span className="badge">{e.ticker ?? "—"}</span> • <span>{e.note ?? e.description ?? ""}</span>
      </div>
    </div>
  );
}

export function ArticleCard({ a }: { a: any }) {
  const ts = a.ts || a.published_at || a.created_at;
  const fresh = withinHours(ts, 12);
  return (
    <div className="card hover" style={{ borderRadius: 12 }}>
      <div className="card-row">
        <div className="card-title">
          {a.url ? (
            <a href={a.url} target="_blank" rel="noreferrer" className="link">
              {a.title ?? "Article"}
            </a>
          ) : (
            <span style={{ fontWeight: 600 }}>{a.title ?? "Article"}</span>
          )}
        </div>
        <span className="badge">{a.source ?? "—"}</span>
      </div>
      <div className="muted">
        <span className="badge">{a.ticker ?? "—"}</span> •{" "}
        <span>{ts ? new Date(ts).toLocaleString() : "—"}</span>
        {fresh && <span style={{ marginLeft: 8, color: "#0f9255" }}>fresh</span>}
      </div>
    </div>
  );
}
