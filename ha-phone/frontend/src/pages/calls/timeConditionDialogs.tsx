import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { type DestinationType, type Extension, type IVRMenu, type RingGroup, type TimeCondition } from "@/types/api";
import { DestinationField, type DestinationValue } from "@/components/DestinationField";
import { FormGrid, FormSpan } from "@/components/FormGrid";
import { WEEKDAYS, WEEKDAY_LABELS, formatDays, parseDays, type Weekday } from "@/lib/weekdays";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const timeConditionSchema = z
  .object({
    name: z.string().min(1, "Pflichtfeld").max(64, "Max. 64 Zeichen"),
    did: z.string().min(1, "Pflichtfeld").max(32, "Max. 32 Zeichen"),
    open_hours_start: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
    open_hours_end: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
    open_days: z.string().min(1, "Pflichtfeld"),
    open_destination: z.coerce.number().int().min(0),
    open_dest_type: z
      .enum(["extension", "ring_group", "ivr", "voicemail", "hangup"])
      .default("extension"),
    closed_destination: z.coerce.number().int().min(0),
    closed_dest_type: z
      .enum(["extension", "ring_group", "ivr", "voicemail", "hangup"])
      .default("voicemail"),
  })
  .refine((data) => data.open_dest_type === "hangup" || data.open_destination >= 1, {
    message: "Pflichtfeld",
    path: ["open_destination"],
  })
  .refine((data) => data.closed_dest_type === "hangup" || data.closed_destination >= 1, {
    message: "Pflichtfeld",
    path: ["closed_destination"],
  });

type TimeConditionFormValues = z.infer<typeof timeConditionSchema>;

const TIME_CONDITION_ALLOWED_DESTINATION_TYPES: DestinationType[] = [
  "extension",
  "ring_group",
  "ivr",
  "voicemail",
  "hangup",
];

// ---- Weekday picker (Business Hours UI, Roadmap Phase B.3) ----
// Replaces the free-text "mon-fri" input with toggle buttons. Converts to/
// from the same Asterisk GotoIfTime day format the backend already stores,
// so no API/model change was needed - a hand-typed value from before this
// existed still parses fine (unknown tokens are just ignored).
function WeekdayPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const selected = parseDays(value);

  function toggle(day: Weekday) {
    const next = new Set(selected);
    if (next.has(day)) next.delete(day);
    else next.add(day);
    onChange(formatDays(next));
  }

  return (
    <div className="flex gap-1.5">
      {WEEKDAYS.map((day) => {
        const active = selected.has(day);
        return (
          <button
            key={day}
            type="button"
            onClick={() => toggle(day)}
            aria-pressed={active}
            className={`h-9 flex-1 rounded-md border text-xs font-medium transition-colors cursor-pointer ${
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input bg-card text-muted-foreground hover:text-foreground"
            }`}
          >
            {WEEKDAY_LABELS[day]}
          </button>
        );
      })}
    </div>
  );
}

