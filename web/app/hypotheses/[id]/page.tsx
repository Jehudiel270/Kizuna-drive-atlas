"use client";
import { use } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { nf, orf, pf } from "@/lib/fmt";
import { Alerts, Badge, Card, Gate, PageHead, Table, VerdictBadge } from "@/components/ui";
import { COLORS, Forest, Lines } from "@/components/charts";
import type { Hyp } from "../page";

type Detail = { hypothesis: Hyp; robustness: any[]; power: any; models: Record<string, any>; warnings: { level: string; text: string }[]; n_model: number; events: number; epv: number | null; method: string; alpha: number };
const PAL = [COLORS.bad, COLORS.accent, COLORS.teal, COLORS.violet];

export default function HypPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, loading } = useApi<Detail>(`/analysis/hypotheses/${id}`, [id]);
  return (
    <Gate loading={loading} error={error} data={data}>{data && <Body d={data} />}</Gate>
  );
}

function Body({ d }: { d: Detail }) {
  const h = d.hypothesis, ex = h.extra || {};
  const curves: Record<string, { level: string; points: { x: number; p: number }[] }[]> | undefined = ex.curves;
  const model = h.id === "H3" ? "C" : h.id === "H4" ? "D" : h.id === "H1" ? "A" : "B";
  const coefs: any[] = d.models[model]?.coefficients ?? [];
  return (
    <div className="stack">
      <PageHead title={`${h.id} — ${h.qs} · ${h.os}`} right={<VerdictBadge v={h.verdict} />}>{h.statement}</PageHead>
      <div className="grid g3">
        <Card title="Question de recherche"><p className="small">{h.question}</p></Card>
        <Card title="Objectif"><p className="small">{h.objective}</p></Card>
        <Card title="Test prévu au protocole"><p className="small">{h.test}</p><p className="note">Sens attendu : {h.expected === "+" ? "augmente le risque d'échec" : "réduit le risque d'échec / effet modérateur négatif"}.</p></Card>
      </div>

      <Card title="Verdict" right={<Badge cls={h.verdict === "supported" ? "ok" : h.verdict === "partial" ? "warn" : h.verdict === "contradicted" ? "bad" : ""}>{h.verdict_label}</Badge>}>
        {!h.testable ? <div className="callout warn">{h.reason}</div> : (<>
          <div className="grid g4" style={{ marginBottom: 12 }}>
            <div><div className="note">{h.primary?.or != null ? "Rapport de cotes (par ET)" : "Test du rapport de vraisemblance"}</div><div className="hid">{h.primary?.or != null ? nf(h.primary.or) : `χ² = ${nf(h.primary?.stat)}`}</div><div className="note">{h.primary?.or != null ? `IC 95 % [${nf(h.primary.ci_low)} ; ${nf(h.primary.ci_high)}]` : `ddl = ${h.primary?.df}`}</div></div>
            <div><div className="note">p brut</div><div className="hid">{pf(h.primary?.p)}</div></div>
            <div><div className="note">p ajusté (Holm, 5 tests)</div><div className="hid">{pf(h.p_holm)}</div></div>
            <div><div className="note">Effectif / échecs</div><div className="hid">{h.n} / {h.events}</div></div>
          </div>
          <p>{h.interpretation}</p>
          <p className="note">Règle de décision : {h.verdict_text.replace(/\.+$/, "")}.</p>
        </>)}
      </Card>

      {h.testable && h.id === "H3" && <Card title="Effets d'interaction du soutien" sub="OR < 1 : plus le soutien est élevé, plus l'effet du facteur de risque diminue (modération négative attendue).">
        <Forest name="h3-interactions" rows={h.details.map((r: any) => ({ label: r.label, or: r.or, ci_low: r.ci_low, ci_high: r.ci_high, p: r.p }))} />
      </Card>}
      {h.testable && h.id === "H4" && <>
        <Card title="Effet de la gouvernance centralisée selon la formalisation" sub="OR de la gouvernance (par ET) dans chaque catégorie de formalisation. Attendu : effet plus fort dans les entreprises informelles/familiales.">
          <Forest name="h4-effets-simples" rows={[...(ex.slopes ?? []), ...(ex.family_slopes ?? [])].map((r: any) => ({ label: `${r.category} (n = ${r.n})${r.small ? " ⚠ petit effectif" : ""}`, or: r.or, ci_low: r.ci_low, ci_high: r.ci_high, p: r.p }))} />
        </Card>
        <Card title="Tests complémentaires">
          <Table head={["Test", "Résultat", "p"]} num={[2]} rows={[
            ["Interaction globale gouvernance × formalisation (LR)", `χ²(${h.primary?.df}) = ${nf(h.primary?.stat)}`, pf(h.primary?.p)],
            ...(ex.trend_lr ? [["Tendance linéaire (informel → formel)", `χ²(${ex.trend_lr.df}) = ${nf(ex.trend_lr.stat)} ; OR d'interaction ${nf(ex.trend?.or)}`, pf(ex.trend_lr.p)]] : []),
            ...(ex.family_interaction ? [["Gouvernance × propriété familiale", `OR d'interaction ${nf(ex.family_interaction.or)} [${nf(ex.family_interaction.ci_low)} ; ${nf(ex.family_interaction.ci_high)}]`, pf(ex.family_interaction.p)]] : []),
          ]} />
        </Card>
      </>}
      {curves && Object.keys(curves).length > 0 && <Card title="Probabilité prédite d'échec" sub={h.id === "H3" ? "Selon chaque facteur de risque, pour un soutien de la direction faible (−1 ET) ou élevé (+1 ET). Des courbes qui s'écartent = modération." : "Selon la gouvernance centralisée, pour chaque niveau de formalisation. Des pentes différentes = modération."}>
        <div className="grid g2">{Object.entries(curves).map(([k, cs]) => (
          <div key={k}><h3 style={{ marginBottom: 6 }}>{k}</h3>
            <Lines name={`${h.id}-${k}`} xLabel={`${k} (écarts-types)`} yLabel="P(échec)" series={cs.map((c, i) => ({ name: c.level, color: PAL[i % PAL.length], points: c.points.map((p) => ({ x: p.x, y: p.p })) }))} /></div>))}</div>
        <p className="note">Probabilités standardisées sur l'échantillon (autres variables à leurs valeurs observées).</p>
      </Card>}

      {h.testable && h.id !== "H3" && h.id !== "H4" && <Card title="Toutes les estimations du modèle" sub={`Modèle ${model} · méthode : ${d.method}`}>
        <Forest name={`${h.id}-modele`} rows={coefs.filter((c) => !c.term.startsWith("Intercept")).map((c) => ({ label: c.label, or: c.or, ci_low: c.ci_low, ci_high: c.ci_high, p: c.p }))} />
      </Card>}
      {h.testable && (h.id === "H3" || h.id === "H4") && <Card title={`Coefficients du modèle ${model}`}>
        <Table head={["Terme", "OR", "IC 95 %", "p"]} num={[1, 3]} rows={coefs.filter((c) => !c.term.startsWith("Intercept")).map((c) => [c.label, nf(c.or), `[${nf(c.ci_low)} ; ${nf(c.ci_high)}]`, pf(c.p)])} />
      </Card>}

      {d.robustness.length > 0 && <Card title="Robustesse : la conclusion tient-elle si on change de spécification ?" sub={h.robustness_summary ? `${h.robustness_summary.sign_ok}/${h.robustness_summary.specs_tested} spécifications dans le sens attendu · ${h.robustness_summary.significant_expected} significatives` : undefined}>
        <Table head={["Spécification", "Description", "Estimation", "p", "Sens attendu"]} num={[3]} rows={d.robustness.map((r: any) => [r.spec, <span key="d" className="note">{r.desc}</span>, r.testable ? (r.or != null ? orf(r) : r.stat != null ? `LR χ²(${r.df}) = ${nf(r.stat)}` : "—") : <span key="x" className="note">non estimable</span>, r.testable ? pf(r.p) : "—", r.testable ? (r.sign_ok ? <Badge key="s" cls="ok">oui</Badge> : <Badge key="s" cls="warn">non</Badge>) : "—"])} />
      </Card>}
      {d.power && (d.power.mde_80 != null) && <Card title="Puissance">
        <p className="small">Avec n = {d.n_model}, cette étude détecte avec 80 % de puissance un OR d'au moins <b>{nf(d.power.mde_80)}</b> par ET{d.power.observed_or ? <> ; OR observé : {nf(d.power.observed_or)}{d.power.achieved_power != null ? ` (puissance atteinte ≈ ${Math.round(d.power.achieved_power * 100)} %)` : ""}</> : null}. Un résultat non significatif sous ce seuil <b>ne prouve pas l'absence d'effet</b>.</p>
      </Card>}
      <Alerts items={d.warnings} />
      <div className="row">{["H1", "H2", "H3", "H4", "H5"].filter((x) => x !== h.id).map((x) => <Link key={x} className="btn sm" href={`/hypotheses/${x}`}>{x}</Link>)}</div>
    </div>
  );
}
