"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Line, OrbitControls, QuadraticBezierLine, Stars } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

export type SNode = { id: string; label: string; pos: [number, number, number]; color: string; size: number; tag?: string };
export type SEdge = { id: string; a: string; b: string; color: string; width: number; dash?: boolean; opacity?: number; curve?: number; arrow?: boolean; label?: string };

function Node({ n, selected, dim, labels, onPick }: { n: SNode; selected: boolean; dim: boolean; labels: boolean; onPick: (id: string) => void }) {
  const ref = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  useFrame((s) => { if (ref.current) { const k = (selected || hover ? 1.18 : 1) + Math.sin(s.clock.elapsedTime * 1.6 + n.pos[0]) * 0.025; ref.current.scale.setScalar(k); } });
  return (
    <group position={n.pos}>
      <mesh ref={ref} onClick={(e) => { e.stopPropagation(); onPick(n.id); }} onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }} onPointerOut={() => { setHover(false); document.body.style.cursor = ""; }}>
        <sphereGeometry args={[n.size, 40, 40]} />
        <meshStandardMaterial color={n.color} emissive={n.color} emissiveIntensity={selected || hover ? 0.9 : 0.45} roughness={0.25} metalness={0.2} transparent opacity={dim ? 0.28 : 1} />
      </mesh>
      <mesh scale={1.55}><sphereGeometry args={[n.size, 24, 24]} /><meshBasicMaterial color={n.color} transparent opacity={dim ? 0.02 : 0.09} depthWrite={false} /></mesh>
      {labels && (
        <Html center distanceFactor={11} position={[0, n.size + 0.42, 0]} style={{ pointerEvents: "none", opacity: dim ? 0.35 : 1 }} zIndexRange={[5, 0]}>
          <div style={{ color: "#eaf1ff", fontSize: 13, fontWeight: 500, whiteSpace: "nowrap", textShadow: "0 1px 6px #000, 0 0 2px #000", textAlign: "center" }}>
            {n.tag && <div style={{ fontSize: 10, letterSpacing: ".12em", color: n.color, textTransform: "uppercase" }}>{n.tag}</div>}{n.label}
          </div>
        </Html>
      )}
    </group>
  );
}

function Arrow({ from, to, color, size }: { from: THREE.Vector3; to: THREE.Vector3; color: string; size: number }) {
  const { pos, quat } = useMemo(() => {
    const dir = to.clone().sub(from); const len = dir.length(); dir.normalize();
    const p = to.clone().sub(dir.clone().multiplyScalar(size + 0.22));
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    return { pos: p, quat: q, len };
  }, [from, to, size]);
  return <mesh position={pos} quaternion={quat}><coneGeometry args={[0.13, 0.36, 16]} /><meshBasicMaterial color={color} /></mesh>;
}

function Edge({ e, nodes, selected, dim, onPick }: { e: SEdge; nodes: Map<string, SNode>; selected: boolean; dim: boolean; onPick: (id: string) => void }) {
  const A = nodes.get(e.a), B = nodes.get(e.b);
  if (!A || !B) return null;
  const a = new THREE.Vector3(...A.pos), b = new THREE.Vector3(...B.pos);
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const off = e.curve ?? 0;
  if (off) mid.add(new THREE.Vector3(0, off, off * 0.4));
  const op = (e.opacity ?? 0.9) * (dim ? 0.18 : 1);
  const w = e.width + (selected ? 1.6 : 0);
  return (
    <group onClick={(ev) => { ev.stopPropagation(); onPick(e.id); }}>
      {off ? <QuadraticBezierLine start={a} end={b} mid={mid} color={e.color} lineWidth={w} dashed={e.dash} dashSize={0.25} gapSize={0.18} transparent opacity={op} />
        : <Line points={[a, b]} color={e.color} lineWidth={w} dashed={e.dash} dashSize={0.25} gapSize={0.18} transparent opacity={op} />}
      {e.arrow && !off && <Arrow from={a} to={b} color={e.color} size={B.size} />}
    </group>
  );
}

export default function Scene3D({ nodes, edges, labels = true, rotate = true, selected, onSelect, extent = 8 }: {
  nodes: SNode[]; edges: SEdge[]; labels?: boolean; rotate?: boolean; selected: string | null; onSelect: (id: string | null) => void; extent?: number;
}) {
  const map = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const sel = selected;
  const selEdge = edges.find((e) => e.id === sel);
  const touching = (id: string) => (sel === null ? true : id === sel || (selEdge ? selEdge.a === id || selEdge.b === id : edges.some((e) => (e.a === sel || e.b === sel) && (e.a === id || e.b === id))));
  return (
    <Canvas camera={{ position: [0, 1.5, extent * 1.9], fov: 48 }} dpr={[1, 2]} onPointerMissed={() => onSelect(null)} gl={{ antialias: true, preserveDrawingBuffer: true }}>
      <color attach="background" args={["#070c18"]} />
      <fog attach="fog" args={["#070c18", 14, 42]} />
      <ambientLight intensity={0.55} />
      <pointLight position={[8, 10, 10]} intensity={90} color="#9ec5ff" />
      <pointLight position={[-9, -6, -8]} intensity={60} color="#a98bff" />
      <Stars radius={60} depth={40} count={1400} factor={3} fade speed={0.4} />
      <gridHelper args={[40, 40, "#16264a", "#101c38"]} position={[0, -extent * 0.62, 0]} />
      {edges.map((e) => <Edge key={e.id} e={e} nodes={map} selected={sel === e.id} dim={sel !== null && sel !== e.id && !(e.a === sel || e.b === sel)} onPick={onSelect} />)}
      {nodes.map((n) => <Node key={n.id} n={n} selected={sel === n.id} dim={sel !== null && !touching(n.id)} labels={labels} onPick={onSelect} />)}
      <OrbitControls enableDamping dampingFactor={0.08} autoRotate={rotate && sel === null} autoRotateSpeed={0.55} minDistance={5} maxDistance={40} />
    </Canvas>
  );
}
