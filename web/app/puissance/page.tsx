"use client";
import { useApi } from "@/lib/api";
import { nf, pct } from "@/lib/fmt";
import { Card, Gate, PageHead, Table } from "@/components/ui";

type P = { power: Record<string, any>; target: { min: number; max: number }; n_model: number };
const NAMES: Record<string, string> = { H1: "H1 · Gouvernance", H2: "H2 · Compétences", H5: "H5 · Communication", H3: "H3 · Interactions du soutien" };

export default function Puissance() {
  const { data, error, loading } = useApi<P>("/analysis/puissance");
  return (
    <>
      <PageHead title="Puissance statistique">Avec 150 à 180 projets et un taux d'échec voisin de 40 %, quelle taille d'effet l'étude peut-elle détecter ? C'est la limite honnête à écrire dans le rapport : un résultat « non significatif » sous ce seuil ne prouve rien.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (
        <div className="stack">
          <div className="grid g3">
            <Card title="Projets dans le modèle"><div className="hid">{data.n_model}</div><div className="note">cible protocole : {data.target.min}–{data.target.max}</div></Card>
            <Card title="Taux d'échec observé"><div className="hid">{data.power._prevalence != null ? pct(data.power._prevalence) : "—"}</div></Card>
            <Card title="Lecture"><p className="small">« OR détectable » = plus petit rapport de cotes (par écart-type du facteur) vu comme significatif 8 fois sur 10 (approximation de Hsieh et al., ajustée pour la corrélation avec les autres prédicteurs).</p></Card>
          </div>
          <Card title="Plus petit effet détectable">
            <Table head={["Hypothèse", "R² avec les autres prédicteurs", "OR détectable (80 %)", "OR détectable (90 %)", "OR observé", "Puissance atteinte"]} num={[1, 2, 3, 4, 5]}
              rows={Object.entries(data.power).filter(([k]) => !k.startsWith("_")).map(([k, v]: [string, any]) => [NAMES[k] ?? k, nf(v.r2_others), nf(v.mde_80), nf(v.mde_90), nf(v.observed_or), v.achieved_power != null ? pct(v.achieved_power) : "—"])} />
            <p className="note" style={{ marginTop: 8 }}>Les interactions (H3, H4) exigent bien plus de données que les effets principaux : leur « non-significativité » est probablement un manque de puissance, pas une absence d'effet.</p>
          </Card>
        </div>
      )}</Gate>
    </>
  );
}
