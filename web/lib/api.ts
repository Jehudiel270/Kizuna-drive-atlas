"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export const BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

const safe = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string | null) => { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* stockage indisponible */ } },
};
export const getToken = () => safe.get("kz_token");
export const setToken = (t: string | null) => safe.set("kz_token", t);
export const getSnap = () => safe.get("kz_snap");
export const setSnapStore = (s: string | null) => safe.set("kz_snap", s);

const SNAP_PATHS = [/^\/analysis/, /^\/report/, /^\/quali\/(answers|synthesis)/];

export function withSnap(path: string, snap: string | null): string {
  if (!snap || !SNAP_PATHS.some((r) => r.test(path))) return path;
  return path + (path.includes("?") ? "&" : "?") + "snapshot=" + snap;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

function detailText(d: unknown): string {
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && "errors" in d) return (d as { errors: string[] }).errors.join(" ; ");
  return JSON.stringify(d);
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; snap?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body = init.body;
  if (init.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.json); }
  const url = BASE + (init.snap === false ? path : withSnap(path, getSnap()));
  let res: Response;
  try { res = await fetch(url, { ...init, headers, body }); }
  catch { throw new ApiError(0, "API injoignable. Vérifier NEXT_PUBLIC_API_URL et que l'API est démarrée."); }
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/login")) {
    setToken(null);
    if (!location.pathname.startsWith("/login")) location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = detailText(j.detail ?? j); } catch { /* corps non JSON */ }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("json") ? await res.json() : await res.text()) as T;
}

export async function download(path: string, filename: string) {
  const t = getToken();
  const res = await fetch(BASE + withSnap(path, getSnap()), { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (!res.ok) { let m = res.statusText; try { m = (await res.json()).detail || m; } catch { /* */ } throw new ApiError(res.status, String(m)); }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export type Me = { email: string; name: string; role: string; demo: boolean };
export type SnapshotInfo = { id: number; name: string; created_at: string; n_rows: number; sha256: string; plan_hash: string; note: string };
export type Ctx = { me: Me | null; snapshot: string | null; setSnapshot: (s: string | null) => void; snapshots: SnapshotInfo[]; reloadSnapshots: () => void };
export const AppCtx = createContext<Ctx>({ me: null, snapshot: null, setSnapshot: () => {}, snapshots: [], reloadSnapshots: () => {} });
export const useApp = () => useContext(AppCtx);

export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const { snapshot } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((x) => x + 1), []);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true); setError(null);
    api<T>(path).then((d) => { if (live) { setData(d); setLoading(false); } })
      .catch((e: ApiError) => { if (live) { setError(e); setLoading(false); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, snapshot, tick, ...deps]);
  return { data, error, loading, reload };
}
