"use client";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { nf, orf, pct, pf } from "@/lib/fmt";
import { Alerts, Card, Gate, PageHead, Stat, VerdictBadge } from "@/components/ui";
import { Funnel, HBar, OUTCOME_COLORS } from "@/components/charts";

type Ov = {
  source: { kind: string }; target: { min: number; max: number }; n_total: number; n_analysable: number; n_model: number; progress_min: number | null;
  issue: { value: string; n: number; pct: number }[]; funnel: { step: string; n: number }[]; alerts: { level: string; text: string }[];
  hypotheses: { id: string; qs: string; os: string; statement: string; verdict: string; primary: { or?: number; ci_low?: number; ci_high?: number; p?: number; stat?: number; df?: number; label?: string } | null; p_holm: number | null; n: number }[];
  epv: number | null; method: string; events: number;
};

export default function Home() {
  const { data, error, loading } = useApi<Ov>("/analysis/overview");
  return (
    <>
      <PageHead title="Synthèse">Où en est la collecte, et que disent les données sur les cinq hypothèses du protocole ? Tout est recalculé à chaque nouvelle réponse Tally.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (
        <div className="stack">
          <div className="grid g4">
            <Stat v={data.n_total} l="soumissions reçues" />
            <Stat v={<>{data.n_analysable}<span style={{ fontSize: 20, color: "var(--muted)" }}> / {data.target.min}–{data.target.max}</span></>} l="projets analysables (cible protocole)" tone={data.n_analysable >= data.target.min ? "ok" : undefined} />
            <Stat v={data.events ?? "—"} l="échecs dans le modèle principal" />
            <Stat v={nf(data.epv, 1)} l={`événements par paramètre (EPV) · ${data.method ?? ""}`} tone={data.epv != null && data.epv < 10 ? "warn" : "ok"} />
          </div>
          <div className="bar" style={{ height: 10 }}><i style={{ width: `${Math.min(100, (data.progress_min ?? 0) * 100)}%` }} /></div>
          <div className="note">Avancement vers le minimum du protocole : {pct(data.progress_min)}</div>

          <h2 style={{ marginTop: 28 }}>Les 5 hypothèses du protocole</h2>
          <div className="grid g2">
            {data.hypotheses.map((h) => (
              <Link key={h.id} href={`/hypotheses/${h.id}`} className="card hcard">
                <div className="row space"><span className="hid">{h.id}</span><VerdictBadge v={h.verdict} /></div>
                <p style={{ margin: "10px 0 8px" }}>{h.statement}</p>
                <div className="row small note" style={{ gap: 18 }}>
                  {h.primary?.or != null ? <span>OR <b className="mono" style={{ color: "var(--text)" }}>{orf(h.primary)}</b></span> : h.primary?.stat != null ? <span>χ² (LR) <b className="mono" style={{ color: "var(--text)" }}>{nf(h.primary.stat)}</b> · ddl {h.primary.df}</span> : <span>Pas encore estimable</span>}
                  <span>p = <b className="mono" style={{ color: "var(--text)" }}>{pf(h.primary?.p)}</b></span>
                  <span>p Holm = <b className="mono" style={{ color: "var(--text)" }}>{pf(h.p_holm)}</b></span>
                  <span>{h.qs} · {h.os}</span>
                </div>
              </Link>
            ))}
          </div>

          <div className="grid g2" style={{ marginTop: 16 }}>
            <Card title="Entonnoir d'éligibilité" sub="Des soumissions brutes aux projets entrant dans les modèles"><Funnel steps={data.funnel} /></Card>
            <Card title="Issue des projets analysables" sub="Variable dépendante du protocole (« en cours » exclus)">
              <HBar name="issue-projets" rows={data.issue.map((r) => ({ label: r.value, value: r.n, color: OUTCOME_COLORS[r.value] }))} valueFmt={(v) => `${v}`} />
            </Card>
          </div>
          {data.alerts.length > 0 && <Card title="Points d'attention"><Alerts items={data.alerts} /></Card>}
        </div>
      )}</Gate>
    </>
  );
}
