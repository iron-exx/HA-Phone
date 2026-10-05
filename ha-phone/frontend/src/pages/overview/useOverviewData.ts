import { useEffect, useState } from "react";
import type { DoorbellEvent, Extension } from "@/types/api";
import type { ConfigRegenerationStatus, UpdateInfo } from "./overviewLogic";

export interface OverviewData {
  trunkStatus: string;
  extensions: Extension[];
  online: Set<string>;
  statusKnown: boolean;
  activeCalls: number;
  doorEvents: DoorbellEvent[];
  regen: ConfigRegenerationStatus | null;
  update: UpdateInfo | null;
}

const POLL_MS = { status: 10_000, trunk: 15_000, calls: 5_000, door: 30_000, regen: 15_000 } as const;

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url}: ${resp.status}`);
  return (await resp.json()) as T;
}

/** Pollt alles für die Übersicht. Fehler einzelner Abfragen lassen den letzten Stand stehen. */
export function useOverviewData(): OverviewData {
  const [trunkStatus, setTrunkStatus] = useState("UNKNOWN");
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [online, setOnline] = useState<Set<string>>(new Set());
  const [statusKnown, setStatusKnown] = useState(false);
  const [activeCalls, setActiveCalls] = useState(0);
  const [doorEvents, setDoorEvents] = useState<DoorbellEvent[]>([]);
  const [regen, setRegen] = useState<ConfigRegenerationStatus | null>(null);
  const [update, setUpdate] = useState<UpdateInfo | null>(null);

  useEffect(() => {
    const ignore = () => {};
    const loadStatus = () =>
      Promise.all([getJson<Extension[]>("/api/extensions"), getJson<{ number: string; status: string }[]>("/api/extensions/status")])
        .then(([all, statuses]) => {
          setExtensions(all);
          setOnline(new Set(statuses.filter((s) => s.status === "Online").map((s) => s.number)));
          setStatusKnown(true);
        })
        .catch(ignore);
    const loadTrunk = () => getJson<{ status: string }>("/api/trunk/status").then((d) => setTrunkStatus(d.status)).catch(ignore);
    const loadCalls = () => getJson<{ count: number }>("/api/status/active-calls").then((d) => setActiveCalls(d.count)).catch(ignore);
    const loadDoor = () => getJson<DoorbellEvent[]>("/api/doorbell?limit=50").then(setDoorEvents).catch(ignore);
    const loadRegen = () => getJson<ConfigRegenerationStatus>("/api/diagnostics/config-regeneration").then(setRegen).catch(ignore);

    void loadStatus(); void loadTrunk(); void loadCalls(); void loadDoor(); void loadRegen();
    getJson<UpdateInfo>("/api/update/info").then(setUpdate).catch(ignore);

    const timers = [
      setInterval(loadStatus, POLL_MS.status),
      setInterval(loadTrunk, POLL_MS.trunk),
      setInterval(loadCalls, POLL_MS.calls),
      setInterval(loadDoor, POLL_MS.door),
      setInterval(loadRegen, POLL_MS.regen),
    ];
    return () => timers.forEach(clearInterval);
  }, []);

  return { trunkStatus, extensions, online, statusKnown, activeCalls, doorEvents, regen, update };
}
