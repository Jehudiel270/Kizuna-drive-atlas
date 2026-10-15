"use client";
import { useApi } from "@/lib/api";
import { nf } from "@/lib/fmt";
import { Badge, Card, Gate, PageHead, Table } from "@/components/ui";

type Rel = { construct: string; label: string; note: string | null; n: number; k: number; threshold: number; alpha: number | null; alpha_ci: [number | null, number | null]; omega: number | null; mean_interitem_r: number | null; spearman_brown: number | null; status: string; status_text?: string;
  items: { name: string; label: string; reversed: boolean; mean: number; sd: number; item_rest_r: number; alpha_if_deleted: number }[] };

export default function Fiabilite() {
  const { data, error, loading } = useApi<Rel[]>("/analysis/fiabilite");
  return (
    <>
      <PageHead title="Fiabilité des échelles">Le protocole (4.10) exige un α de Cronbach d'au moins 0,70 pour les échelles multi-items. Les items « ↺ » sont inversés avant calcul. Un score non fiable ne peut pas porter une hypothèse.</PageHead>
      <Gate loading={loading} error={error} data={data}>{data && (
        <div className="stack">
          {data.map((r) => (
            <Card key={r.construct} title={r.label} right={<Badge cls={r.status === "ok" ? "ok" : r.status === "faible" ? "warn" : ""}>{r.status === "ok" ? "conforme" : r.status === "faible" ? "sous le seuil" : "non calculable"}</Badge>}
              sub={r.note ?? undefined}>
              <div className="grid g4" style={{ marginBottom: 12 }}>
                <div><div className="note">α de Cronbach</div><div className="hid">{nf(r.alpha)}</div><div className="note">IC 95 % [{nf(r.alpha_ci[0])} ; {nf(r.alpha_ci[1])}]</div></div>
                <div><div className="note">ω total</div><div className="hid">{nf(r.omega)}</div></div>
                <div><div className="note">Corrélation inter-items moyenne</div><div className="hid">{nf(r.mean_interitem_r)}</div>{r.spearman_brown != null && <div className="note">Spearman-Brown {nf(r.spearman_brown)}</div>}</div>
                <div><div className="note">Effectif / items</div><div className="hid">{r.n} / {r.k}</div></div>
              </div>
              {r.status_text && <div className={`callout ${r.status === "faible" ? "warn" : "ok"}`} style={{ marginBottom: 12 }}>{r.status_text}</div>}
              <Table head={["Item", "Moyenne", "ET", "Corrél. item-reste", "α si retiré"]} num={[1, 2, 3, 4]}
                rows={r.items.map((i) => [`${i.reversed ? "↺ " : ""}${i.label}`, nf(i.mean), nf(i.sd), nf(i.item_rest_r), nf(i.alpha_if_deleted)])} />
            </Card>
          ))}
        </div>
      )}</Gate>
    </>
  );
}
