import { useEffect, useMemo, useState } from "react";
import { SortableHead } from "@/components/SortableHead";
import { useSort } from "@/lib/useSort";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { copyToClipboard } from "@/lib/clipboard";
import { Copy, Trash2, Plus, Save, Pencil, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { DeviceDialog } from "./DeviceDialog";
import { type Extension, type ProvisionedDevice as Device, type ProvisioningTemplate as Template } from "@/types/api";

interface ExtensionDiagnostic {
  number: string;
  status: "Online" | "Offline";
  contact_uri: string;
}
interface ExtensionStatusInfo {
  status: "Online" | "Offline";
  ip: string;
}

function contactIp(contactUri: string): string {
  // contact_uri looks like "sip:11@192.168.7.217:51966;ob" - pull just the host.
  const match = contactUri.match(/@([^:;]+)/);
  return match ? match[1] : "";
}

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([]);
  const deviceColumns = useMemo(() => ({
    name: (d: Device) => d.name,
    model: (d: Device) => `${d.manufacturer} ${d.model}`,
    mac: (d: Device) => d.mac,
    extension: (d: Device) => (d.extension_numbers.length ? Math.min(...d.extension_numbers) : null),
  }), []);
  const deviceSort = useSort(devices, deviceColumns, "name");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  // null = not loaded yet ("unbekannt"), distinct from a confirmed Offline -
  // a failed/slow diagnostics fetch used to silently render as Offline.
  const [extStatus, setExtStatus] = useState<Record<string, ExtensionStatusInfo> | null>(null);
  const [loading, setLoading] = useState(true);

  // Device add/edit dialog: null = closed, {device:null} = add, {device} = edit.
  const [deviceDialog, setDeviceDialog] = useState<{ device: Device | null } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Device | null>(null);

  // template editor
  const [editTpl, setEditTpl] = useState<Template | null>(null);

  function loadAll() {
    Promise.all([
      fetch("/api/provisioning/devices").then((r) => r.json()),
      fetch("/api/provisioning/templates").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
    ])
      .then(([d, t, e]) => { setDevices(d); setTemplates(t); setExtensions(e); })
      .catch(() => toast.error("Die Daten der Tischtelefone konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  function loadDiagnostics() {
    // Online/Offline comes from the SAME endpoint the Nebenstellen page uses
    // (/api/extensions/status), so the two pages can never show conflicting
    // status for the same extension. /api/diagnostics/overview is only used
    // for the IP address (via contact_uri), which that simpler endpoint
    // doesn't expose.
    Promise.all([
      fetch("/api/extensions/status").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/diagnostics/overview").then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([statuses, overview]) => {
        if (!Array.isArray(statuses)) return;
        const ipByNumber: Record<string, string> = {};
        for (const ext of (overview?.extensions ?? []) as ExtensionDiagnostic[]) {
          ipByNumber[ext.number] = contactIp(ext.contact_uri);
        }
        const byNumber: Record<string, ExtensionStatusInfo> = {};
        for (const s of statuses as { number: string; status: "Online" | "Offline" }[]) {
          byNumber[s.number] = { status: s.status, ip: ipByNumber[s.number] ?? "" };
        }
        setExtStatus(byNumber);
      })
      .catch(() => {});
  }
  useEffect(() => {
    loadAll();
    loadDiagnostics();
    const interval = setInterval(loadDiagnostics, 10000);
    return () => clearInterval(interval);
  }, []);

  async function confirmDeleteDevice() {
    if (!deleteTarget) return;
    try {
      const resp = await fetch(`/api/provisioning/devices/${deleteTarget.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      const data = await resp.json().catch(() => null);
      setDevices((ds) => ds.filter((d) => d.id !== deleteTarget.id));
      toast.success(
        data?.hung_up_calls
          ? `Gerät gelöscht, ${data.hung_up_calls} aktive(s) Gespräch(e) getrennt.`
          : "Gerät gelöscht."
      );
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Löschen."));
      throw err;
    }
  }

  async function saveTemplate() {
    if (!editTpl) return;
    try {
      const isNew = editTpl.id === 0;
      const resp = await fetch(
        isNew ? "/api/provisioning/templates" : `/api/provisioning/templates/${editTpl.id}`,
        {
          method: isNew ? "POST" : "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(editTpl),
        },
      );
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern der Vorlage."));
      setEditTpl(null);
      loadAll();
      toast.success("Vorlage gespeichert.");
    } catch (err) { toast.error(toErrorMessage(err, "Fehler beim Speichern der Vorlage.")); }
  }

  async function deleteTemplate(id: number) {
    try {
      await fetch(`/api/provisioning/templates/${id}`, { method: "DELETE" });
      setTemplates((ts) => ts.filter((t) => t.id !== id));
      toast.success("Vorlage gelöscht.");
    } catch { toast.error("Fehler beim Löschen."); }
  }

  async function resync(d: Device) {
    try {
      const resp = await fetch(`/api/provisioning/devices/${d.id}/resync`, { method: "POST" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Neu einlesen fehlgeschlagen."));
      toast.success(`${d.name || d.mac}: Telefon startet neu und lädt seine Einstellungen.`);
    } catch (err) { toast.error(toErrorMessage(err, "Neu einlesen fehlgeschlagen.")); }
  }

  function copy(text: string) {
    copyToClipboard(text, "Kopiert.");
  }

  return (
    <div>
      <PageHeader
        actions={
          <Button onClick={() => setDeviceDialog({ device: null })}>
            <Plus />
            Gerät hinzufügen
          </Button>
        }
      />

      <Tabs defaultValue="devices">
        <TabsList aria-label="Tischtelefone">
          <TabsTrigger value="devices">Geräte</TabsTrigger>
          <TabsTrigger value="templates">Vorlagen</TabsTrigger>
        </TabsList>
        <TabsContent value="devices">
          <div className="rounded-card border border-hair bg-card p-6">
            {loading ? (
              <p className="text-sm text-muted-foreground">Lädt…</p>
            ) : devices.length === 0 ? (
              <p className="rounded-lg border border-dashed border-stroke py-8 text-center text-sm text-muted-foreground">
                Noch keine Geräte. Klicke auf „Gerät hinzufügen", um zu starten.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <SortableHead plain column="name" label="Name" sortKey={deviceSort.sortKey} sortDir={deviceSort.sortDir} onSort={deviceSort.toggle} className="pb-2 pr-3 font-normal" />
                      <SortableHead plain column="model" label="Hersteller / Modell" sortKey={deviceSort.sortKey} sortDir={deviceSort.sortDir} onSort={deviceSort.toggle} className="pb-2 pr-3 font-normal" />
                      <SortableHead plain column="mac" label="MAC" sortKey={deviceSort.sortKey} sortDir={deviceSort.sortDir} onSort={deviceSort.toggle} className="pb-2 pr-3 font-normal" />
                      <SortableHead plain column="extension" label="Status" sortKey={deviceSort.sortKey} sortDir={deviceSort.sortDir} onSort={deviceSort.toggle} className="pb-2 pr-3 font-normal" />
                      <th className="pb-2 pr-3">Provisioning-URL</th>
                      <th className="pb-2 text-right">Aktion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deviceSort.sorted.map((d) => (
                      <tr key={d.id} className="border-t border-hair">
                        <td className="py-3 pr-3">{d.name || "—"}</td>
                        <td className="py-3 pr-3">{d.manufacturer} {d.model}</td>
                        <td className="py-3 pr-3 font-mono text-xs">{d.mac}</td>
                        <td className="py-3 pr-3">
                          <div className="flex flex-col gap-0.5">
                            {d.extension_numbers.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                            {d.extension_numbers.map((num) => {
                              const info = extStatus?.[String(num)];
                              const online = info?.status === "Online";
                              const unknown = extStatus === null;
                              return (
                                <span key={num} className="flex items-center gap-1.5 text-xs">
                                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${online ? "bg-answer" : "bg-faint"}`} />
                                  <span className="font-mono text-muted-foreground">{num}</span>
                                  <span className={online ? "text-answer" : "text-muted-foreground"}>
                                    {unknown ? "Prüft…" : online ? (info?.ip || "Online") : "Offline"}
                                  </span>
                                </span>
                              );
                            })}
                          </div>
                        </td>
                        <td className="py-3 pr-3">
                          <button onClick={() => copy(d.provisioning_url)}
                            className="inline-flex items-center gap-1 font-mono text-xs text-violet hover:underline">
                            <Copy className="h-3 w-3" /> {d.provisioning_url}
                          </button>
                        </td>
                        <td className="py-3 text-right">
                          <Button variant="ghost" size="icon" className="h-8 w-8"
                            onClick={() => resync(d)} aria-label="Neu einlesen" title="Neu einlesen (Telefon startet neu)">
                            <RefreshCw className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8"
                            onClick={() => setDeviceDialog({ device: d })} aria-label="Gerät bearbeiten">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive"
                            onClick={() => setDeleteTarget(d)} aria-label="Gerät löschen">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-4 text-xs text-muted-foreground">
              Nach dem Speichern die angezeigte Provisioning-URL im Gerät eintragen (Web-UI → Auto-Provisioning-Server)
              oder per DHCP-Option 66 verteilen. Das Gerät holt sich die Konfiguration dann selbst von dieser URL —
              es wird nichts aktiv „gesendet".
            </p>
          </div>
        </TabsContent>
        <TabsContent value="templates">
          <div className="rounded-card border border-hair bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Vorlagen</h2>
              <Button size="sm" variant="outline" className="gap-1"
                onClick={() => setEditTpl({ id: 0, name: "", vendor: "", file_pattern: "{mac}.cfg", content: "", builtin: false })}>
                <Plus className="h-3.5 w-3.5" /> Neue Vorlage
              </Button>
            </div>
            <div className="space-y-2">
              {templates.map((t) => (
                <div key={t.id} className="flex items-center justify-between rounded-lg border border-hair px-4 py-2.5">
                  <div>
                    <span className="text-sm font-medium">{t.name}</span>
                    {t.builtin && <span className="ml-2 rounded bg-violet-soft px-1.5 py-0.5 text-[10px] uppercase text-violet">Vorlage</span>}
                    <span className="ml-2 font-mono text-xs text-muted-foreground">{t.file_pattern}</span>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditTpl(t)} aria-label="Bearbeiten">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => deleteTemplate(t.id)} aria-label="Löschen">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            {editTpl && (
              <div className="mt-5 space-y-3 rounded-lg border border-violet/30 p-4">
                <div className="flex gap-2">
                  <Input value={editTpl.name} onChange={(e) => setEditTpl({ ...editTpl, name: e.target.value })} placeholder="Name der Vorlage" />
                  <Input value={editTpl.file_pattern} onChange={(e) => setEditTpl({ ...editTpl, file_pattern: e.target.value })} placeholder="{mac}.cfg" className="font-mono" />
                </div>
                <textarea value={editTpl.content} onChange={(e) => setEditTpl({ ...editTpl, content: e.target.value })}
                  rows={14} spellCheck={false}
                  className="w-full rounded-ctl border border-input bg-transparent p-3 font-mono text-xs"
                  placeholder="Config mit Platzhaltern…" />
                <p className="text-xs text-muted-foreground">
                  Platzhalter: <span className="font-mono">{"{{mac}} {{extension}} {{display_name}} {{sip_username}} {{sip_password}} {{sip_server}} {{sip_port}} {{label}}"}</span>
                </p>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" size="sm" onClick={() => setEditTpl(null)}>Abbrechen</Button>
                  <Button size="sm" className="gap-1" onClick={saveTemplate}><Save className="h-3.5 w-3.5" /> Speichern</Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Add/edit device dialog */}
      {deviceDialog && (
        <DeviceDialog
          device={deviceDialog.device}
          templates={templates}
          extensions={extensions}
          onClose={() => setDeviceDialog(null)}
          onSaved={loadAll}
        />
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <DeleteConfirmDialog
          title={`Gerät "${deleteTarget.name || deleteTarget.mac}" löschen?`}
          description="Ein laufendes Gespräch auf diesem Gerät wird sofort getrennt. Ein aktuell nur registriertes (nicht telefonierendes) Gerät bleibt technisch angemeldet, bis seine Registrierung planmäßig ausläuft (hier bis zu 2 Stunden) oder es neu gestartet wird - Asterisk bietet keine Möglichkeit, eine bestehende, inaktive SIP-Registrierung sofort zwangsweise zu beenden."
          onConfirm={confirmDeleteDevice}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
