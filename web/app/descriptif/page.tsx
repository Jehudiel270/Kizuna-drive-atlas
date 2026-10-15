"use client";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { nf, pct, pf } from "@/lib/fmt";
import { Card, Gate, PageHead, Table, Tabs } from "@/components/ui";
import { HBar, Hist, Likert, OUTCOME_COLORS } from "@/components/charts";

type Desc = {
  profile: { n: number; variables: Record<string, { title: string; missing: number; table: { value: string; n: number; pct: number }[] }> };
  likert: { construct: string; construct_label: string; name: string; label: string; counts: number[]; reversed: boolean; mean: number | null }[];
  scores: { var: string; title: string; n: number; histogram: { edges: number[]; counts: number[] }; groups: { issue: string; label: string; n: number; mean: number | null; sd: number | null; median: number | null }[];
    anova: { F: number; p: number; df1: number; df2: number; eta2: number | null } | null; kruskal: { H: number; p: number } | null; posthoc: { a: string; b: string; diff: number; p: number; reject: boolean }[] }[];
};
type Ct = { var: string; title: string; n: number; columns: string[]; table: { value: string; counts: number[]; total: number; row_pct: (number | null)[] }[]; test: { chi2: number; dof: number; p: number; cramers_v: number; low_expected_share: number; mc_p: number | null; warning?: string } | null }[];

export default function Descriptif() {
  const [tab, setTab] = useState("profil");
  const d = useApi<Desc>("/analysis/descriptif");
  const c = useApi<Ct>(tab === "croise" ? "/analysis/crosstabs" : null, [tab]);
  return (
    <>
      <PageHead title="Descriptif & comparaisons">Profil de l'échantillon, réponses aux échelles et comparaisons selon l'issue du projet (ANOVA / Kruskal-Wallis pour les scores, Khi² pour les catégories, protocole 5.1–5.2). Ces tests sont descriptifs : les hypothèses se jugent dans la section « Questions de recherche ».</PageHead>
      <Tabs value={tab} onChange={setTab} tabs={[["profil", "Profil de l'échantillon"], ["echelles", "Réponses aux échelles"], ["scores", "Scores selon l'issue"], ["croise", "Croisements (Khi²)"]]} />
      {tab !== "croise" && <Gate loading={d.loading} error={d.error} data={d.data}>{d.data && (<>
        {tab === "profil" && <div className="grid g2">{Object.entries(d.data.profile.variables).map(([k, v]) => (
          <Card key={k} title={v.title} sub={v.missing ? `${v.missing} non renseigné(s)` : undefined}><HBar name={`profil-${k}`} rows={v.table.slice(0, 10).map((r) => ({ label: r.value, value: r.n }))} valueFmt={(x) => `${x}`} /></Card>))}</div>}
        {tab === "echelles" && <Card title="Distribution des réponses (1 à 5)" sub="↺ = item inversé dans le score. Rouge = pas du tout d'accord, vert = tout à fait d'accord.">
          <Likert name="echelles-likert" rows={d.data.likert.map((l) => ({ label: l.label, counts: l.counts, reversed: l.reversed }))} /></Card>}
        {tab === "scores" && <div className="stack">{d.data.scores.map((s) => (
          <Card key={s.var} title={s.title} sub={`n = ${s.n}`}>
            <div className="grid g2">
              <div><Table head={["Issue", "n", "Moyenne", "ET", "Médiane"]} num={[1, 2, 3, 4]} rows={s.groups.map((g) => [<span key="l" style={{ color: OUTCOME_COLORS[g.label] }}>● {g.label}</span>, g.n, nf(g.mean), nf(g.sd), nf(g.median)])} />
                <div className="small" style={{ marginTop: 10 }}>{s.anova ? <>ANOVA : F({s.anova.df1}, {s.anova.df2}) = {nf(s.anova.F)}, p = {pf(s.anova.p)}, η² = {nf(s.anova.eta2)} · Kruskal-Wallis p = {pf(s.kruskal?.p)}</> : "Effectifs insuffisants pour comparer."}</div>
                {s.posthoc.length > 0 && <div className="note" style={{ marginTop: 6 }}>Tukey : {s.posthoc.map((p) => `${p.a} vs ${p.b} (Δ ${nf(p.diff)}, p ${pf(p.p)})`).join(" ; ")}</div>}</div>
              <Hist name={`hist-${s.var}`} edges={s.histogram.edges} counts={s.histogram.counts} />
            </div>
          </Card>))}</div>}
      </>)}</Gate>}
      {tab === "croise" && <Gate loading={c.loading} error={c.error} data={c.data}>{c.data && <div className="stack">{c.data.map((t) => (
        <Card key={t.var} title={t.title} sub={t.test ? `χ²(${t.test.dof}) = ${nf(t.test.chi2)} · p = ${pf(t.test.p)}${t.test.mc_p != null ? ` · p Monte-Carlo = ${pf(t.test.mc_p)}` : ""} · V de Cramér corrigé = ${nf(t.test.cramers_v)}` : "Test non calculable"}>
          {t.test?.warning && <div className="callout warn" style={{ marginBottom: 10 }}>{t.test.warning}</div>}
          <Table head={["", ...t.columns.map((x) => x + " (%)"), "Total"]} num={t.columns.map((_, i) => i + 1).concat([t.columns.length + 1])} rows={t.table.map((r) => [r.value, ...r.counts.map((n, i) => `${n} (${pct(r.row_pct[i])})`), r.total])} />
        </Card>))}</div>}</Gate>}
    </>
  );
}
