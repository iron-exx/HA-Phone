import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, UserRound } from "lucide-react";
import type { Extension, ExtensionStatus, RingGroup } from "@/types/api";
import { useSort } from "@/lib/useSort";
import { IconTile } from "@/components/IconTile";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AddExtensionDialog } from "./AddExtensionDialog";
import { EditExtensionDialog } from "./EditExtensionDialog";
import { DeleteExtensionDialog } from "./DeleteExtensionDialog";
import { MobileAppQrDialog } from "./MobileAppQrDialog";
import {
  ExtensionsTable,
  type ExtensionContact,
  type ExtensionLiveInfo,
  type ProvisionedDeviceSummary,
} from "./ExtensionsTable";

export default function Extensions() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, "Online" | "Offline">>({});
  const extColumns = useMemo(() => ({
    number: (e: Extension) => e.number,
    name: (e: Extension) => e.display_name,
    status: (e: Extension) => statusMap[String(e.number)] ?? "",
    active: (e: Extension) => e.enabled,
  }), [statusMap]);
  const extSort = useSort(extensions, extColumns, "number");
  const [devices, setDevices] = useState<ProvisionedDeviceSummary[]>([]);
  const [liveInfo, setLiveInfo] = useState<Record<string, ExtensionLiveInfo>>({});
  const [loading, setLoading] = useState(true);
  const [dialogMode, setDialogMode] = useState<"add" | "edit" | null>(null);
  const [editTarget, setEditTarget] = useState<Extension | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Extension | null>(null);
  const [mobileQrTarget, setMobileQrTarget] = useState<Extension | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchDevices() {
    try {
      const resp = await fetch("/api/provisioning/devices");
      if (!resp.ok) return;
      setDevices(await resp.json());
    } catch {
      // Non-fatal - the "Geräte" column just shows nothing assigned.
    }
  }

  async function fetchRingGroups() {
    try {
      const resp = await fetch("/api/ring-groups");
      if (!resp.ok) throw new Error();
      const data: RingGroup[] = await resp.json();
      setRingGroups(data);
    } catch {
      toast.error("Rufgruppen konnten nicht geladen werden.");
    }
  }

  useEffect(() => {
    fetch("/api/extensions")
      .then((r) => r.json())
      .then((data: Extension[]) => setExtensions(data))
      .catch(() => toast.error("Nebenstellen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
    fetchRingGroups();
    fetchDevices();
  }, []);

  useEffect(() => {
    function pollStatus() {
      fetch("/api/extensions/status")
        .then((r) => r.json())
        .then((data: ExtensionStatus[]) => {
          setStatusMap((prev) => {
            const next = { ...prev };
            data.forEach((s: ExtensionStatus) => {
              next[s.number] = s.status;
            });
            return next;
          });
        })
        .catch(() => {});

      // Live contact detail (which client(s) are actually registered - a
      // hardware phone from Auto-Provisioning, a softphone, or both) isn't
      // in the simpler status endpoint above; diagnostics carries it.
      fetch("/api/diagnostics/overview")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!d?.extensions) return;
          const next: Record<string, ExtensionLiveInfo> = {};
          for (const ext of d.extensions as { number: string; contacts: number; contacts_detail?: ExtensionContact[] }[]) {
            next[ext.number] = { contacts: ext.contacts, contacts_detail: ext.contacts_detail ?? [] };
          }
          setLiveInfo(next);
        })
        .catch(() => {});
    }

    pollStatus();
    intervalRef.current = setInterval(pollStatus, 10_000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, []);

  async function toggleEnabled(ext: Extension) {
    const original = ext.enabled;
    setExtensions((prev) =>
      prev.map((e) => (e.id === ext.id ? { ...e, enabled: !e.enabled } : e))
    );
    try {
      const resp = await fetch(`/api/extensions/${ext.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !original }),
      });
      if (!resp.ok) throw new Error();
      const updated: Extension = await resp.json();
      setExtensions((prev) =>
        prev.map((e) => (e.id === updated.id ? updated : e))
      );
    } catch {
      setExtensions((prev) =>
        prev.map((e) => (e.id === ext.id ? { ...e, enabled: original } : e))
      );
      toast.error("Fehler beim Speichern.");
    }
  }

  return (
    <div>
      <PageHeader actions={<Button onClick={() => setDialogMode("add")}><Plus />Nebenstelle anlegen</Button>} />

      {loading ? (
        <div className="space-y-3 rounded-card border border-hair bg-card p-6">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      ) : extensions.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-card border border-hair bg-card py-16 text-center">
          <IconTile icon={UserRound} tone="blue" />
          <h2 className="mt-3 font-display text-base font-extrabold">Noch keine Nebenstellen</h2>
          <p className="mt-1.5 max-w-xs text-sm text-muted-foreground">Lege deine erste Nebenstelle an, damit Telefone und die App sich anmelden können.</p>
        </div>
      ) : (
        <ExtensionsTable
          rows={extSort.sorted}
          sort={extSort}
          statusMap={statusMap}
          ringGroups={ringGroups}
          devices={devices}
          liveInfo={liveInfo}
          onToggleEnabled={(ext) => void toggleEnabled(ext)}
          onEdit={(ext) => { setEditTarget(ext); setDialogMode("edit"); }}
          onDelete={setDeleteTarget}
          onQr={setMobileQrTarget}
        />
      )}

      {dialogMode === "add" && (
        <AddExtensionDialog
          open
          onClose={() => setDialogMode(null)}
          onCreated={(ext) => setExtensions((prev) => [...prev, ext])}
          ringGroups={ringGroups}
          onRingGroupsChanged={fetchRingGroups}
        />
      )}

      {dialogMode === "edit" && editTarget && (
        <EditExtensionDialog
          extension={editTarget}
          onClose={() => { setDialogMode(null); setEditTarget(null); }}
          onUpdated={(updated) => {
            setExtensions((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
            setDialogMode(null);
            setEditTarget(null);
          }}
          ringGroups={ringGroups}
          onRingGroupsChanged={fetchRingGroups}
        />
      )}

      {deleteTarget && (
        <DeleteExtensionDialog
          extension={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={(id) => {
            setExtensions((prev) => prev.filter((e) => e.id !== id));
            setDeleteTarget(null);
          }}
        />
      )}

      {mobileQrTarget && (
        <MobileAppQrDialog
          extension={mobileQrTarget}
          onClose={() => setMobileQrTarget(null)}
        />
      )}
    </div>
  );
}
