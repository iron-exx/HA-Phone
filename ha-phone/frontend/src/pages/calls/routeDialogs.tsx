import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { type DestinationType, type Extension, type IVRMenu, type RingGroup, type Route } from "@/types/api";
import { DestinationField, formatDestination, type DestinationValue } from "@/components/DestinationField";
import { FormGrid } from "@/components/FormGrid";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

// ---- Zod schemas ----
const routeSchema = z
  .object({
    did: z.string().min(1, "Pflichtfeld").max(32, "Max. 32 Zeichen"),
    destination_type: z
      .enum(["extension", "ring_group", "ivr", "voicemail", "hangup"])
      .default("extension"),
    destination_id: z.coerce.number().int().min(0),
  })
  .refine((data) => data.destination_type === "hangup" || data.destination_id >= 1, {
    message: "Pflichtfeld",
    path: ["destination_id"],
  });

const ROUTE_ALLOWED_DESTINATION_TYPES: DestinationType[] = [
  "extension",
  "ring_group",
  "ivr",
  "voicemail",
  "hangup",
];

type RouteFormValues = z.infer<typeof routeSchema>;

export function formatRouteDestination(route: Route, extensions: Extension[], ringGroups: RingGroup[], ivrMenus: IVRMenu[]) {
  return formatDestination(
    { type: route.destination_type, target: route.destination_id },
    extensions,
    ringGroups,
    ivrMenus,
    "id"
  );
}

// ---- Route anlegen ----
export function AddRouteDialog({
  open,
  onClose,
  onCreated,
  extensions,
  ringGroups,
  ivrMenus,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (route: Route) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
}) {
  const form = useForm<RouteFormValues>({
    resolver: zodResolver(routeSchema),
    defaultValues: {
      did: "",
      destination_type: "extension",
      destination_id: undefined as unknown as number,
    },
  });
  const [saving, setSaving] = useState(false);
  const destinationType = form.watch("destination_type");

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen. Läuft die Anlage?"));
      const created: Route = await resp.json();
      onCreated(created);
      toast.success("Gespeichert.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen. Läuft die Anlage?"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>Rufnummern-Route anlegen</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormGrid>
              <FormField
                control={form.control}
                name="did"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Angerufene Rufnummer (DID)</FormLabel>
                    <FormControl>
                      <Input placeholder="z. B. +4922222222" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DestinationField
                value={{ type: destinationType, target: form.watch("destination_id") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("destination_type", next.type);
                  form.setValue("destination_id", (next.target ?? 0) as number);
                }}
                allowedTypes={ROUTE_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Zieltyp"
                error={form.formState.errors.destination_id?.message as string | undefined}
              />
            </FormGrid>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Speichert…" : "Route speichern"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Route bearbeiten ----
export function EditRouteDialog({
  route,
  onClose,
  onUpdated,
  extensions,
  ringGroups,
  ivrMenus,
}: {
  route: Route;
  onClose: () => void;
  onUpdated: (route: Route) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
}) {
  const form = useForm<RouteFormValues>({
    resolver: zodResolver(routeSchema),
    defaultValues: {
      did: route.did,
      destination_type: route.destination_type,
      destination_id: route.destination_id,
    },
  });
  const [saving, setSaving] = useState(false);
  const destinationType = form.watch("destination_type");

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/routes/${route.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen. Läuft die Anlage?"));
      const updated: Route = await resp.json();
      onUpdated(updated);
      toast.success("Gespeichert.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen. Läuft die Anlage?"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>Rufnummern-Route bearbeiten</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormGrid>
              <FormField control={form.control} name="did" render={({ field }) => (
                <FormItem>
                  <FormLabel>Angerufene Rufnummer (DID)</FormLabel>
                  <FormControl><Input placeholder="z. B. +4922222222" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <DestinationField
                value={{ type: destinationType, target: form.watch("destination_id") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("destination_type", next.type);
                  form.setValue("destination_id", (next.target ?? 0) as number);
                }}
                allowedTypes={ROUTE_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Zieltyp"
                error={form.formState.errors.destination_id?.message as string | undefined}
              />
            </FormGrid>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
              <Button type="submit" disabled={saving}>{saving ? "Speichert…" : "Route speichern"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
