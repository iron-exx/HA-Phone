import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { copyToClipboard } from "@/lib/clipboard";
import { Copy, Trash2, Plus, Save, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
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

function normalizeMac(value: string) {
  return value.replace(/[^0-9a-fA-F]/g, "").toUpperCase();
}

/**
 * Add/edit dialog for a provisioned device. A proper full-width form dialog
 * (like the extensions dialog) instead of the previous cramped inline table
 * row whose fields were too narrow to read. `device` null = add mode.
 */
function DeviceDialog({
  device,
  templates,
  extensions,
  onClose,
  onSaved,
}: {
  device: Device | null;
  templates: Template[];
  extensions: Extension[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = device !== null;
  const [name, setName] = useState(device?.name ?? "");
  const [manufacturer, setManufacturer] = useState(device?.manufacturer ?? "");
  const [model, setModel] = useState(device?.model ?? "");
  const [mac, setMac] = useState(device?.mac ?? "");
  const [extNumbers, setExtNumbers] = useState<number[]>(device?.extension_numbers ?? []);
  const [templateId, setTemplateId] = useState<number | "">(device?.template_id || "");
  const [saving, setSaving] = useState(false);

  function toggleExtNumber(number: number) {
    setExtNumbers((prev) =>
      prev.includes(number) ? prev.filter((n) => n !== number) : [...prev, number]
    );
  }

  async function save() {
    if (normalizeMac(mac).length !== 12) {
      toast.error("MAC muss 12 Hex-Zeichen haben (z.B. AA:BB:CC:DD:EE:FF).");
      return;
    }
    if (extNumbers.length === 0) {
      toast.error("Mindestens eine Nebenstelle zuweisen.");
      return;
    }
    if (templateId === "") {
      toast.error("Bitte ein Template auswählen.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch(
        isEdit ? `/api/provisioning/devices/${device.id}` : "/api/provisioning/devices",
        {
          method: isEdit ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name, manufacturer, model, mac: normalizeMac(mac),
            extension_numbers: extNumbers.join(","), template_id: Number(templateId),
          }),
        }
      );
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      toast.success(isEdit ? "Gerät gespeichert." : "Gerät hinzugefügt.");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Gerät bearbeiten` : "Gerät hinzufügen"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Türklingel" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Hersteller</label>
              <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} placeholder="z.B. Gigaset" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Modell</label>
              <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="z.B. N510 IP PRO" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">MAC-Adresse</label>
            <Input
              value={mac}
              onChange={(e) => setMac(e.target.value)}
              placeholder="AA:BB:CC:DD:EE:FF"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">12 Hex-Zeichen, mit oder ohne Doppelpunkte.</p>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Nebenstellen</label>
            <p className="text-xs text-muted-foreground">
              Welche Nebenstelle(n) dieses Gerät bedient. Mehrere möglich (z.B. DECT-Basis mit mehreren Mobilteilen).
            </p>
            <div className="max-h-52 space-y-1 overflow-y-auto rounded-md border border-input bg-[#0b0e1a] p-3">
              {extensions.length === 0 && (
                <span className="text-sm text-muted-foreground">Keine Nebenstellen vorhanden.</span>
              )}
              {extensions.map((x) => (
                <label
                  key={x.id}
                  className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 text-sm text-slate-200 hover:bg-white/5"
                >
                  <input
                    type="checkbox"
                    checked={extNumbers.includes(x.number)}
                    onChange={() => toggleExtNumber(x.number)}
                    className="h-4 w-4 cursor-pointer"
                  />
                  <span className="font-mono">{x.number}</span>
                  <span className="text-muted-foreground">{x.display_name}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Template</label>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : "")}
              className="h-10 w-full rounded-md border border-input bg-[#0b0e1a] px-3 text-sm text-slate-200 [color-scheme:dark]"
            >
              <option value="">Template auswählen…</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
          <Button onClick={save} disabled={saving} className="gap-1.5">
            <Save className="h-4 w-4" /> {saving ? "Speichert…" : "Speichern"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Provisioning() {
  const [devices, setDevices] = useState<Device[]>([]);
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
      .catch(() => toast.error("Provisioning-Daten konnten nicht geladen werden."))
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
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern des Templates."));
      setEditTpl(null);
      loadAll();
      toast.success("Template gespeichert.");
    } catch (err) { toast.error(toErrorMessage(err, "Fehler beim Speichern des Templates.")); }
  }

  async function deleteTemplate(id: number) {
    try {
      await fetch(`/api/provisioning/templates/${id}`, { method: "DELETE" });
      setTemplates((ts) => ts.filter((t) => t.id !== id));
      toast.success("Template gelöscht.");
    } catch { toast.error("Fehler beim Löschen."); }
  }

  function copy(text: string) {
    copyToClipboard(text, "Kopiert.");
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Auto-Provisioning</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Endgeräte (Tischtelefone, DECT-Basen, Türstationen) automatisch konfigurieren.
        </p>
      </div>

      {/* Devices */}
      <div className="glass rounded-xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Geräte</h2>
          <Button size="sm" className="gap-1.5" onClick={() => setDeviceDialog({ device: null })}>
            <Plus className="h-4 w-4" /> Gerät hinzufügen
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : devices.length === 0 ? (
          <p className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground"
            style={{ borderColor: "rgba(255,255,255,0.1)" }}>
            Noch keine Geräte. Klicke auf „Gerät hinzufügen", um zu starten.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 pr-3">Name</th>
                  <th className="pb-2 pr-3">Hersteller / Modell</th>
                  <th className="pb-2 pr-3">MAC</th>
                  <th className="pb-2 pr-3">Status</th>
                  <th className="pb-2 pr-3">Provisioning-URL</th>
                  <th className="pb-2 text-right">Aktion</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id} className="border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
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
                              <span
                                className="inline-block h-1.5 w-1.5 rounded-full"
                                style={{ background: unknown ? "#475569" : online ? "#22C55E" : "#64748B" }}
                              />
                              <span className="font-mono text-muted-foreground">{num}</span>
                              <span className={online ? "text-emerald-400" : "text-muted-foreground"}>
                                {unknown ? "Prüft…" : online ? (info?.ip || "Online") : "Offline"}
                              </span>
                            </span>
                          );
                        })}
                      </div>
                    </td>
                    <td className="py-3 pr-3">
                      <button onClick={() => copy(d.provisioning_url)}
                        className="inline-flex items-center gap-1 font-mono text-xs text-violet-300 hover:text-violet-200">
                        <Copy className="h-3 w-3" /> {d.provisioning_url}
                      </button>
                    </td>
                    <td className="py-3 text-right">
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

      {/* Templates */}
      <Separator />
      <div className="glass rounded-xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">Templates</h2>
          <Button size="sm" variant="outline" className="gap-1"
            onClick={() => setEditTpl({ id: 0, name: "", vendor: "", file_pattern: "{mac}.cfg", content: "", builtin: false })}>
            <Plus className="h-3.5 w-3.5" /> Neues Template
          </Button>
        </div>
        <div className="space-y-2">
          {templates.map((t) => (
            <div key={t.id} className="flex items-center justify-between rounded-lg border px-4 py-2.5"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}>
              <div>
                <span className="text-sm font-medium">{t.name}</span>
                {t.builtin && <span className="ml-2 rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] uppercase text-violet-300">Vorlage</span>}
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
          <div className="mt-5 space-y-3 rounded-lg border p-4" style={{ borderColor: "rgba(139,92,246,0.2)" }}>
            <div className="flex gap-2">
              <Input value={editTpl.name} onChange={(e) => setEditTpl({ ...editTpl, name: e.target.value })} placeholder="Template-Name" />
              <Input value={editTpl.file_pattern} onChange={(e) => setEditTpl({ ...editTpl, file_pattern: e.target.value })} placeholder="{mac}.cfg" className="font-mono" />
            </div>
            <textarea value={editTpl.content} onChange={(e) => setEditTpl({ ...editTpl, content: e.target.value })}
              rows={14} spellCheck={false}
              className="w-full rounded-md border border-input bg-transparent p-3 font-mono text-xs"
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
