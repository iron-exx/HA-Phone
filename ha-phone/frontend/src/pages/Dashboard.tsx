import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Phone, Network, PhoneCall, RefreshCw, ArrowUpCircle, Router, Voicemail } from "lucide-react";

interface UpdateInfo {
  version: string;
  version_latest: string;
  update_available: boolean;
}
interface ExtensionStatus {
  number: string;
  status: "Online" | "Offline";
}

const HISTORY_LEN = 40; // ~3.3 min at 5s sampling

// ── Inline SVG donut gauge ───────────────────────────────────────────────────
function Donut({
  value, max, color, label, sub,
}: { value: number; max: number; color: string; label: string; sub?: string }) {
  const size = 132, stroke = 12;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const dash = circ * pct;
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke="rgba(255,255,255,0.07)" strokeWidth={stroke} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={color} strokeWidth={stroke} strokeLinecap="round"
            strokeDasharray={`${dash} ${circ - dash}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: "stroke-dasharray 0.6s ease", filter: `drop-shadow(0 0 6px ${color}66)` }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-semibold" style={{ color }}>{value}</span>
          <span className="font-mono text-xs text-muted-foreground">/ {max}</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">{label}</p>
        {sub && <p className="mt-0.5 text-xs" style={{ color }}>{sub}</p>}
      </div>
    </div>
  );
}

// ── Inline SVG live area sparkline ───────────────────────────────────────────
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const w = 640, h = 150, pad = 6;
  const max = Math.max(1, ...data);
  const n = data.length;
  const pts = data.map((v, i) => {
    const x = n <= 1 ? w : (i / (n - 1)) * w;
    const y = h - pad - (v / max) * (h - 2 * pad);
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${w} ${h} L 0 ${h} Z`;
  const gid = "spark-fill";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-full w-full">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((g) => (
        <line key={g} x1="0" y1={h * g} x2={w} y2={h * g} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      ))}
      {n > 0 && <path d={area} fill={`url(#${gid})`} />}
      {n > 0 && <path d={line} fill="none" stroke={color} strokeWidth="2.5"
        style={{ filter: `drop-shadow(0 0 5px ${color}88)` }} />}
    </svg>
  );
}

function TrunkPill({ status }: { status: string }) {
  const map: Record<string, { c: string; t: string }> = {
    Registered: { c: "#22C55E", t: "REGISTERED" },
    Unreachable: { c: "#EAB308", t: "UNREACHABLE" },
    Unregistered: { c: "#EAB308", t: "UNREGISTERED" },
  };
  const s = map[status] || { c: "#64748B", t: (status || "UNKNOWN").toUpperCase() };
  const pulse = status === "Registered";
  return (
    <div className="flex items-center gap-2.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${pulse ? "dot-pulse" : ""}`}
        style={{ background: s.c }} />
      <span className="font-mono text-xl font-semibold" style={{ color: s.c }}>{s.t}</span>
    </div>
  );
}

