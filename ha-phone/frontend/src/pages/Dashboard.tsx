import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Phone, Network, PhoneCall, RefreshCw, ArrowUpCircle } from "lucide-react";

interface UpdateInfo {
  version: string;
  version_latest: string;
  update_available: boolean;
}

interface ExtensionStatus {
  number: string;
  status: "Online" | "Offline";
}

interface TrunkStatusResponse {
  status: string;
}

interface ActiveCallsResponse {
  count: number;
}

type LoadState = "loading" | "loaded" | "error";

// ---- Glassmorphism stat card ----
function StatCard({
  icon: Icon,
  label,
  children,
  accentColor,
  loading,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
  accentColor: string;
  loading: boolean;
}) {
  return (
    <div
      className="glass relative flex min-w-48 flex-1 flex-col gap-4 overflow-hidden rounded-xl p-5"
      style={{ minWidth: "11rem" }}
    >
      {/* Corner accent glow */}
      <div
        className="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full blur-2xl"
        style={{ background: accentColor, opacity: 0.25 }}
      />

      <div className="flex items-center gap-2">
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ background: `${accentColor}20`, border: `1px solid ${accentColor}30` }}
        >
          <Icon className="h-3.5 w-3.5" style={{ color: accentColor }} />
        </div>
        <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
      </div>

      <div className="flex items-end">
        {loading ? (
          <Skeleton className="h-9 w-20" style={{ background: "rgba(255,255,255,0.06)" }} />
        ) : (
          children
        )}
      </div>
    </div>
  );
}

