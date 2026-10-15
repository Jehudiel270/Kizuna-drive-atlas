"use client";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { nf, orf, pf } from "@/lib/fmt";
import { Alerts, Card, Gate, PageHead, Table, VerdictBadge } from "@/components/ui";
import { Forest } from "@/components/charts";

export type Hyp = {
  id: string; qs: string; os: string; statement: string; question: string; objective: string; test: string; expected: string; testable: boolean; reason: string | null; n: number; events: number;
  primary: { kind?: string; label?: string; or?: number; ci_low?: number; ci_high?: number; p?: number; stat?: number; df?: number; coef?: number } | null; p_holm: number | null; sign_ok: boolean | null;
  details: any[]; extra: any; verdict: string; verdict_label: string; verdict_text: string; interpretation: string; robustness_summary?: { specs_tested: number; sign_ok: number; significant_expected: number };
};
export type HypRes = { n_model: number; events: number; epv: number | null; method: string; alpha: number; hypotheses: Hyp[]; warnings: { level: string; text: string }[]; robustness: Record<string, any[]>; power: Record<string, any>; models: Record<string, any> };

export default function Hypotheses() {
  const { data, error, loading } = useApi<HypRes>("/analysis/hypotheses");
  return (
    <>
      <PageHead title="Les cinq hypothèses">Chaque hypothèse du protocole est reliée à sa question (QS), son objectif (OS), son test et sa règle de décision. Les p-valeurs des 5 tests principaux sont corrigées par Holm pour limiter les fausses découvertes.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (
        <div className="stack">
          <Alerts items={data.warnings} />
          <Card title="Effets principaux (rapports de cotes par écart-type)" sub={`Modèle B · ${data.n_model} projets, ${data.events} échecs · OR > 1 : le facteur augmente la probabilité d'échec`}>
            <Forest name="forest-hypotheses" rows={[
              ...(data.hypotheses.filter((h) => ["H1", "H2", "H5"].includes(h.id) && h.primary?.or != null).map((h) => ({ label: `${h.id} · ${h.primary?.label ?? ""}`, or: h.primary!.or!, ci_low: h.primary!.ci_low!, ci_high: h.primary!.ci_high!, p: h.primary!.p }))),
              ...((data.models.B?.coefficients ?? []).filter((c: any) => c.term === "z_soutien").map((c: any) => ({ label: "Soutien de la direction (effet direct)", or: c.or, ci_low: c.ci_low, ci_high: c.ci_high, p: c.p }))),
            ]} />
          </Card>
          <Card title="Tableau de décision">
            <Table head={["", "Hypothèse", "Test", "Estimation", "p", "p Holm", "Verdict"]} num={[4, 5]}
              rows={data.hypotheses.map((h) => [<Link key="i" href={`/hypotheses/${h.id}`}><b>{h.id}</b></Link>, h.statement.length > 110 ? h.statement.slice(0, 108) + "…" : h.statement, h.test.length > 60 ? h.test.slice(0, 58) + "…" : h.test,
                h.primary?.or != null ? orf(h.primary) : h.primary?.stat != null ? `LR χ²(${h.primary.df}) = ${nf(h.primary.stat)}` : "—", pf(h.primary?.p), pf(h.p_holm), <VerdictBadge key="v" v={h.verdict} />])} />
            <p className="note" style={{ marginTop: 10 }}>Règle : « soutenue » = effet dans le sens attendu, significatif après Holm (α = {data.alpha}) ; « partiellement » = sens attendu mais non significatif après correction, ou seulement une partie des composantes ; « contredite » = effet significatif de sens opposé.</p>
          </Card>
        </div>
      )}</Gate>
    </>
  );
}
