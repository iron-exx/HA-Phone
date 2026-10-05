import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import type { Extension, RingGroup } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { zodFormResolver } from "@/lib/zodFormResolver";
import { FormGrid, FormSection } from "@/components/FormGrid";
import { ToggleRow } from "@/components/ToggleRow";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { extensionSchema, type ExtensionFormValues } from "./schema";
import { syncRingGroupMemberships } from "./ringGroupMembership";
import { RingGroupPicker } from "./RingGroupPicker";

export function AddExtensionDialog({
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
    resolver: zodFormResolver(extensionSchema),
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
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>Nebenstelle anlegen</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormSection title="Allgemein">
              <FormGrid>
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
                      <FormLabel>SIP-Passwort</FormLabel>
                      <FormControl>
                        <div className="flex gap-2">
                          <Input type="text" placeholder="Auto-generiert" className="font-mono" {...field} />
                          <Button type="button" variant="outline" onClick={generatePassword}
                            className="shrink-0">
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
              </FormGrid>
            </FormSection>
            <RingGroupPicker ringGroups={ringGroups} selectedIds={selectedRingGroupIds} onChange={setSelectedRingGroupIds} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Speichert…" : "Speichern"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
