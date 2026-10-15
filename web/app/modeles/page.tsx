"use client";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { nf, pf } from "@/lib/fmt";
import { Alerts, Card, Gate, PageHead, Table, Tabs } from "@/components/ui";
import { COLORS, Forest, Lines } from "@/components/charts";

type M = { title: string; coefficients: any[]; diagnostics: any };
type Res = { models: Record<string, M>; n_model: number; events: number; epv: number | null; method: string; warnings: { level: string; text: string }[]; specs: { name: string; desc: string }[] };

export default function Modeles() {
  const { data, error, loading } = useApi<Res>("/analysis/modeles");
  const [k, setK] = useState("B");
  return (
    <>
      <PageHead title="Modèles & diagnostics">Régression logistique de l'échec du projet (échec partiel ou total = 1, succès = 0). Prédicteurs standardisés : un OR se lit « par écart-type ». Les diagnostics disent si on peut faire confiance aux estimations.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (() => {
        const keys = Object.keys(data.models); const m = data.models[keys.includes(k) ? k : keys[0]]; const dg = m?.diagnostics ?? {};
        return (
          <div className="stack">
            <Alerts items={data.warnings} />
            <Tabs value={k} onChange={setK} tabs={keys.map((x) => [x, `Modèle ${x}`] as [string, string])} />
            {m && <>
              <Card title={m.title} sub={`n = ${dg.n} · ${dg.events} échecs · ${dg.k} paramètres · EPV = ${nf(dg.epv, 1)} · méthode ${dg.method}`}>
                <Forest name={`modele-${k}`} rows={m.coefficients.filter((c) => !c.term.startsWith("Intercept")).map((c) => ({ label: c.label, or: c.or, ci_low: c.ci_low, ci_high: c.ci_high, p: c.p }))} />
                <div style={{ height: 12 }} />
                <Table head={["Terme", "Coef.", "ET", "OR", "IC 95 %", "p"]} num={[1, 2, 3, 5]} rows={m.coefficients.map((c) => [c.label, nf(c.coef, 3), nf(c.se, 3), nf(c.or), `[${nf(c.ci_low)} ; ${nf(c.ci_high)}]`, pf(c.p)])} />
              </Card>
              <div className="grid g2">
                <Card title="Qualité d'ajustement">
                  <Table head={["Indicateur", "Valeur"]} num={[1]} rows={[["AUC (discrimination)", nf(dg.auc)], ["R² de McFadden", nf(dg.mcfadden)], ["R² de Nagelkerke", nf(dg.nagelkerke)], ["AIC", nf(dg.aic, 1)], ["BIC", nf(dg.bic, 1)],
                    ["Hosmer-Lemeshow", dg.hosmer_lemeshow ? `χ²(${dg.hosmer_lemeshow.df}) = ${nf(dg.hosmer_lemeshow.stat)}, p = ${pf(dg.hosmer_lemeshow.p)}` : "—"], ["Convergence", dg.converged ? "oui" : "non"]]} />
                  {dg.notes?.length > 0 && <div className="callout warn" style={{ marginTop: 10 }}>{dg.notes.join(" ")}</div>}
                </Card>
                {dg.vif && <Card title="Colinéarité (VIF)" sub="Au-dessus de 5, deux prédicteurs se confondent : leurs effets séparés sont peu fiables."><Table head={["Terme", "VIF"]} num={[1]} rows={dg.vif.filter((v: any) => v.term !== "Intercept").map((v: any) => [v.term, <span key="v" style={{ color: v.vif > 5 ? "var(--bad)" : undefined }}>{nf(v.vif, 1)}</span>])} /></Card>}
              </div>
              <div className="grid g2">
                {dg.roc && <Card title="Courbe ROC" sub={`AUC = ${nf(dg.auc)}`}><Lines name={`roc-${k}`} xLabel="1 − spécificité" yLabel="sensibilité" xDomain={[0, 1]} diag series={[{ name: `Modèle ${k}`, color: COLORS.accent, points: dg.roc.map((p: any) => ({ x: p.fpr, y: p.tpr })) }]} /></Card>}
                {dg.hosmer_lemeshow?.bins && <Card title="Calibration" sub="Probabilité prédite vs taux d'échec observé par décile : sur la diagonale = bien calibré."><Lines name={`calib-${k}`} xLabel="probabilité prédite" yLabel="taux observé" xDomain={[0, 1]} diag series={[{ name: "Déciles", color: COLORS.teal, points: [...dg.hosmer_lemeshow.bins].sort((a: any, b: any) => a.mean_pred - b.mean_pred).map((p: any) => ({ x: p.mean_pred, y: p.obs_rate })) }]} /></Card>}
              </div>
            </>}
          </div>
        );
      })()}</Gate>
    </>
  );
}
