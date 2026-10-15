"use client";
import { useApi } from "@/lib/api";
import { pct } from "@/lib/fmt";
import { Alerts, Card, Gate, PageHead, Stat, Table } from "@/components/ui";
import { Funnel, HBar, OUTCOME_COLORS, Timeline } from "@/components/charts";

type Dist = { value: string; n: number; pct: number; target: number | null; gap: number | null }[];
type Col = {
  target: { min: number; max: number }; n_total: number; n_analysable: number; n_model: number; funnel: { step: string; n: number }[];
  issue: Dist; secteur: Dist; taille: Dist; ville: Dist; mode: Dist; relais: Dist; enqueteurs: Dist; relais_hhi: number | null; relais_top_share: number | null;
  quota_cross: { rows: string[]; cols: string[]; values: number[][] }; timeline: { day: string; cum_total: number; cum_analysable: number }[] | null;
  quality: Record<string, number>; alerts: { level: string; text: string }[];
};
const bars = (d: Dist) => d.map((r) => ({ label: r.value, value: r.n, target: r.target }));

export default function Collecte() {
  const { data, error, loading } = useApi<Col>("/analysis/collecte");
  return (
    <>
      <PageHead title="Suivi de collecte">Échantillonnage par choix raisonné avec quotas (protocole 4.5) : suivre l'éligibilité, la diversité des secteurs/tailles, la dépendance à un relais et la qualité des réponses, <i>avant</i> qu'il soit trop tard pour corriger.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (
        <div className="stack">
          <div className="grid g4">
            <Stat v={data.n_total} l="soumissions" /><Stat v={data.n_analysable} l="projets analysables" /><Stat v={data.n_model} l="complets pour les modèles" />
            <Stat v={data.relais_hhi != null ? data.relais_hhi.toFixed(2).replace(".", ",") : "—"} l="concentration des relais (HHI, 1 = un seul relais)" tone={data.relais_top_share != null && data.relais_top_share > 0.3 ? "warn" : undefined} />
          </div>
          {data.alerts.length > 0 && <Alerts items={data.alerts} />}
          <div className="grid g2">
            <Card title="Entonnoir d'éligibilité"><Funnel steps={data.funnel} /></Card>
            <Card title="Progression cumulée" sub="Soumissions et projets analysables vs cible minimale"><Timeline data={data.timeline ?? []} target={data.target} /></Card>
          </div>
          <div className="grid g2">
            <Card title="Secteur d'activité" sub="Trait blanc = quota cible (à saisir dans le plan d'analyse)"><HBar name="secteur" rows={bars(data.secteur)} /></Card>
            <Card title="Taille de l'entreprise"><HBar name="taille" rows={bars(data.taille)} /></Card>
            <Card title="Issue du projet"><HBar name="issue" rows={data.issue.map((r) => ({ label: r.value, value: r.n, color: OUTCOME_COLORS[r.value] }))} /></Card>
            <Card title="Ville"><HBar name="ville" rows={bars(data.ville)} /></Card>
            <Card title="Relais ayant orienté vers les PME" sub="Un relais dominant biaise l'échantillon (seuil d'alerte : 30 %)"><HBar name="relais" rows={bars(data.relais).slice(0, 12)} /></Card>
            <Card title="Enquêteurs & mode de passation"><HBar name="enqueteurs" rows={bars(data.enqueteurs).slice(0, 10)} /><div style={{ height: 12 }} /><HBar name="mode" rows={bars(data.mode)} /></Card>
          </div>
          <Card title="Quotas secteur × taille" sub="Effectifs réels par cellule">
            <Table head={["Secteur \\ Taille", ...data.quota_cross.cols]} num={data.quota_cross.cols.map((_, i) => i + 1)} rows={data.quota_cross.rows.map((r, i) => [r, ...data.quota_cross.values[i]])} />
          </Card>
          <Card title="Qualité des réponses">
            <Table head={["Contrôle", "n"]} num={[1]} rows={[["Même note partout (réponses bâclées)", data.quality.straightlining], ["Doublons d'identifiant de répondant", data.quality.duplicates_respondent], ["Doublons d'e-mail", data.quality.duplicates_email], ["Issue incohérente", data.quality.incoherent_outcome], ["Habitués > employés", data.quality.habitues_gt_employes]]} />
            <p className="note" style={{ marginTop: 8 }}>Les cas douteux se traitent dans « Données &amp; Tally » (exclusion motivée et tracée).</p>
          </Card>
        </div>
      )}</Gate>
    </>
  );
}