export default function Dashboard() {
  const [extOnline, setExtOnline] = useState(0);
  const [extTotal, setExtTotal] = useState(0);
  const [trunkStatus, setTrunkStatus] = useState("UNKNOWN");
  const [activeCalls, setActiveCalls] = useState(0);
  const [deviceCount, setDeviceCount] = useState(0);
  const [history, setHistory] = useState<number[]>([]);
  const [err, setErr] = useState(false);

  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [updating, setUpdating] = useState(false);
  const [updateDone, setUpdateDone] = useState(false);
  const histRef = useRef<number[]>([]);

  function fetchExtensions() {
    Promise.all([
      fetch("/api/extensions/status").then((r) => r.json()) as Promise<ExtensionStatus[]>,
      fetch("/api/extensions").then((r) => r.json()) as Promise<unknown[]>,
    ])
      .then(([statuses, all]) => {
        setExtOnline(statuses.filter((e) => e.status === "Online").length);
        setExtTotal(Array.isArray(all) ? all.length : 0);
      })
      .catch(() => setErr(true));
  }
  function fetchTrunk() {
    fetch("/api/trunk/status").then((r) => r.json())
      .then((d: { status: string }) => setTrunkStatus(d.status)).catch(() => setErr(true));
  }
  function fetchCalls() {
    fetch("/api/status/active-calls").then((r) => r.json())
      .then((d: { count: number }) => {
        setActiveCalls(d.count);
        const next = [...histRef.current, d.count].slice(-HISTORY_LEN);
        histRef.current = next;
        setHistory(next);
      })
      .catch(() => setErr(true));
  }
  function fetchDevices() {
    fetch("/api/provisioning/devices").then((r) => r.json())
      .then((d: unknown[]) => setDeviceCount(Array.isArray(d) ? d.length : 0)).catch(() => {});
  }
  function fetchUpdate() {
    fetch("/api/update/info").then((r) => (r.ok ? r.json() : null))
      .then((d: UpdateInfo | null) => d && setUpdateInfo(d)).catch(() => {});
  }

  function startUpdate() {
    setUpdating(true);
    fetch("/api/update/start", { method: "POST" })
      .then((r) => (r.ok ? setUpdateDone(true) : setUpdating(false)))
      .catch(() => setUpdating(false));
  }

  useEffect(() => {
    fetchExtensions(); fetchTrunk(); fetchCalls(); fetchDevices(); fetchUpdate();
    const a = setInterval(fetchExtensions, 10000);
    const b = setInterval(fetchTrunk, 15000);
    const c = setInterval(fetchCalls, 5000);
    const d = setInterval(fetchDevices, 30000);
    return () => { clearInterval(a); clearInterval(b); clearInterval(c); clearInterval(d); };
  }, []);

  const trunkColor = trunkStatus === "Registered" ? "#22C55E"
    : (trunkStatus === "Unreachable" || trunkStatus === "Unregistered") ? "#EAB308" : "#64748B";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Systemstatus in Echtzeit</p>
      </div>

      {updateInfo?.update_available && !updateDone && (
        <div className="glass flex items-center justify-between gap-4 rounded-xl px-5 py-4"
          style={{ borderColor: "rgba(234,179,8,0.25)", background: "rgba(234,179,8,0.06)" }}>
          <div className="flex items-center gap-3">
            <ArrowUpCircle className="h-4 w-4 shrink-0 text-yellow-400" />
            <span className="text-sm text-slate-200">
              Update verfügbar: <span className="font-mono font-semibold text-yellow-300">{updateInfo.version_latest}</span>
              <span className="ml-2 text-xs text-muted-foreground">(aktuell: {updateInfo.version})</span>
            </span>
          </div>
          <Button size="sm" disabled={updating} onClick={startUpdate} className="shrink-0 cursor-pointer"
            style={{ background: "rgba(234,179,8,0.15)", border: "1px solid rgba(234,179,8,0.3)", color: "#FCD34D" }}>
            {updating ? <><RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />Aktualisiert…</> : "Jetzt aktualisieren"}
          </Button>
        </div>
      )}
      {updateDone && (
        <div className="glass flex items-center gap-3 rounded-xl px-5 py-4"
          style={{ borderColor: "rgba(34,197,94,0.25)", background: "rgba(34,197,94,0.06)" }}>
          <span className="dot-pulse inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-sm text-emerald-300">Update gestartet — nach ~15 Min neu laden.</span>
        </div>
      )}
      {err && (
        <div className="glass flex items-center gap-3 rounded-xl px-5 py-4"
          style={{ borderColor: "rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.06)" }}>
          <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
          <span className="text-sm text-red-300">Asterisk nicht erreichbar — PBX startet evtl. noch.</span>
        </div>
      )}

      {/* Hero: live active-calls chart + trunk panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="glass relative overflow-hidden rounded-xl p-6 lg:col-span-2">
          <div className="mb-1 flex items-center gap-2">
            <PhoneCall className="h-4 w-4 text-sky-400" />
            <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Aktive Anrufe</span>
          </div>
          <div className="mb-4 font-mono text-4xl font-semibold text-sky-300">{activeCalls}</div>
          <div className="h-[150px] w-full">
            <Sparkline data={history} color="#38BDF8" />
          </div>
        </div>

        <div className="glass flex flex-col justify-center gap-4 rounded-xl p-6">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4" style={{ color: trunkColor }} />
            <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Trunk Status</span>
          </div>
          <TrunkPill status={trunkStatus} />
          <div className="mt-2 h-px" style={{ background: "rgba(255,255,255,0.06)" }} />
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Provisionierte Geräte</span>
            <span className="font-mono font-semibold text-violet-300">{deviceCount}</span>
          </div>
        </div>
      </div>

      {/* Gauges */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="glass flex items-center justify-center rounded-xl p-6">
          <Donut value={extOnline} max={Math.max(extTotal, extOnline)} color="#A78BFA"
            label="Nebenstellen online" sub={`${extTotal} gesamt`} />
        </div>
        <div className="glass flex items-center justify-center rounded-xl p-6">
          <Donut value={activeCalls} max={Math.max(4, activeCalls)} color="#38BDF8"
            label="Aktive Gespräche" />
        </div>
        <div className="glass flex flex-col items-center justify-center gap-3 rounded-xl p-6">
          <div className="flex h-[132px] w-[132px] items-center justify-center rounded-full"
            style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.15)" }}>
            <div className="text-center">
              <Router className="mx-auto mb-1 h-6 w-6 text-violet-300" />
              <span className="font-mono text-2xl font-semibold text-violet-300">{deviceCount}</span>
            </div>
          </div>
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">Geräte (Provisioning)</p>
        </div>
      </div>

      {/* Quick metric chips */}
      <div className="flex flex-wrap gap-4">
        <MetricChip icon={Phone} label="Nebenstellen" value={`${extOnline}/${extTotal}`} color="#A78BFA" />
        <MetricChip icon={PhoneCall} label="Aktive Anrufe" value={String(activeCalls)} color="#38BDF8" />
        <MetricChip icon={Router} label="Geräte" value={String(deviceCount)} color="#A78BFA" />
        <MetricChip icon={Voicemail} label="Trunk" value={trunkStatus === "Registered" ? "OK" : "—"} color={trunkColor} />
      </div>
    </div>
  );
}

function MetricChip({ icon: Icon, label, value, color }:
  { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <div className="glass flex min-w-40 flex-1 items-center gap-3 rounded-xl px-4 py-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-md"
        style={{ background: `${color}1f`, border: `1px solid ${color}33` }}>
        <Icon className="h-4 w-4" style={{ color }} />
      </div>
      <div>
        <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">{label}</p>
        <p className="font-mono text-lg font-semibold" style={{ color }}>{value}</p>
      </div>
    </div>
  );
}
