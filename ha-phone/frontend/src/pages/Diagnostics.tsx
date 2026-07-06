import { useEffect, useRef, useState } from "react";
import { Activity, Download, PhoneCall, ServerCog, Square, Trash2, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { DiagnosticsOverview } from "@/types/api";

interface TraceStatus {
  running: boolean;
  file_ready: boolean;
  size_bytes: number;
  started_at: number | null;
  file_mtime: number | null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatTimestamp(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function Diagnostics() {
  const [status, setStatus] = useState<TraceStatus>({ running: false, file_ready: false, size_bytes: 0, started_at: null, file_mtime: null });
  const [overview, setOverview] = useState<DiagnosticsOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchStatus() {
    try {
      const resp = await fetch("/api/trace/status");
      if (resp.ok) {
        const data: TraceStatus = await resp.json();
        setStatus(data);
      }
    } catch { /* ignore */ }
  }

  async function fetchOverview() {
    try {
      const resp = await fetch("/api/diagnostics/overview");
      if (resp.ok) {
        const data: DiagnosticsOverview = await resp.json();
        setOverview(data);
      }
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    fetchStatus();
    fetchOverview();
    pollRef.current = setInterval(() => {
      fetchStatus();
      fetchOverview();
    }, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Derive elapsed time from the backend-provided start timestamp, not a local counter.
  // A counter resets on every remount (tab switch) even though the capture keeps running;
  // anchoring to started_at keeps the displayed time correct across tab switches + reloads.
  useEffect(() => {
    if (status.running && status.started_at) {
      const startMs = status.started_at * 1000;
      const tick = () => setElapsed(Math.max(0, Math.round((Date.now() - startMs) / 1000)));
      tick();
      timerRef.current = setInterval(tick, 1000);
    } else {
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [status.running, status.started_at]);

  async function handleStart() {
    setLoading(true);
    try {
      const resp = await fetch("/api/trace/start", { method: "POST" });
      if (!resp.ok) throw new Error();
      setElapsed(0);
      await fetchStatus();
      toast.success("Aufzeichnung gestartet.");
    } catch {
      toast.error("Fehler beim Starten. tcpdump verfügbar?");
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    setLoading(true);
    try {
      const resp = await fetch("/api/trace/stop", { method: "POST" });
      if (!resp.ok) throw new Error();
      await fetchStatus();
      toast.success("Aufzeichnung gestoppt — Datei bereit.");
    } catch {
      toast.error("Fehler beim Stoppen.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDiscard() {
    try {
      await fetch("/api/trace/file", { method: "DELETE" });
      await fetchStatus();
      toast.success("Aufzeichnung gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  function handleDownload() {
    // Must include the HA ingress prefix manually: window.location.href bypasses the
    // fetch() wrapper in main.tsx that normally prepends it, so a root-absolute path
    // would hit the HA host root (404) instead of the add-on.
    const ingress = (window as unknown as { __INGRESS_PATH__?: string }).__INGRESS_PATH__ ?? "";
    window.location.href = `${ingress}/api/trace/download`;
  }

  function formatMicros(value: number | null): string {
    if (value === null) return "–";
    return `${(value / 1000).toFixed(1)} ms`;
  }

  const onlineExtensions = overview?.extensions.filter((item) => item.status === "Online").length ?? 0;
  const trunkDebugEntries = overview
    ? Object.entries(overview.trunk_debug).filter(([, value]) => String(value ?? "").trim() !== "")
    : [];

  return (
    <div className="space-y-8">

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Diagnose</h1>
        <p className="mt-1 text-sm text-muted-foreground">Netzwerk-Trace aufzeichnen und analysieren</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
              <ServerCog className="h-4 w-4 text-violet-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-muted-foreground">Trunk</p>
              <p className="text-lg font-semibold text-foreground">{overview?.trunk_status ?? "Lädt..."}</p>
            </div>
          </div>
          {trunkDebugEntries.length > 0 && (
            <div className="mt-4 space-y-2 text-xs text-muted-foreground">
              {trunkDebugEntries.slice(0, 4).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-3">
                  <span className="truncate">{key}</span>
                  <span className="truncate font-mono text-foreground">{String(value)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
              <Wifi className="h-4 w-4 text-emerald-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-muted-foreground">Nebenstellen online</p>
              <p className="text-lg font-semibold text-foreground">
                {onlineExtensions} / {overview?.extensions.length ?? 0}
              </p>
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
              <PhoneCall className="h-4 w-4 text-sky-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-muted-foreground">Aktive Gespräche</p>
              <p className="text-lg font-semibold text-foreground">{overview?.active_calls ?? 0}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="glass rounded-xl">
        <div
          className="flex items-center justify-between border-b px-6 py-4"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div>
            <p className="text-sm font-semibold text-foreground">Nebenstellen live</p>
            <p className="text-xs text-muted-foreground">Registrierung, Kontakt und Erreichbarkeit direkt aus Asterisk</p>
          </div>
        </div>
        <div className="overflow-x-auto p-6">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left text-xs uppercase tracking-widest text-muted-foreground">
                <th className="pb-3 font-medium">Nr.</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">Gerätezustand</th>
                <th className="pb-3 font-medium">Kontakte</th>
                <th className="pb-3 font-medium">Kontakt</th>
                <th className="pb-3 font-medium">Latenz</th>
                <th className="pb-3 font-medium">Kanäle</th>
              </tr>
            </thead>
            <tbody>
              {(overview?.extensions ?? []).map((extension) => (
                <tr key={extension.number} className="border-b border-white/5 last:border-0">
                  <td className="py-3 font-mono text-violet-300">{extension.number}</td>
                  <td className="py-3">
                    <span className={extension.status === "Online" ? "text-emerald-300" : "text-slate-400"}>
                      {extension.status}
                    </span>
                  </td>
                  <td className="py-3 text-muted-foreground">{extension.device_state || "–"}</td>
                  <td className="py-3 text-muted-foreground">
                    {extension.contacts}
                    {extension.contact_status ? ` · ${extension.contact_status}` : ""}
                  </td>
                  <td className="py-3 font-mono text-xs text-muted-foreground">{extension.contact_uri || "–"}</td>
                  <td className="py-3 text-muted-foreground">{formatMicros(extension.roundtrip_usec)}</td>
                  <td className="py-3 text-muted-foreground">{extension.active_channels}</td>
                </tr>
              ))}
              {(overview?.extensions.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-sm text-muted-foreground">
                    Noch keine Live-Daten für Nebenstellen verfügbar.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="glass rounded-xl">
        <div
          className="flex items-center justify-between border-b px-6 py-4"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div>
            <p className="text-sm font-semibold text-foreground">Aktive Kanäle</p>
            <p className="text-xs text-muted-foreground">Laufende Gespräche und ihr aktueller Dialplan-Pfad</p>
          </div>
        </div>
        <div className="overflow-x-auto p-6">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left text-xs uppercase tracking-widest text-muted-foreground">
                <th className="pb-3 font-medium">Kanal</th>
                <th className="pb-3 font-medium">Von</th>
                <th className="pb-3 font-medium">Nach</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">Kontext</th>
                <th className="pb-3 font-medium">App</th>
                <th className="pb-3 font-medium">Dauer</th>
              </tr>
            </thead>
            <tbody>
              {(overview?.channels ?? []).map((channel) => (
                <tr key={channel.channel} className="border-b border-white/5 last:border-0">
                  <td className="py-3 font-mono text-xs text-muted-foreground">{channel.channel}</td>
                  <td className="py-3 text-muted-foreground">
                    {[channel.caller_id_num, channel.caller_id_name].filter(Boolean).join(" " ) || "–"}
                  </td>
                  <td className="py-3 text-muted-foreground">
                    {[channel.connected_line_num, channel.connected_line_name].filter(Boolean).join(" " ) || channel.extension || "–"}
                  </td>
                  <td className="py-3 text-muted-foreground">{channel.state || "–"}</td>
                  <td className="py-3 font-mono text-xs text-muted-foreground">{channel.context || "–"}</td>
                  <td className="py-3 text-muted-foreground">{channel.application || "–"}</td>
                  <td className="py-3 text-muted-foreground">{channel.duration || "–"}</td>
                </tr>
              ))}
              {(overview?.channels.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-sm text-muted-foreground">
                    Im Moment laufen keine Gespräche.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Capture card */}
      <div className="glass rounded-xl">
        {/* Card header */}
        <div
          className="flex items-center gap-3 border-b px-6 py-4"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{
              background: status.running
                ? "rgba(239,68,68,0.12)"
                : "rgba(139,92,246,0.12)",
              border: `1px solid ${status.running ? "rgba(239,68,68,0.2)" : "rgba(139,92,246,0.2)"}`,
            }}
          >
            <Activity
              className="h-4 w-4"
              style={{ color: status.running ? "#F87171" : "#A78BFA" }}
            />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">SIP / RTP Netzwerk-Trace</p>
            <p className="text-xs text-muted-foreground">
              Port 5060, 5061 + UDP 10000–20000 · PCAP für Wireshark
            </p>
          </div>
        </div>

        <div className="p-6 space-y-6">

          {/* Status row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {status.running ? (
                <>
                  {/* Pulsing red dot */}
                  <span className="relative flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
                  </span>
                  <span className="font-mono text-sm font-semibold text-red-400">AUFZEICHNUNG</span>
                  <span className="font-mono text-sm text-muted-foreground">{formatDuration(elapsed)}</span>
                </>
              ) : status.file_ready ? (
                <>
                  <span className="inline-flex h-3 w-3 rounded-full bg-emerald-500" />
                  <span className="font-mono text-sm font-semibold text-emerald-400">DATEI BEREIT</span>
                  <span className="font-mono text-xs text-muted-foreground">{formatBytes(status.size_bytes)}</span>
                  {status.file_mtime && (
                    <span className="font-mono text-xs text-muted-foreground">
                      · {formatTimestamp(status.file_mtime)}
                    </span>
                  )}
                </>
              ) : (
                <>
                  <span className="inline-flex h-3 w-3 rounded-full bg-slate-600" />
                  <span className="font-mono text-sm font-semibold text-slate-400">BEREIT</span>
                </>
              )}
            </div>

            {/* Start / Stop button */}
            {status.running ? (
              <Button
                onClick={handleStop}
                disabled={loading}
                className="cursor-pointer gap-2"
                style={{
                  background: "rgba(239,68,68,0.15)",
                  border: "1px solid rgba(239,68,68,0.3)",
                  color: "#FCA5A5",
                  boxShadow: "none",
                }}
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                Stoppen
              </Button>
            ) : (
              <Button
                onClick={handleStart}
                disabled={loading}
                className="cursor-pointer gap-2"
                style={{
                  background: "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
                  boxShadow: loading ? "none" : "0 0 16px rgba(124,58,237,0.35)",
                  border: "none",
                }}
              >
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-red-400" />
                Aufzeichnen
              </Button>
            )}
          </div>

          {/* Download / discard row — only when file is ready */}
          {status.file_ready && !status.running && (
            <div
              className="flex items-center justify-between rounded-lg px-4 py-3"
              style={{ background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.12)" }}
            >
              <div className="flex items-center gap-2">
                <Wifi className="h-4 w-4 text-emerald-400" />
                <p className="text-sm text-emerald-300">
                  <span className="font-semibold">{formatBytes(status.size_bytes)}</span>
                  {" "}— in Wireshark öffnen um SIP-Signalling + RTP zu analysieren
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDiscard}
                  className="cursor-pointer gap-1.5 text-muted-foreground hover:text-red-400"
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    borderColor: "rgba(255,255,255,0.08)",
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Verwerfen
                </Button>
                <Button
                  size="sm"
                  onClick={handleDownload}
                  className="cursor-pointer gap-1.5"
                  style={{
                    background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                    border: "none",
                    boxShadow: "0 0 12px rgba(5,150,105,0.3)",
                  }}
                >
                  <Download className="h-3.5 w-3.5" />
                  haphone-capture.pcap
                </Button>
              </div>
            </div>
          )}

          {/* Hint box */}
          <div
            className="rounded-lg px-4 py-3 text-xs text-muted-foreground space-y-1"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}
          >
            <p className="font-medium text-slate-400">Anleitung</p>
            <ol className="list-decimal list-inside space-y-0.5 leading-relaxed">
              <li>Trunk konfigurieren und <span className="font-mono">Trunk speichern</span> klicken.</li>
              <li>Hier <span className="font-mono">Aufzeichnen</span> starten.</li>
              <li>Anruf versuchen (oder Registrierung abwarten).</li>
              <li><span className="font-mono">Stoppen</span> — PCAP herunterladen.</li>
              <li>In Wireshark: <span className="font-mono">Telefonie → SIP-Flows</span> für Signalling, <span className="font-mono">Telefonie → RTP-Streams</span> für Audio-Qualität.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