// ---- Trunk status indicator ----
function TrunkIndicator({ status }: { status: string }) {
  if (status === "Registered") {
    return (
      <div className="flex items-center gap-2.5">
        <span className="dot-pulse inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
        <span className="font-mono text-2xl font-semibold text-emerald-400">REGISTERED</span>
      </div>
    );
  }
  if (status === "Unreachable" || status === "Unregistered") {
    return (
      <div className="flex items-center gap-2.5">
        <span className="inline-block h-2.5 w-2.5 rounded-full bg-yellow-400" />
        <span className="font-mono text-2xl font-semibold text-yellow-400">
          {status.toUpperCase()}
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2.5">
      <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-500" />
      <span className="font-mono text-2xl font-semibold text-slate-400">UNKNOWN</span>
    </div>
  );
}

// ---- Main page ----
export default function Dashboard() {
  const [extensionsOnline, setExtensionsOnline] = useState<number>(0);
  const [trunkStatus, setTrunkStatus] = useState<string>("UNKNOWN");
  const [activeCalls, setActiveCalls] = useState<number>(0);

  const [extState, setExtState] = useState<LoadState>("loading");
  const [trunkState, setTrunkState] = useState<LoadState>("loading");
  const [callsState, setCallsState] = useState<LoadState>("loading");

  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [updating, setUpdating] = useState(false);
  const [updateDone, setUpdateDone] = useState(false);

  const extStatusMap = useRef<Record<string, string>>({});

  const fetchExtensions = () => {
    fetch("/api/extensions/status")
      .then((r) => {
        if (!r.ok) throw new Error("API error");
        return r.json() as Promise<ExtensionStatus[]>;
      })
      .then((data) => {
        data.forEach((ext) => {
          extStatusMap.current[ext.number] = ext.status;
        });
        const onlineCount = data.filter((e) => e.status === "Online").length;
        setExtensionsOnline(onlineCount);
        setExtState("loaded");
      })
      .catch(() => setExtState("error"));
  };

  const fetchTrunkStatus = () => {
    fetch("/api/trunk/status")
      .then((r) => {
        if (!r.ok) throw new Error("API error");
        return r.json() as Promise<TrunkStatusResponse>;
      })
      .then((data) => {
        setTrunkStatus(data.status);
        setTrunkState("loaded");
      })
      .catch(() => setTrunkState("error"));
  };

  const fetchActiveCalls = () => {
    fetch("/api/status/active-calls")
      .then((r) => {
        if (!r.ok) throw new Error("API error");
        return r.json() as Promise<ActiveCallsResponse>;
      })
      .then((data) => {
        setActiveCalls(data.count);
        setCallsState("loaded");
      })
      .catch(() => setCallsState("error"));
  };

  const fetchUpdateInfo = () => {
    fetch("/api/update/info")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: UpdateInfo | null) => {
        if (data) setUpdateInfo(data);
      })
      .catch(() => {});
  };

  const startUpdate = () => {
    setUpdating(true);
    fetch("/api/update/start", { method: "POST" })
      .then((r) => {
        if (r.ok) setUpdateDone(true);
        else setUpdating(false);
      })
      .catch(() => setUpdating(false));
  };

  useEffect(() => {
    fetchExtensions();
    fetchTrunkStatus();
    fetchActiveCalls();
    fetchUpdateInfo();

    const extInterval = setInterval(fetchExtensions, 10000);
    const trunkInterval = setInterval(fetchTrunkStatus, 15000);
    const callsInterval = setInterval(fetchActiveCalls, 10000);

    return () => {
      clearInterval(extInterval);
      clearInterval(trunkInterval);
      clearInterval(callsInterval);
    };
  }, []);

  const isLoading =
    extState === "loading" && trunkState === "loading" && callsState === "loading";

  return (
    <div className="space-y-8">

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Systemstatus auf einen Blick</p>
      </div>

      {/* Update banner */}
      {updateInfo?.update_available && !updateDone && (
        <div
          className="glass flex items-center justify-between gap-4 rounded-xl px-5 py-4"
          style={{
            borderColor: "rgba(234,179,8,0.25)",
            background: "rgba(234,179,8,0.06)",
          }}
        >
          <div className="flex items-center gap-3">
            <ArrowUpCircle className="h-4 w-4 shrink-0 text-yellow-400" />
            <span className="text-sm text-slate-200">
              Update verfügbar:{" "}
              <span className="font-mono font-semibold text-yellow-300">
                {updateInfo.version_latest}
              </span>
              <span className="ml-2 text-xs text-muted-foreground">
                (aktuell: {updateInfo.version})
              </span>
            </span>
          </div>
          <Button
            size="sm"
            disabled={updating}
            onClick={startUpdate}
            className="shrink-0 cursor-pointer"
            style={{
              background: "rgba(234,179,8,0.15)",
              border: "1px solid rgba(234,179,8,0.3)",
              color: "#FCD34D",
            }}
          >
            {updating ? (
              <><RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />Aktualisiert…</>
            ) : (
              "Jetzt aktualisieren"
            )}
          </Button>
        </div>
      )}

      {updateDone && (
        <div
          className="glass flex items-center gap-3 rounded-xl px-5 py-4"
          style={{
            borderColor: "rgba(34,197,94,0.25)",
            background: "rgba(34,197,94,0.06)",
          }}
        >
          <span className="dot-pulse inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-sm text-emerald-300">
            Update gestartet — HA-Phone wird neu gestartet. Seite bitte nach ~15 Minuten neu laden.
          </span>
        </div>
      )}

      {/* Error banner */}
      {(extState === "error" || trunkState === "error" || callsState === "error") && (
        <div
          className="glass flex items-center gap-3 rounded-xl px-5 py-4"
          style={{
            borderColor: "rgba(239,68,68,0.25)",
            background: "rgba(239,68,68,0.06)",
          }}
        >
          <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
          <span className="text-sm text-red-300">
            Asterisk nicht erreichbar. PBX startet noch — 10 Sekunden warten und neu laden.
          </span>
        </div>
      )}

      {/* Stat cards */}
      <div className="flex flex-wrap gap-4">
        <StatCard
          icon={Phone}
          label="Extensions Online"
          accentColor="#A78BFA"
          loading={isLoading}
        >
          <span className="font-mono text-4xl font-semibold text-violet-300">
            {extensionsOnline}
          </span>
        </StatCard>

        <StatCard
          icon={Network}
          label="Trunk Status"
          accentColor={
            trunkStatus === "Registered"
              ? "#22C55E"
              : trunkStatus === "Unreachable" || trunkStatus === "Unregistered"
              ? "#EAB308"
              : "#64748B"
          }
          loading={isLoading}
        >
          <TrunkIndicator status={trunkStatus} />
        </StatCard>

        <StatCard
          icon={PhoneCall}
          label="Active Calls"
          accentColor="#38BDF8"
          loading={isLoading}
        >
          <span className="font-mono text-4xl font-semibold text-sky-300">
            {activeCalls}
          </span>
        </StatCard>
      </div>
    </div>
  );
}
