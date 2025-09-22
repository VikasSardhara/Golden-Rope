export type Article = {
  article_id: string;
  first_seen_at: string;
  source: string;
  title: string;
  url: string;
  language: string | null;
  summary?: string | null;
};

export type Event = {
  event_id: string;
  created_at: string;
  occurred_at: string | null;
  event_type: string;
  primary_ticker: string;
  affected_tickers: string[] | null;
  sentiment: number | null;
  confidence: number | null;
  article_id: string | null;
  extracted: any | null;
};

export type Signal = {
  signal_id: string;
  generated_at: string;
  event_id: string;
  ticker: string;
  horizon: "1D" | "5D" | "20D" | string;
  predicted_return: number | null;
  uncertainty: number | null;
  direction: -1 | 0 | 1;
  model_version?: string | null;
  // derived on server:
  event_type?: string;
};
