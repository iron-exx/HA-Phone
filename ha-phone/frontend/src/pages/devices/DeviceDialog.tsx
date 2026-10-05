import { FormGrid, FormSpan } from "@/components/FormGrid";
import { useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { type Extension, type ProvisionedDevice as Device, type ProvisioningTemplate as Template } from "@/types/api";

function normalizeMac(value: string) {
  return value.replace(/[^0-9a-fA-F]/g, "").toUpperCase();
}

const FANVIL_LANGUAGES = ["German", "English", "French", "Spanish", "Russian"];
// Fanvil V65: 9 programmable keys (same count as backend FANVIL_V65_DSS_KEYS).
const FANVIL_V65_DSS_KEYS = Array.from({ length: 9 }, (_, i) => i + 1);

// Codes are mapped to Fanvil Fkey types in the backend (_FANVIL_KEY_TYPES).
const FANVIL_DSS_TYPES = [
  { value: "0", label: "Leer" },
  { value: "1", label: "Kurzwahl" },
  { value: "2", label: "BLF" },
  { value: "line", label: "Leitung" },
  { value: "intercom", label: "Intercom" },
  { value: "16", label: "Parken" },
];

/**
 * Add/edit dialog for a provisioned device. A proper full-width form dialog
 * (like the extensions dialog) instead of the previous cramped inline table
 * row whose fields were too narrow to read. `device` null = add mode.
 */
export function DeviceDialog({
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
  const [extraVars, setExtraVars] = useState<Record<string, string>>(device?.extra_vars ?? {});
  const [saving, setSaving] = useState(false);

  const selectedTemplate = templates.find(t => t.id === Number(templateId));
  const isFanvilV65 = selectedTemplate?.name.includes("Fanvil V65") ?? false;

  function setVar(key: string, value: string) {
    setExtraVars(prev => ({ ...prev, [key]: value }));
  }

  function toggleExtNumber(number: number) {
    setExtNumbers((prev) =>
      prev.includes(number) ? prev.filter((n) => n !== number) : [...prev, number]
    );
  }

  async function save() {
    if (normalizeMac(mac).length !== 12) {
      toast.error("MAC muss 12 Hex-Zeichen haben (z. B. AA:BB:CC:DD:EE:FF).");
      return;
    }
    if (extNumbers.length === 0) {
      toast.error("Mindestens eine Nebenstelle zuweisen.");
      return;
    }
    if (templateId === "") {
      toast.error("Bitte eine Vorlage auswählen.");
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
            extra_vars: extraVars,
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
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Gerät bearbeiten` : "Gerät hinzufügen"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <FormGrid>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Türklingel" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Hersteller</label>
                <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} placeholder="z. B. Gigaset" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Modell</label>
                <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="z. B. N510 IP PRO" />
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
                Welche Nebenstelle(n) dieses Gerät bedient. Mehrere möglich (z. B. DECT-Basis mit mehreren Mobilteilen).
              </p>
              <div className="max-h-52 space-y-1 overflow-y-auto rounded-ctl border border-input bg-raised p-3">
                {extensions.length === 0 && (
                  <span className="text-sm text-muted-foreground">Keine Nebenstellen vorhanden.</span>
                )}
                {extensions.map((x) => (
                  <label
                    key={x.id}
                    className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 text-sm text-foreground hover:bg-raised"
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
              <label className="text-sm font-medium">Vorlage</label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : "")}
                className="h-10 w-full rounded-ctl border border-input bg-raised px-3 text-sm text-foreground"
              >
                <option value="">Vorlage auswählen…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <FormSpan>
              {isFanvilV65 && (
                <div className="space-y-3 rounded-ctl border border-input bg-raised p-3">
                  <p className="text-sm font-medium text-foreground">Fanvil V65 – Geräteeinstellungen</p>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Sprache</label>
                      <select
                        value={extraVars.fanvil_language ?? "German"}
                        onChange={e => setVar("fanvil_language", e.target.value)}
                        className="h-8 w-full rounded-ctl border border-input bg-card px-2 text-sm text-foreground"
                      >
                        {FANVIL_LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Türvideo vor dem Abnehmen</label>
                      <select
                        value={extraVars.fanvil_early_media ?? "1"}
                        onChange={e => setVar("fanvil_early_media", e.target.value)}
                        className="h-8 w-full rounded-ctl border border-input bg-card px-2 text-sm text-foreground"
                      >
                        <option value="1">An (Early Media)</option>
                        <option value="0">Aus</option>
                      </select>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">Zeitzone: Mitteleuropa (UTC+1 mit Sommerzeit)</p>

                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Funktionstasten (DSS Keys)</p>
                    <div className="grid grid-cols-[1.25rem_5.5rem_1fr_1fr_2rem] gap-1 px-0.5 text-xs text-muted-foreground">
                      <span>#</span><span>Typ</span><span>Nummer</span><span>Beschriftung</span><span className="text-center">Ln</span>
                    </div>
                    {FANVIL_V65_DSS_KEYS.map(n => (
                      <div key={n} className="grid grid-cols-[1.25rem_5.5rem_1fr_1fr_2rem] gap-1 items-center">
                        <span className="text-xs text-muted-foreground text-center">{n}</span>
                        <select
                          value={extraVars[`fanvil_dss${n}_type`] ?? "0"}
                          onChange={e => setVar(`fanvil_dss${n}_type`, e.target.value)}
                          className="h-7 rounded border border-input bg-card px-1 text-xs text-foreground"
                        >
                          {FANVIL_DSS_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </select>
                        <Input value={extraVars[`fanvil_dss${n}_value`] ?? ""} onChange={e => setVar(`fanvil_dss${n}_value`, e.target.value)} className="h-7 text-xs" placeholder="102" />
                        <Input value={extraVars[`fanvil_dss${n}_label`] ?? ""} onChange={e => setVar(`fanvil_dss${n}_label`, e.target.value)} className="h-7 text-xs" placeholder="Büro" />
                        <Input value={extraVars[`fanvil_dss${n}_line`] ?? "1"} onChange={e => setVar(`fanvil_dss${n}_line`, e.target.value)} className="h-7 text-xs text-center" placeholder="1" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </FormSpan>
          </FormGrid>
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
