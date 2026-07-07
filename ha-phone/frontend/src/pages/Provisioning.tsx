import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Copy, Trash2, Plus, Save, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { type Extension } from "@/types/api";

interface Template {
  id: number;
  name: string;
  vendor: string;
  file_pattern: string;
  content: string;
  builtin: boolean;
}
interface Device {
  id: number;
  name: string;
  manufacturer: string;
  model: string;
  mac: string;
  extension_numbers: number[];
  template_id: number;
  provisioning_url: string;
}
interface ExtensionDiagnostic {
  number: string;
  status: "Online" | "Offline";
  contact_uri: string;
}

function contactIp(contactUri: string): string {
  // contact_uri looks like "sip:11@192.168.7.217:51966;ob" - pull just the host.
  const match = contactUri.match(/@([^:;]+)/);
  return match ? match[1] : "";
}

const inputCls = "h-9 font-mono";

export default function Provisioning() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [extDiagnostics, setExtDiagnostics] = useState<Record<string, ExtensionDiagnostic>>({});
  const [loading, setLoading] = useState(true);

  // add-device form
  const [dName, setDName] = useState("");
  const [dManu, setDManu] = useState("");
  const [dModel, setDModel] = useState("");
  const [dMac, setDMac] = useState("");
  const [dExtNumbers, setDExtNumbers] = useState<number[]>([]);
  const [dTpl, setDTpl] = useState<number | "">("");
  const [savingDev, setSavingDev] = useState(false);

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
    fetch("/api/diagnostics/overview")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.extensions) return;
        const byNumber: Record<string, ExtensionDiagnostic> = {};
        for (const ext of d.extensions as ExtensionDiagnostic[]) byNumber[ext.number] = ext;
        setExtDiagnostics(byNumber);
      })
      .catch(() => {});
  }
  useEffect(() => {
    loadAll();
    loadDiagnostics();
    const interval = setInterval(loadDiagnostics, 10000);
    return () => clearInterval(interval);
  }, []);

  function toggleExtNumber(number: number) {
    setDExtNumbers((prev) =>
      prev.includes(number) ? prev.filter((n) => n !== number) : [...prev, number]
    );
  }

  async function addDevice() {
    if (!dMac.trim() || dExtNumbers.length === 0 || dTpl === "") {
      toast.error("MAC, mindestens eine Nebenstelle und Template sind erforderlich.");
      return;
    }
    setSavingDev(true);
    try {
      const resp = await fetch("/api/provisioning/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: dName, manufacturer: dManu, model: dModel, mac: dMac,
          extension_numbers: dExtNumbers.join(","), template_id: Number(dTpl),
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setDName(""); setDManu(""); setDModel(""); setDMac(""); setDExtNumbers([]); setDTpl("");
      loadAll();
      toast.success("Gerät hinzugefügt.");
    } catch (e) {
      toast.error(`Fehler: ${(e as Error).message || "Speichern fehlgeschlagen"}`);
    } finally {
      setSavingDev(false);
    }
  }

  async function deleteDevice(id: number) {
    try {
      await fetch(`/api/provisioning/devices/${id}`, { method: "DELETE" });
      setDevices((ds) => ds.filter((d) => d.id !== id));
      toast.success("Gerät gelöscht.");
    } catch { toast.error("Fehler beim Löschen."); }
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
    navigator.clipboard?.writeText(text);
    toast.success("Kopiert.");
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
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-muted-foreground">Geräte</h2>
        {loading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 pr-3">Name</th>
                  <th className="pb-2 pr-3">Hersteller / Modell</th>
                  <th className="pb-2 pr-3">MAC</th>
                  <th className="pb-2 pr-3">Nebenstellen</th>
                  <th className="pb-2 pr-3">Status</th>
                  <th className="pb-2 pr-3">Provisioning-URL</th>
                  <th className="pb-2 text-right">Aktion</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id} className="border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <td className="py-2 pr-3">{d.name || "—"}</td>
                    <td className="py-2 pr-3">{d.manufacturer} {d.model}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{d.mac}</td>
                    <td className="py-2 pr-3 font-mono">{d.extension_numbers.join(", ") || "—"}</td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-col gap-0.5">
                        {d.extension_numbers.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                        {d.extension_numbers.map((num) => {
                          const diag = extDiagnostics[String(num)];
                          const online = diag?.status === "Online";
                          const ip = diag ? contactIp(diag.contact_uri) : "";
                          return (
                            <span key={num} className="flex items-center gap-1.5 text-xs">
                              <span
                                className="inline-block h-1.5 w-1.5 rounded-full"
                                style={{ background: online ? "#22C55E" : "#64748B" }}
                              />
                              <span className="font-mono text-muted-foreground">{num}</span>
                              <span className={online ? "text-emerald-400" : "text-muted-foreground"}>
                                {online ? (ip || "Online") : "Offline"}
                              </span>
                            </span>
                          );
                        })}
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <button onClick={() => copy(d.provisioning_url)}
                        className="inline-flex items-center gap-1 font-mono text-xs text-violet-300 hover:text-violet-200">
                        <Copy className="h-3 w-3" /> {d.provisioning_url}
                      </button>
                    </td>
                    <td className="py-2 text-right">
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive"
                        onClick={() => deleteDevice(d.id)} aria-label="Gerät löschen">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {/* add row */}
                <tr className="border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                  <td className="py-2 pr-3"><Input value={dName} onChange={(e) => setDName(e.target.value)} placeholder="Name" className={inputCls} /></td>
                  <td className="py-2 pr-3">
                    <div className="flex gap-1">
                      <Input value={dManu} onChange={(e) => setDManu(e.target.value)} placeholder="Hersteller" className={inputCls} />
                      <Input value={dModel} onChange={(e) => setDModel(e.target.value)} placeholder="Modell" className={inputCls} />
                    </div>
                  </td>
                  <td className="py-2 pr-3"><Input value={dMac} onChange={(e) => setDMac(e.target.value)} placeholder="AA:BB:CC:DD:EE:FF" className={inputCls} /></td>
                  <td className="py-2 pr-3">
                    <div
                      className="max-h-24 w-36 space-y-1 overflow-y-auto rounded-md border border-input bg-[#0b0e1a] p-2"
                      title="Mehrere Nebenstellen moeglich - je Mobilteil/Leitung eine (z.B. DECT-Basis)."
                    >
                      {extensions.length === 0 && <span className="text-xs text-muted-foreground">Keine Nebenstellen</span>}
                      {extensions.map((x) => (
                        <label key={x.id} className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-200">
                          <input
                            type="checkbox"
                            checked={dExtNumbers.includes(x.number)}
                            onChange={() => toggleExtNumber(x.number)}
                            className="cursor-pointer"
                          />
                          {x.number} ({x.display_name})
                        </label>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-3" />
                  <td className="py-2 pr-3">
                    <select value={dTpl} onChange={(e) => setDTpl(e.target.value ? Number(e.target.value) : "")}
                      className="h-9 w-full rounded-md border border-input bg-[#0b0e1a] px-2 text-sm text-slate-200 [color-scheme:dark]">
                      <option value="">Template…</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </td>
                  <td className="py-2 text-right">
                    <Button size="sm" onClick={addDevice} disabled={savingDev} className="gap-1">
                      <Plus className="h-3.5 w-3.5" /> {savingDev ? "…" : "Add"}
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          Trage die Provisioning-URL im Gerät ein (Web-UI → Auto-Provisioning-Server) oder verteile sie per DHCP-Option 66.
          Gigaset: <span className="font-mono">…/api/autoprovision/[MAC].xml</span> als Datenserver-URL.
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
    </div>
  );
}
