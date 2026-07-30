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
  type IVRMenu,
  type PresenceForwardingRule,
  type LinphoneProvisioningInfo,
} from "@/types/api";
import { DestinationField, formatDestination, type DestinationValue } from "@/components/DestinationField";
import { Button } from "@/components/ui/button";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { copyToClipboard } from "@/lib/clipboard";

// ---- Zod schema ----
const extensionSchema = z.object({
  number: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
  display_name: z.string().min(1, "Required").max(64, "Max 64 chars"),
  sip_password: z.string().min(8, "Min 8 characters"),
  enabled: z.boolean(),
  video_capable: z.boolean().default(false),
  internal_only: z.boolean().default(false),
  numeric_callerid: z.boolean().default(false),
});

type ExtensionFormValues = z.infer<typeof extensionSchema>;

const PRESENCE_STATUSES: { value: string; label: string }[] = [
  { value: "available", label: "Verfügbar" },
  { value: "away", label: "Abwesend" },
  { value: "lunch", label: "Mittagspause" },
  { value: "do_not_disturb", label: "Nicht stören" },
  { value: "off_work", label: "Feierabend" },
];

const editSchema = extensionSchema.extend({
  sip_password: z
    .string()
    .refine((v) => v === "" || v.length >= 8, "Min 8 characters if provided"),
  presence_status: z.string().default("available"),
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

/**
 * A labelled on/off row for a boolean form field.
 *
 * Uses a self-contained <button> toggle with INLINE colors instead of the
 * Radix Switch. Why: the Radix Switch's track/thumb colours come from Tailwind
 * theme classes (bg-input/bg-primary/bg-foreground + CSS variables). In the
 * deployed build those resolved to transparent (verified: computed
 * background-color rgba(0,0,0,0) on both track and thumb), so the switch was
 * effectively invisible - users saw only the row border and nothing to click.
 * Inline style colours render identically in every browser (including the
 * older embedded browsers this add-on gets opened in) with no dependency on
 * Tailwind variable resolution.
 *
 * A real <button role="switch"> is a labelable element, so the <label htmlFor>
 * still forwards a click from the text exactly once - single toggle, no
 * double-fire, no row-level onClick. Do NOT reintroduce a row-level onClick.
 */
function ToggleRow({
  id,
  label,
  description,
  checked,
  onToggle,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <div
      className="flex items-center justify-between rounded-lg border p-3"
      style={{ borderColor: "rgba(255,255,255,0.08)" }}
    >
      <label htmlFor={id} className="flex-1 cursor-pointer pr-3">
        <div className="text-sm font-medium leading-none">{label}</div>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </label>
      <ToggleSwitch id={id} checked={checked} ariaLabel={label} onToggle={() => onToggle(!checked)} />
    </div>
  );
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
    defaultValues: { number: undefined as unknown as number, display_name: "", sip_password: "", enabled: true, video_capable: false, internal_only: false, numeric_callerid: false },
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
              name="video_capable"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Video-fähig"
                  description="Erlaubt Videotelefonie (H.264) — z.B. Video-Türsprechstelle oder Linphone. Beide Gesprächsseiten müssen video-fähig sein."
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />
            <FormField
              control={form.control}
              name="internal_only"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Nur intern"
                  description="Kann nur intern telefonieren — kein Anruf nach außen (z.B. Türsprechstelle)."
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />
            <FormField
              control={form.control}
              name="numeric_callerid"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Altgeräte-Modus"
                  description={'Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte SIP-Clients (z.B. Android nativ), die Namen als "Anonym" anzeigen.'}
                  checked={field.value}
                  onToggle={field.onChange}
                />
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
      video_capable: extension.video_capable ?? false,
      internal_only: extension.internal_only ?? false,
      numeric_callerid: extension.numeric_callerid ?? false,
      presence_status: extension.presence_status || "available",
    },
  });
  const [saving, setSaving] = useState(false);
  const [selectedRingGroupIds, setSelectedRingGroupIds] = useState<number[]>(
    getExtensionRingGroupIds(extension, ringGroups)
  );

  async function onSubmit(values: EditFormValues) {
    setSaving(true);
    const body: Partial<{ display_name: string; sip_password: string; enabled: boolean; video_capable: boolean; internal_only: boolean; numeric_callerid: boolean; presence_status: string }> = {
      display_name: values.display_name,
      enabled: values.enabled,
      video_capable: values.video_capable,
      internal_only: values.internal_only,
      numeric_callerid: values.numeric_callerid,
      presence_status: values.presence_status,
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
              name="video_capable"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Video-fähig"
                  description="Erlaubt Videotelefonie (H.264) — z.B. Video-Türsprechstelle oder Linphone. Beide Gesprächsseiten müssen video-fähig sein."
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />
            <FormField
              control={form.control}
              name="internal_only"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Nur intern"
                  description="Kann nur intern telefonieren — kein Anruf nach außen (z.B. Türsprechstelle)."
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />
            <FormField
              control={form.control}
              name="numeric_callerid"
              render={({ field }) => (
                <ToggleRow
                  id={field.name}
                  label="Altgeräte-Modus"
                  description={'Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte SIP-Clients (z.B. Android nativ), die Namen als "Anonym" anzeigen.'}
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />
            <FormField
              control={form.control}
              name="presence_status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Presence-Status</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {PRESENCE_STATUSES.map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Bestimmt, welche Weiterleitungsregel (falls konfiguriert) für diesen Status
                    gilt — siehe Weiterleitungsregeln unten in der Nebenstellen-Liste.
                  </p>
                  <FormMessage />
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
    await copyToClipboard(buildProvisioningUrl(provisioning.provisioning_path), "Provisioning-Link kopiert.");
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
const DIRECTION_LABELS: Record<string, string> = { internal: "Intern", external: "Extern" };
const MODE_LABELS: Record<string, string> = {
  ring_then_dest: "Klingeln, dann weiterleiten",
  always_dest: "Sofort weiterleiten",
};
const PRESENCE_STATUS_ALLOWED_DESTINATION_TYPES = ["extension", "ring_group", "ivr", "voicemail", "hangup"] as const;

// ---- Presence-based forwarding rules ----
// Configures what happens to a call reaching a specific extension while it is
// in a specific presence status, separately for internal vs external calls.
// No rule for a given (extension, status, direction) = the extension's
// unchanged default behavior (ring, then its own voicemail on no-answer).
function PresenceRulesSection() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [ivrMenus, setIvrMenus] = useState<IVRMenu[]>([]);
  const [rules, setRules] = useState<PresenceForwardingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [extensionId, setExtensionId] = useState<number | "">("");
  const [status, setStatus] = useState(PRESENCE_STATUSES[0].value);
  const [direction, setDirection] = useState<"internal" | "external">("internal");
  const [mode, setMode] = useState<"ring_then_dest" | "always_dest">("ring_then_dest");
  const [ringTimeout, setRingTimeout] = useState("20");
  const [dest, setDest] = useState<DestinationValue>({ type: "voicemail", target: undefined });

  function load() {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
      fetch("/api/ivrs").then((r) => r.json()),
      fetch("/api/presence-rules").then((r) => r.json()),
    ])
      .then(([extData, rgData, ivrData, ruleData]: [Extension[], RingGroup[], IVRMenu[], PresenceForwardingRule[]]) => {
        setExtensions(extData);
        setRingGroups(rgData);
        setIvrMenus(ivrData);
        setRules(ruleData);
      })
      .catch(() => toast.error("Weiterleitungsregeln konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function extensionLabel(id: number) {
    const ext = extensions.find((e) => e.id === id);
    return ext ? `${ext.number} ${ext.display_name}` : `#${id}`;
  }

  async function addRule() {
    if (extensionId === "") {
      toast.error("Nebenstelle ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/presence-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          extension_id: extensionId,
          status,
          direction,
          mode,
          dest_type: dest.type,
          dest_target: dest.target ?? 0,
          ring_timeout: Number(ringTimeout) || 20,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      load();
      toast.success("Regel gespeichert.");
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: number) {
    try {
      const resp = await fetch(`/api/presence-rules/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      setRules((rs) => rs.filter((r) => r.id !== id));
      toast.success("Regel gelöscht.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Löschen."));
    }
  }

  return (
    <div className="mt-8">
      <Separator className="mb-8" />
      <div className="mb-2">
        <h2 className="text-xl font-semibold">Presence-Weiterleitung</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Legt fest, wohin ein Anruf geht, solange eine Nebenstelle in einem bestimmten
          Presence-Status ist (getrennt nach internen und externen Anrufen). Ohne Regel bleibt
          das Standardverhalten (klingeln, dann eigene Voicemail) unverändert.
        </p>
      </div>
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nebenstelle</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Richtung</TableHead>
              <TableHead>Verhalten</TableHead>
              <TableHead>Ziel</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{extensionLabel(r.extension_id)}</TableCell>
                <TableCell>{PRESENCE_STATUSES.find((s) => s.value === r.status)?.label || r.status}</TableCell>
                <TableCell>{DIRECTION_LABELS[r.direction] || r.direction}</TableCell>
                <TableCell>
                  {MODE_LABELS[r.mode] || r.mode}
                  {r.mode === "ring_then_dest" && <span className="text-muted-foreground"> ({r.ring_timeout}s)</span>}
                </TableCell>
                <TableCell>{formatDestination({ type: r.dest_type, target: r.dest_target }, extensions, ringGroups, ivrMenus, "id")}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    aria-label="Regel löschen"
                    onClick={() => deleteRule(r.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {!loading && (
        <div className="mt-4 grid grid-cols-1 gap-3 rounded-md border border-white/10 bg-white/[0.02] p-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="text-xs text-muted-foreground">Nebenstelle</label>
            <select
              value={extensionId}
              onChange={(e) => setExtensionId(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="">Wählen…</option>
              {extensions.map((ext) => (
                <option key={ext.id} value={ext.id}>{ext.number} {ext.display_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              {PRESENCE_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Richtung</label>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as "internal" | "external")}
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="internal">Intern</option>
              <option value="external">Extern</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Verhalten</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "ring_then_dest" | "always_dest")}
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="ring_then_dest">Klingeln, dann weiterleiten</option>
              <option value="always_dest">Sofort weiterleiten</option>
            </select>
          </div>
          {mode === "ring_then_dest" && (
            <div>
              <label className="text-xs text-muted-foreground">Klingeldauer (Sekunden)</label>
              <input
                type="number"
                min={1}
                value={ringTimeout}
                onChange={(e) => setRingTimeout(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
          )}
          <div className="sm:col-span-2 lg:col-span-3">
            <DestinationField
              value={dest}
              onChange={setDest}
              allowedTypes={[...PRESENCE_STATUS_ALLOWED_DESTINATION_TYPES]}
              extensions={extensions}
              ringGroups={ringGroups}
              ivrMenus={ivrMenus}
              keyBy="id"
              label="Zieltyp"
            />
          </div>
          <div className="sm:col-span-2 lg:col-span-3">
            <Button size="sm" onClick={addRule} disabled={saving}>{saving ? "…" : "Regel speichern"}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

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
                    <ToggleSwitch
                      checked={ext.enabled}
                      ariaLabel={`${ext.enabled ? "Deaktivieren" : "Aktivieren"} ${ext.number}`}
                      onToggle={() => toggleEnabled(ext)}
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

      <PresenceRulesSection />

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
