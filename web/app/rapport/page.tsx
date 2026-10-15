"use client";
import { useState } from "react";
import { download, useApi, useApp } from "@/lib/api";
import { Busy, Card, ErrorBox, Gate, PageHead, Table } from "@/components/ui";

type Prev = { blocks: { type: string; content: any[] }[] };

export default function Rapport() {
  const { data, error, loading } = useApi<Prev>("/report/preview");
  const { snapshot } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const dl = (p: string, f: string) => async () => { setErr(null); try { await download(p, f); } catch (e) { setErr((e as Error).message); } };
  return (
    <>
      <PageHead title="Rapport & exports">Le rapport d'analyse de collecte se génère à partir des chiffres calculés ici. Pour un rapport définitif, figer d'abord un instantané (Données → Instantanés figés), puis le sélectionner en haut de page.</PageHead>
      <div className="stack">
        {!snapshot && <div className="callout warn">Vous êtes sur les données courantes : elles changeront à chaque nouvelle réponse. Figez un instantané pour la version à remettre.</div>}
        <Card title="Télécharger">
          <div className="row">
            <Busy cls="btn primary" action={dl("/report/docx", "kizuna-rapport.docx")}>Rapport Word (.docx)</Busy>
            <Busy action={dl("/report/markdown", "kizuna-rapport.md")}>Markdown</Busy>
            <Busy action={dl("/report/xlsx", "kizuna-tableaux.xlsx")}>Tableaux Excel</Busy>
            <Busy action={dl("/report/package", "kizuna-reproductibilite.zip")}>Paquet de reproductibilité (.zip)</Busy>
          </div>
          <p className="note" style={{ marginTop: 8 }}>Le paquet contient : rapport (.md, .docx), tableaux (.xlsx), résultats JSON, données analysables pseudonymisées (sans e-mail ni texte libre), plan d'analyse et codebook (.yaml), graphes GraphML/GEXF et réseau exploratoire en CSV. Les graphiques individuels s'exportent en SVG/PNG au survol de chaque figure.</p>
          <ErrorBox error={err} />
        </Card>
        <Gate loading={loading} error={error} data={data}>{data && (
          <Card title="Aperçu du rapport">
            <div style={{ maxWidth: 860 }}>
              {data.blocks.map((b, i) => {
                const [c0, c1] = b.content;
                if (b.type === "title") return <h1 key={i} style={{ marginBottom: 10 }}>{c0}</h1>;
                if (b.type === "h1") return <h2 key={i} style={{ marginTop: 26, fontSize: 21 }}>{c0}</h2>;
                if (b.type === "h2") return <h3 key={i} style={{ marginTop: 18, fontSize: 16 }}>{c0}</h3>;
                if (b.type === "callout") return <div key={i} className="callout bad" style={{ margin: "10px 0" }}><b>{c0}</b></div>;
                if (b.type === "bullets") return <ul key={i}>{(c0 as string[]).map((t, j) => <li key={j}>{t}</li>)}</ul>;
                if (b.type === "table") return <div key={i} style={{ margin: "8px 0 14px" }}><Table head={c0} rows={c1} /></div>;
                return <p key={i}>{c0}</p>;
              })}
            </div>
          </Card>
        )}</Gate>
      </div>
    </>
  );
}
