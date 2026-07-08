import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import QRCode from "qrcode";
import { MoreHorizontal, Pencil, Trash2, Plus, Phone, QrCode, Copy } from "lucide-react";

import {
  type Extension,
  type ExtensionStatus,
  type RingGroup,
  type LinphoneProvisioningInfo,
} from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  buildLinphoneConfigUri,
  buildLinphoneQrPayload,
  buildProvisioningUrl,
} from "@/lib/linphoneProvisioning";

// ---- Zod schema ----
const extensionSchema = z.object({
  number: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
  display_name: z.string().min(1, "Required").max(64, "Max 64 chars"),
  sip_password: z.string().min(8, "Min 8 characters"),
  enabled: z.boolean(),
  internal_only: z.boolean().default(false),
  numeric_callerid: z.boolean().default(false),
});

type ExtensionFormValues = z.infer<typeof extensionSchema>;

const editSchema = extensionSchema.extend({
  sip_password: z
    .string()
    .refine((v) => v === "" || v.length >= 8, "Min 8 characters if provided"),
});

type EditFormValues = z.infer<typeof editSchema>;

function getExtensionRingGroupIds(extension: Extension, ringGroups: RingGroup[]) {
  return ringGroups
    .filter((group) =>
      group.extension_numbers
        .split(",")
        .map((number) => number.trim())
        .includes(String(extension.number))
    )
    .map((group) => group.id);
}

function toggleRingGroupId(ids: number[], id: number) {
  return ids.includes(id) ? ids.filter((current) => current !== id) : [...ids, id];
}

function buildExtensionNumbers(group: RingGroup, extensionNumber: number, selected: boolean) {
  const numbers = group.extension_numbers
    .split(",")
    .map((number) => number.trim())
    .filter(Boolean)
    .filter((number) => number !== String(extensionNumber));

  if (selected) numbers.push(String(extensionNumber));

  return Array.from(new Set(numbers))
    .map((number) => Number(number))
    .filter((number) => Number.isFinite(number))
    .sort((a, b) => a - b)
    .join(",");
}