// ---- Zeitsteuerung anlegen ----
export function AddTimeConditionDialog({
  open,
  onClose,
  onCreated,
  extensions,
  ringGroups,
  ivrMenus,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (tc: TimeCondition) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
}) {
  const form = useForm<TimeConditionFormValues>({
    resolver: zodResolver(timeConditionSchema),
    defaultValues: {
      name: "",
      did: "",
      open_hours_start: "07:00",
      open_hours_end: "22:00",
      open_days: "mon-sun",
      open_destination: undefined as unknown as number,
      open_dest_type: "extension",
      closed_destination: undefined as unknown as number,
      closed_dest_type: "voicemail",
    },
  });
  const [saving, setSaving] = useState(false);

  async function onSubmit(values: TimeConditionFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/time-conditions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen. Läuft die Anlage?"));
      const created: TimeCondition = await resp.json();
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
        <DialogHeader><DialogTitle>Zeitsteuerung anlegen</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormGrid>
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input placeholder="z. B. Geschäftszeiten" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="did" render={({ field }) => (
                <FormItem>
                  <FormLabel>Angerufene Rufnummer (DID)</FormLabel>
                  <FormControl><Input placeholder="z. B. +4922222222" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormSpan>
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Geöffnet ab</FormLabel>
                      <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Geöffnet bis</FormLabel>
                      <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>
              </FormSpan>
              <FormSpan>
                <FormField control={form.control} name="open_days" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Geöffnete Tage</FormLabel>
                    <FormControl><WeekdayPicker value={field.value} onChange={field.onChange} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </FormSpan>
              <DestinationField
                value={{ type: form.watch("open_dest_type"), target: form.watch("open_destination") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("open_dest_type", next.type);
                  form.setValue("open_destination", (next.target ?? 0) as number);
                }}
                allowedTypes={TIME_CONDITION_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Ziel bei geöffnet"
                error={form.formState.errors.open_destination?.message as string | undefined}
              />
              <DestinationField
                value={{ type: form.watch("closed_dest_type"), target: form.watch("closed_destination") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("closed_dest_type", next.type);
                  form.setValue("closed_destination", (next.target ?? 0) as number);
                }}
                allowedTypes={TIME_CONDITION_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Ziel bei geschlossen"
                error={form.formState.errors.closed_destination?.message as string | undefined}
              />
            </FormGrid>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
              <Button type="submit" disabled={saving}>{saving ? "Speichert…" : "Zeitsteuerung speichern"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Zeitsteuerung bearbeiten ----
export function EditTimeConditionDialog({
  condition,
  onClose,
  onUpdated,
  extensions,
  ringGroups,
  ivrMenus,
}: {
  condition: TimeCondition;
  onClose: () => void;
  onUpdated: (tc: TimeCondition) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
}) {
  const form = useForm<TimeConditionFormValues>({
    resolver: zodResolver(timeConditionSchema),
    defaultValues: {
      name: condition.name,
      did: condition.did,
      open_hours_start: condition.open_hours_start,
      open_hours_end: condition.open_hours_end,
      open_days: condition.open_days,
      open_destination: condition.open_destination,
      open_dest_type: condition.open_dest_type,
      closed_destination: condition.closed_destination,
      closed_dest_type: condition.closed_dest_type,
    },
  });
  const [saving, setSaving] = useState(false);

  async function onSubmit(values: TimeConditionFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/time-conditions/${condition.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen. Läuft die Anlage?"));
      const updated: TimeCondition = await resp.json();
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
        <DialogHeader><DialogTitle>Zeitsteuerung bearbeiten</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormGrid>
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input placeholder="z. B. Geschäftszeiten" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="did" render={({ field }) => (
                <FormItem>
                  <FormLabel>Angerufene Rufnummer (DID)</FormLabel>
                  <FormControl><Input placeholder="z. B. +4922222222" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormSpan>
                <div className="grid grid-cols-2 gap-4">
                  <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Geöffnet ab</FormLabel>
                      <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Geöffnet bis</FormLabel>
                      <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                </div>
              </FormSpan>
              <FormSpan>
                <FormField control={form.control} name="open_days" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Geöffnete Tage</FormLabel>
                    <FormControl><WeekdayPicker value={field.value} onChange={field.onChange} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </FormSpan>
              <DestinationField
                value={{ type: form.watch("open_dest_type"), target: form.watch("open_destination") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("open_dest_type", next.type);
                  form.setValue("open_destination", (next.target ?? 0) as number);
                }}
                allowedTypes={TIME_CONDITION_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Ziel bei geöffnet"
                error={form.formState.errors.open_destination?.message as string | undefined}
              />
              <DestinationField
                value={{ type: form.watch("closed_dest_type"), target: form.watch("closed_destination") }}
                onChange={(next: DestinationValue) => {
                  form.setValue("closed_dest_type", next.type);
                  form.setValue("closed_destination", (next.target ?? 0) as number);
                }}
                allowedTypes={TIME_CONDITION_ALLOWED_DESTINATION_TYPES}
                extensions={extensions}
                ringGroups={ringGroups}
                ivrMenus={ivrMenus}
                keyBy="id"
                label="Ziel bei geschlossen"
                error={form.formState.errors.closed_destination?.message as string | undefined}
              />
            </FormGrid>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
              <Button type="submit" disabled={saving}>{saving ? "Speichert…" : "Zeitsteuerung speichern"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
