import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import type { DoorAction, Extension } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { zodFormResolver } from "@/lib/zodFormResolver";
import { DoorActionsEditor, doorActionsError } from "@/components/DoorActionsEditor";
import { SnapshotTestButton } from "@/components/SnapshotTestButton";
import { ToggleRow } from "@/components/ToggleRow";
import { FormGrid, FormSpan } from "@/components/FormGrid";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { doorDefaults, doorPatchBody, doorSchema, type DoorFormValues } from "./doorSchema";

export function DoorSettingsDialog({
  extension,
  onClose,
  onSaved,
}: {
  extension: Extension;
  onClose: () => void;
  onSaved: (updated: Extension) => void;
}) {
  const form = useForm<DoorFormValues>({ resolver: zodFormResolver(doorSchema), defaultValues: doorDefaults(extension) });
  const [doorActions, setDoorActions] = useState<DoorAction[]>(extension.door_actions ?? []);
  const [saving, setSaving] = useState(false);
  const isDoor = form.watch("is_door");

  async function onSubmit(values: DoorFormValues) {
    const actionsError = doorActionsError(doorActions);
    if (actionsError) {
      toast.error(actionsError);
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch(`/api/extensions/${extension.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(doorPatchBody(values, doorActions)),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      const updated: Extension = await resp.json();
      onSaved(updated);
      toast.success("Türstation gespeichert.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>Türstation {extension.number} · {extension.display_name}</DialogTitle>
          <DialogDescription>Tür öffnen, Klingelbild und Aktionen für die App.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormGrid>
              <FormField
                control={form.control}
                name="is_door"
                render={({ field }) => (
                  <ToggleRow
                    id={field.name}
                    label="Türstation"
                    description="Diese Nebenstelle ist eine Türklingel oder Türsprechstelle (Akuvox, 2N, DoorBird, Fanvil …). Nur Türstationen erscheinen im Klingel-Verlauf, klingeln in der App als Tür und bekommen Tür öffnen, Klingelbild und Aktionen."
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
                    description={"Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte SIP-Geräte, die Namen als „Anonym“ anzeigen."}
                    checked={field.value}
                    onToggle={field.onChange}
                  />
                )}
              />
              {isDoor && (
                <>
                  <FormField
                    control={form.control}
                    name="door_open_code"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Tür-Öffnen-Code (DTMF)</FormLabel>
                        <FormControl><Input placeholder="z. B. *1" {...field} /></FormControl>
                        <p className="text-xs text-muted-foreground">
                          Die HA-Phone App zeigt beim Klingeln und im Gespräch die Taste „Tür öffnen“ und sendet diese Tasten.
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="door_open_webhook"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Tür-Öffnen-Webhook</FormLabel>
                        <FormControl>
                          <Input placeholder="z. B. http://homeassistant.local:8123/api/webhook/haustuer" className="font-mono" {...field} />
                        </FormControl>
                        <p className="text-xs text-muted-foreground">
                          Der Schieberegler „Zum Öffnen schieben“ in der HA-Phone App ruft diese Adresse auf (POST mit JSON), auch schon während es klingelt. Die App sieht die Adresse nie. Leer = die App sendet im Gespräch den Tür-Öffnen-Code.
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="doorbell_camera"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Klingelbild-Quelle</FormLabel>
                        <FormControl>
                          <Input placeholder="camera.haustuer oder http://tuer.local/snapshot.jpg" className="font-mono" {...field} />
                        </FormControl>
                        <p className="text-xs text-muted-foreground">
                          Bei jedem Klingeln holt die Anlage hier ein Foto für den Klingel-Verlauf und die App. Eine Home-Assistant-Kamera (<code>camera.…</code>) oder die Snapshot-Adresse der Türstation, Zugangsdaten als <code>http://benutzer:passwort@…</code>. Leer = Klingeln ohne Foto.
                        </p>
                        <SnapshotTestButton source={field.value ?? ""} />
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormSpan><DoorActionsEditor value={doorActions} onChange={setDoorActions} /></FormSpan>
                </>
              )}
            </FormGrid>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
              <Button type="submit" disabled={saving}>{saving ? "Speichert…" : "Speichern"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
