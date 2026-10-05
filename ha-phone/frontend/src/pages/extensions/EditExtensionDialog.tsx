import { useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { toast } from "sonner";
import type { Extension, RingGroup } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { zodFormResolver } from "@/lib/zodFormResolver";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { editDefaults, editPatchBody, editSchema, type EditFormValues } from "./schema";
import { getExtensionRingGroupIds, syncRingGroupMemberships } from "./ringGroupMembership";
import { EXTENSION_TABS, FIELD_TAB, firstTabWithError, isExtensionTab, type ExtensionTab } from "./editTabs";
import { EditGeneralTab } from "./EditGeneralTab";
import { EditAppTab } from "./EditAppTab";
import { EditReachTab } from "./EditReachTab";

export function EditExtensionDialog({
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
  const form = useForm<EditFormValues>({ resolver: zodFormResolver(editSchema), defaultValues: editDefaults(extension) });
  const [tab, setTab] = useState<ExtensionTab>("general");
  const [saving, setSaving] = useState(false);
  const [selectedRingGroupIds, setSelectedRingGroupIds] = useState<number[]>(() => getExtensionRingGroupIds(extension, ringGroups));

  async function onSubmit(values: EditFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/extensions/${extension.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editPatchBody(values)),
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

  function onInvalid(errors: FieldErrors<EditFormValues>) {
    const target = firstTabWithError(errors);
    if (target) setTab(target);
    const first = Object.keys(errors)
      .map((field) => field as keyof EditFormValues)
      .find((field) => FIELD_TAB[field] === target);
    // Der Reiter-Inhalt wird erst nach dem Wechsel gerendert – danach fokussieren.
    if (first) setTimeout(() => form.setFocus(first), 0);
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>Nebenstelle {extension.number} bearbeiten</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-4">
            <Tabs value={tab} onValueChange={(v) => { if (isExtensionTab(v)) setTab(v); }}>
              <TabsList aria-label="Bereiche der Nebenstelle">
                {EXTENSION_TABS.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
              </TabsList>
              <TabsContent value="general" forceMount>
                <EditGeneralTab
                  form={form}
                  ringGroups={ringGroups}
                  selectedRingGroupIds={selectedRingGroupIds}
                  onSelectedRingGroupIdsChange={setSelectedRingGroupIds}
                />
              </TabsContent>
              <TabsContent value="app" forceMount><EditAppTab form={form} extension={extension} /></TabsContent>
              <TabsContent value="reach" forceMount><EditReachTab form={form} extensionId={extension.id} /></TabsContent>
            </Tabs>
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