async function syncRingGroupMemberships(
  extensionNumber: number,
  selectedRingGroupIds: number[],
  ringGroups: RingGroup[]
) {
  const updates = ringGroups
    .map((group) => ({
      ...group,
      extension_numbers: buildExtensionNumbers(
        group,
        extensionNumber,
        selectedRingGroupIds.includes(group.id)
      ),
    }))
    .filter((group, index) => group.extension_numbers !== ringGroups[index].extension_numbers);

  await Promise.all(
    updates.map((group) =>
      fetch(`/api/ring-groups/${group.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(group),
      }).then((resp) => {
        if (!resp.ok) throw new Error("Failed to update ring group");
        return resp.json();
      })
    )
  );
}

// ---- Status dot ----
function StatusDot({ status }: { status: "Online" | "Offline" | undefined }) {
  if (status === "Online") {
    return (
      <div className="flex items-center gap-2">
        <span className="dot-pulse inline-block h-2 w-2 rounded-full bg-emerald-400" />
        <span className="text-xs font-medium text-emerald-400">Online</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="inline-block h-2 w-2 rounded-full bg-slate-600" />
      <span className="text-xs font-medium text-muted-foreground">Offline</span>
    </div>
  );
}

// ---- Add form dialog ----
function AddExtensionDialog({
  open,
  onClose,
  onCreated,
  ringGroups,
  onRingGroupsChanged,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (ext: Extension) => void;
  ringGroups: RingGroup[];
  onRingGroupsChanged: () => Promise<void>;
}) {
  const form = useForm<ExtensionFormValues>({
    resolver: zodResolver(extensionSchema),
    defaultValues: { number: undefined as unknown as number, display_name: "", sip_password: "", enabled: true, internal_only: false, numeric_callerid: false },
  });
  const [saving, setSaving] = useState(false);
  const [selectedRingGroupIds, setSelectedRingGroupIds] = useState<number[]>([]);

  async function generatePassword() {
    try {
      const resp = await fetch("/api/extensions/generate-password");
      if (resp.ok) {
        const data = await resp.json();
        form.setValue("sip_password", data.password, { shouldValidate: true });
      }
    } catch {
      // Non-fatal
    }
  }

  useEffect(() => {
    if (open) generatePassword();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function onSubmit(values: ExtensionFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/extensions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      const created: Extension = await resp.json();
      await syncRingGroupMemberships(created.number, selectedRingGroupIds, ringGroups);
      await onRingGroupsChanged();
      onCreated(created);
      toast.success("Gespeichert.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nebenstelle hinzufügen</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Durchwahl (Nummer)</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="z.B. 10" className="font-mono" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Anzeigename</FormLabel>
                  <FormControl>
                    <Input placeholder="z.B. Büro" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sip_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>SIP Passwort</FormLabel>
                  <FormControl>
                    <div className="flex gap-2">
                      <Input type="text" placeholder="Auto-generiert" className="font-mono" {...field} />
                      <Button type="button" variant="outline" onClick={generatePassword}
                        className="cursor-pointer shrink-0"
                        style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.1)" }}>
                        Neu
                      </Button>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="internal_only"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3"
                  style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                  <div>
                    <FormLabel>Nur intern</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      Kann nur intern telefonieren — kein Anruf nach außen (z.B. Türsprechstelle).
                    </p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="numeric_callerid"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3"
                  style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                  <div>
                    <FormLabel>Altgeräte-Modus</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte
                      SIP-Clients (z.B. Android nativ), die Namen als "Anonym" anzeigen.
                    </p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            {ringGroups.length > 0 && (
              <div className="space-y-2">
                <FormLabel>Ring Groups</FormLabel>
                <div className="grid gap-2">
                  {ringGroups.map((group) => {
                    const selected = selectedRingGroupIds.includes(group.id);
                    return (
                      <button
                        key={group.id}
                        type="button"
                        onClick={() =>
                          setSelectedRingGroupIds((current) =>
                            toggleRingGroupId(current, group.id)
                          )
                        }
                        className={[
                          "flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                          selected
                            ? "border-violet-500/60 bg-violet-500/15 text-violet-100"
                            : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                        ].join(" ")}
                      >
                        <span className="font-medium">{group.name}</span>
                        <span className="text-xs">
                          {selected ? "Zugewiesen" : "Nicht zugewiesen"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}
                className="cursor-pointer">
                Abbrechen
              </Button>
              <Button type="submit" disabled={saving}
                className="cursor-pointer"
                style={{ background: "linear-gradient(135deg, #7C3AED, #4F46E5)", border: "none" }}>
                {saving ? "Speichert…" : "Speichern"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit form dialog ----
function EditExtensionDialog({
  extension,
  onClose,
  onUpdated,
  ringGroups,
  onRingGroupsChanged,
}: {
  extension: Extension;
  onClose: () => void;
  onUpdated: (ext: Extension) => void;
  ringGroups: RingGroup[];
  onRingGroupsChanged: () => Promise<void>;
}) {
  const form = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      number: extension.number,
      display_name: extension.display_name,
      sip_password: "",
      enabled: extension.enabled,
      internal_only: extension.internal_only ?? false,
      numeric_callerid: extension.numeric_callerid ?? false,
    },
  });
  const [saving, setSaving] = useState(false);
  const [selectedRingGroupIds, setSelectedRingGroupIds] = useState<number[]>(
    getExtensionRingGroupIds(extension, ringGroups)
  );

  async function onSubmit(values: EditFormValues) {
    setSaving(true);
    const body: Partial<{ display_name: string; sip_password: string; enabled: boolean; internal_only: boolean; numeric_callerid: boolean }> = {
      display_name: values.display_name,
      enabled: values.enabled,
      internal_only: values.internal_only,
      numeric_callerid: values.numeric_callerid,
    };
    if (values.sip_password && values.sip_password.length > 0) {
      body.sip_password = values.sip_password;
    }
    try {
      const resp = await fetch(`/api/extensions/${extension.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      const updated: Extension = await resp.json();
      await syncRingGroupMemberships(updated.number, selectedRingGroupIds, ringGroups);
      await onRingGroupsChanged();
      onUpdated(updated);
      toast.success("Gespeichert.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nebenstelle {extension.number} bearbeiten</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Durchwahl (Nummer)</FormLabel>
                  <FormControl>
                    <Input type="number" className="font-mono opacity-60 cursor-not-allowed" {...field} readOnly />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Anzeigename</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sip_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>SIP Passwort</FormLabel>
                  <FormControl>
                    <Input type="password" placeholder="Leer lassen = behalten" className="font-mono" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="internal_only"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3"
                  style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                  <div>
                    <FormLabel>Nur intern</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      Kann nur intern telefonieren — kein Anruf nach außen (z.B. Türsprechstelle).
                    </p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="numeric_callerid"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-3"
                  style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                  <div>
                    <FormLabel>Altgeräte-Modus</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte
                      SIP-Clients (z.B. Android nativ), die Namen als "Anonym" anzeigen.
                    </p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            {ringGroups.length > 0 && (
              <div className="space-y-2">
                <FormLabel>Ring Groups</FormLabel>
                <div className="grid gap-2">
                  {ringGroups.map((group) => {
                    const selected = selectedRingGroupIds.includes(group.id);
                    return (
                      <button
                        key={group.id}
                        type="button"
                        onClick={() =>
                          setSelectedRingGroupIds((current) =>
                            toggleRingGroupId(current, group.id)
                          )
                        }
                        className={[
                          "flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                          selected
                            ? "border-violet-500/60 bg-violet-500/15 text-violet-100"
                            : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                        ].join(" ")}
                      >
                        <span className="font-medium">{group.name}</span>
                        <span className="text-xs">
                          {selected ? "Zugewiesen" : "Nicht zugewiesen"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}
                className="cursor-pointer">
                Abbrechen
              </Button>
              <Button type="submit" disabled={saving}
                className="cursor-pointer"
                style={{ background: "linear-gradient(135deg, #7C3AED, #4F46E5)", border: "none" }}>
                {saving ? "Speichert…" : "Speichern"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Delete confirmation dialog ----
function DeleteExtensionDialog({
  extension,
  onClose,
  onDeleted,
}: {
  extension: Extension;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleDelete() {
    setDeleteLoading(true);
    try {
      const resp = await fetch(`/api/extensions/${extension.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      onDeleted(extension.id);
      toast.success("Nebenstelle gelöscht.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Löschen."));
      setDeleteLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !deleteLoading) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nebenstelle {extension.number} löschen?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Das entfernt die SIP-Registrierung. Das Telefon muss sich mit neuen Zugangsdaten neu anmelden.
        </p>
        <DialogFooter>
          {!deleteLoading && (
            <Button variant="outline" onClick={onClose} className="cursor-pointer">
              Behalten
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteLoading}
            className="cursor-pointer"
          >
            {deleteLoading ? "Löscht…" : "Löschen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LinphoneQrDialog({
  extension,
  onClose,
}: {
  extension: Extension;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState("");
  const [provisioning, setProvisioning] = useState<LinphoneProvisioningInfo | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const resp = await fetch(`/api/extensions/${extension.id}/linphone-qr`);
        if (!resp.ok) throw new Error();
        const data: LinphoneProvisioningInfo = await resp.json();
        if (cancelled) return;
        setProvisioning(data);
        // Linphone's IN-APP QR scanner ("Scan QR Code" in the assistant) expects
        // the RAW http(s) provisioning URL as QR payload — NOT the
        // "linphone-config:" wrapped form, which it rejects as "invalid URI".
        // The linphone-config: scheme is only for clickable links that launch
        // the app via the OS (see openInLinphone below).
        const dataUrl = await QRCode.toDataURL(buildLinphoneQrPayload(data.provisioning_path), {
          width: 320,
          margin: 2,
          color: {
            dark: "#F8FAFC",
            light: "#050816",
          },
        });
        if (!cancelled) setQrCodeDataUrl(dataUrl);
      } catch {
        if (!cancelled) toast.error("Linphone-QR konnte nicht geladen werden.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [extension.id]);

  async function copyProvisioningLink() {
    if (!provisioning) return;
    const value = buildProvisioningUrl(provisioning.provisioning_path);

    // This page usually runs inside Home Assistant's ingress <iframe>, where the
    // async Clipboard API can be unavailable/blocked by permissions policy even
    // in a secure context. Try it, but always fall back to execCommand, and if
    // even that is blocked, leave the text selected so the user can hit Ctrl+C.
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        toast.success("Provisioning-Link kopiert.");
        return;
      }
    } catch {
      // fall through to execCommand fallback
    }

    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    let success = false;
    try {
      success = document.execCommand("copy");
    } catch {
      success = false;
    }
    document.body.removeChild(textarea);

    if (success) {
      toast.success("Provisioning-Link kopiert.");
    } else {
      toast.error("Automatisches Kopieren blockiert - bitte Link im Feld markieren und manuell kopieren.");
    }
  }

  function openInLinphone() {
    if (!provisioning) return;
    const uri = buildLinphoneConfigUri(provisioning.provisioning_path);
    // Inside Home Assistant's ingress <iframe>, navigating window.location only
    // moves the iframe - the browser never sees it as a top-level navigation, so
    // it won't offer to hand the custom "linphone-config:" scheme to the OS/app.
    // Navigate the top window instead (same-origin under ingress), falling back
    // to the local window if that's blocked (e.g. direct, non-ingress access).
    try {
      if (window.top && window.top !== window) {
        window.top.location.href = uri;
        return;
      }
    } catch {
      // cross-origin or blocked - fall through
    }
    window.location.href = uri;
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Linphone QR fuer Nebenstelle {extension.number}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="mx-auto h-72 w-72" style={{ background: "rgba(255,255,255,0.05)" }} />
            <Skeleton className="h-10 w-full" style={{ background: "rgba(255,255,255,0.05)" }} />
          </div>
        ) : provisioning ? (
          <div className="space-y-4">
            <div
              className="mx-auto flex w-full max-w-[320px] items-center justify-center rounded-xl border p-4"
              style={{ borderColor: "rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)" }}
            >
              {qrCodeDataUrl ? (
                <img
                  src={qrCodeDataUrl}
                  alt={`Linphone QR fuer Extension ${provisioning.extension_number}`}
                  className="h-72 w-72 rounded-lg"
                />
              ) : (
                <Skeleton className="h-72 w-72" style={{ background: "rgba(255,255,255,0.05)" }} />
              )}
            </div>

            <div className="space-y-2">
              <p className="text-sm text-foreground">
                {provisioning.display_name} ({provisioning.extension_number})
              </p>
              <p className="text-xs text-muted-foreground">
                In Linphone "Scan QR Code" waehlen. Fuer die manuelle Einrichtung unten den Provisioning-Link in Linphone unter "Provisioning Link" einfuegen.
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Provisioning-Link</p>
              <div className="flex gap-2">
                <Input
                  readOnly
                  value={buildProvisioningUrl(provisioning.provisioning_path)}
                  className="font-mono text-xs"
                />
                <Button type="button" variant="outline" onClick={copyProvisioningLink} className="cursor-pointer shrink-0">
                  <Copy className="mr-2 h-4 w-4" />
                  Kopieren
                </Button>
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={openInLinphone} className="cursor-pointer">
                In Linphone oeffnen
              </Button>
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} className="cursor-pointer">
            Schliessen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ProvisionedDeviceSummary {
  id: number;
  name: string;
  mac: string;
  extension_numbers: number[];
}
interface ExtensionContact {
  user_agent: string;
  uri: string;
}
interface ExtensionLiveInfo {
  contacts: number;
  contacts_detail: ExtensionContact[];
}

function contactHost(uri: string): string {
  const match = uri.match(/@([^:;]+)/);
  return match ? match[1] : "";
}

// ---- Main page ----
export default function Extensions() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, "Online" | "Offline">>({});
  const [devices, setDevices] = useState<ProvisionedDeviceSummary[]>([]);
  const [liveInfo, setLiveInfo] = useState<Record<string, ExtensionLiveInfo>>({});
  const [loading, setLoading] = useState(true);
  const [dialogMode, setDialogMode] = useState<"add" | "edit" | null>(null);
  const [editTarget, setEditTarget] = useState<Extension | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Extension | null>(null);
  const [qrTarget, setQrTarget] = useState<Extension | null>(null);
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
      toast.error("Ring Groups konnten nicht geladen werden.");
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
    <div className="space-y-8">

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Nebenstellen</h1>
          <p className="mt-1 text-sm text-muted-foreground">SIP-Nebenstellen verwalten</p>
        </div>
        <Button
          onClick={() => setDialogMode("add")}
          className="cursor-pointer gap-1.5"
          style={{
            background: "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
            boxShadow: "0 0 16px rgba(124,58,237,0.3)",
            border: "none",
          }}
        >
          <Plus className="h-4 w-4" />
          Nebenstelle hinzufügen
        </Button>
      </div>

      {/* Table / empty state */}
      {loading ? (
        <div className="glass rounded-xl p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-10 w-full" style={{ background: "rgba(255,255,255,0.05)" }} />
          ))}
        </div>
      ) : extensions.length === 0 ? (
        <div
          className="glass flex flex-col items-center justify-center rounded-xl py-20 text-center"
        >
          <div
            className="mb-4 flex h-14 w-14 items-center justify-center rounded-full"
            style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)" }}
          >
            <Phone className="h-6 w-6 text-violet-400" />
          </div>
          <h2 className="text-base font-semibold text-foreground">Noch keine Nebenstellen</h2>
          <p className="mt-1.5 max-w-xs text-sm text-muted-foreground">
            Füge deine erste Extension hinzu, damit SIP-Telefone sich registrieren können.
          </p>
        </div>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
          <Table>
            <TableHeader>
              <TableRow style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Nummer
                </TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Name
                </TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Status
                </TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Ring Groups
                </TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Geräte
                </TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Aktiv
                </TableHead>
                <TableHead className="text-right text-xs font-medium uppercase tracking-widest text-muted-foreground">
                  Aktionen
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {extensions.map((ext) => (
                <TableRow
                  key={ext.id}
                  style={{ borderColor: "rgba(255,255,255,0.04)" }}
                  className="transition-colors duration-100 hover:bg-white/[0.02]"
                >
                  <TableCell className="font-mono font-medium text-violet-300">
                    {ext.number}
                  </TableCell>
                  <TableCell className="font-medium text-foreground">{ext.display_name}</TableCell>
                  <TableCell>
                    <StatusDot status={statusMap[String(ext.number)]} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {ringGroups
                      .filter((group) =>
                        group.extension_numbers
                          .split(",")
                          .map((number) => number.trim())
                          .includes(String(ext.number))
                      )
                      .map((group) => group.name)
                      .join(", ") || "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {(() => {
                      const assignedDevices = devices.filter((d) =>
                        d.extension_numbers.includes(ext.number)
                      );
                      const contacts = liveInfo[String(ext.number)]?.contacts_detail ?? [];
                      if (assignedDevices.length === 0 && contacts.length === 0) return "—";
                      return (
                        <div className="flex flex-col gap-0.5">
                          {assignedDevices.map((d) => (
                            <span key={d.id} className="text-xs">
                              {d.name || d.mac}
                            </span>
                          ))}
                          {contacts.map((c, i) => (
                            <span key={i} className="text-xs text-emerald-400/80">
                              {c.user_agent || contactHost(c.uri) || "unbekanntes Gerät"} verbunden
                            </span>
                          ))}
                        </div>
                      );
                    })()}
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={ext.enabled}
                      onCheckedChange={() => toggleEnabled(ext)}
                      aria-label={`${ext.enabled ? "Deaktivieren" : "Aktivieren"} ${ext.number}`}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 cursor-pointer opacity-60 hover:opacity-100"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Aktionen für Nebenstelle {ext.number}</span>
                            </Button>
                          </DropdownMenuTrigger>
                        </TooltipTrigger>
                        <TooltipContent>Aktionen</TooltipContent>
                      </Tooltip>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          className="cursor-pointer"
                          onClick={() => setQrTarget(ext)}
                        >
                          <QrCode className="mr-2 h-4 w-4" />
                          Linphone QR
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="cursor-pointer"
                          onClick={() => {
                            setEditTarget(ext);
                            setDialogMode("edit");
                          }}
                        >
                          <Pencil className="mr-2 h-4 w-4" />
                          Bearbeiten
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="cursor-pointer text-destructive focus:text-destructive"
                          onClick={() => setDeleteTarget(ext)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Löschen
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
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

      {qrTarget && (
        <LinphoneQrDialog
          extension={qrTarget}
          onClose={() => setQrTarget(null)}
        />
      )}
    </div>
  );
}
