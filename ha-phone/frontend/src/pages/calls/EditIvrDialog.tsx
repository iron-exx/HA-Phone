import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodFormResolver } from "@/lib/zodFormResolver";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Trash2, Upload, Volume2 } from "lucide-react";
import { type Extension, type RingGroup, type IVRMenu, type IVROption } from "@/types/api";
import { DestinationField } from "@/components/DestinationField";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { ivrSchema, IVR_OPTION_ALLOWED_DESTINATION_TYPES, type IVRFormValues } from "./ivrSchema";

export function EditIvrDialog({
  ivr,
  onClose,
  onUpdated,
  extensions,
  ringGroups,
  ivrs,
}: {
  ivr: IVRMenu;
  onClose: () => void;
  onUpdated: (ivr: IVRMenu) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrs: IVRMenu[];
}) {
  const parsedOptions: IVROption[] = (() => {
    try { return JSON.parse(ivr.options || "[]"); } catch { return []; }
  })();

  const form = useForm<IVRFormValues>({
    resolver: zodFormResolver(ivrSchema),
    defaultValues: {
      number: ivr.number,
      name: ivr.name,
      timeout: ivr.timeout,
      max_invalid_tries: ivr.max_invalid_tries,
    },
  });
  const [saving, setSaving] = useState(false);
  const [options, setOptions] = useState<IVROption[]>(parsedOptions);
  const [greetingFile, setGreetingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function addOption() {
    setOptions([...options, { key: String(options.length + 1), action: "extension", target: undefined, label: "" }]);
  }

  function removeOption(idx: number) {
    setOptions(options.filter((_, i) => i !== idx));
  }

  function updateOption(idx: number, field: keyof IVROption, value: string | number | undefined) {
    setOptions(options.map((opt, i) => (i === idx ? { ...opt, [field]: value } : opt)));
  }

  // Atomic multi-field update (action + target together) - calling updateOption
  // twice in a row for the same row would have both calls read the same stale
  // `options` closure and the second call would clobber the first.
  function updateOptionFields(idx: number, patch: Partial<IVROption>) {
    setOptions((prev) => prev.map((opt, i) => (i === idx ? { ...opt, ...patch } : opt)));
  }

  async function onSubmit(values: IVRFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/ivrs/${ivr.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...values,
          options: JSON.stringify(options),
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));

      // Upload greeting if selected
      if (greetingFile) {
        const formData = new FormData();
        formData.append("file", greetingFile);
        await fetch(`/api/ivrs/${ivr.id}/greeting`, {
          method: "POST",
          body: formData,
        });
      }

      const updated: IVRMenu = await resp.json();
      onUpdated(updated);
      toast.success("IVR-Menü gespeichert.");
      onClose();
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteGreeting() {
    try {
      await fetch(`/api/ivrs/${ivr.id}/greeting`, { method: "DELETE" });
      toast.success("Begrüßung gelöscht.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Begrüßung konnte nicht gelöscht werden."));
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent size="form">
        <DialogHeader>
          <DialogTitle>IVR-Menü bearbeiten</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField control={form.control} name="number" render={({ field }) => (
                <FormItem>
                  <FormLabel>Durchwahl</FormLabel>
                  <FormControl><Input type="number" min={10} max={99} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField control={form.control} name="timeout" render={({ field }) => (
                <FormItem>
                  <FormLabel>Timeout (Sekunden)</FormLabel>
                  <FormControl><Input type="number" min={3} max={60} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="max_invalid_tries" render={({ field }) => (
                <FormItem>
                  <FormLabel>Max. Falscheingaben</FormLabel>
                  <FormControl><Input type="number" min={1} max={10} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>

            {/* Greeting upload */}
            <div>
              <FormLabel>Begrüßung (WAV-Datei)</FormLabel>
              <div className="flex items-center gap-2 mt-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".wav"
                  className="hidden"
                  onChange={(e) => setGreetingFile(e.target.files?.[0] ?? null)}
                />
                <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="h-4 w-4 mr-2" />
                  Datei wählen
                </Button>
                {ivr.greeting_file && (
                  <div className="flex items-center gap-2">
                    <Volume2 className="h-4 w-4 text-answer" />
                    <span className="text-sm">{ivr.greeting_file}</span>
                    <Button type="button" variant="ghost" size="icon" className="h-6 w-6 text-destructive" onClick={deleteGreeting}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                )}
                {greetingFile && (
                  <span className="text-sm text-muted-foreground">Neu: {greetingFile.name}</span>
                )}
              </div>
            </div>

            {/* Menu options */}
            <div>
              <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <FormLabel>Menü-Optionen</FormLabel>
                <Button type="button" variant="outline" size="sm" onClick={addOption}>
                  + Option hinzufügen
                </Button>
              </div>
              {options.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine Optionen.</p>
              ) : (
                <div className="space-y-2">
                  {options.map((opt, idx) => (
                    <div key={idx} className="flex flex-col gap-2 rounded-ctl border border-hair bg-raised p-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground">Taste:</span>
                        <Input
                          value={opt.key}
                          onChange={(e) => updateOption(idx, "key", e.target.value)}
                          className="h-8 w-12 font-mono text-center"
                          maxLength={2}
                        />
                      </div>
                      <DestinationField
                        value={{ type: opt.action, target: opt.target }}
                        onChange={(next) => updateOptionFields(idx, { action: next.type, target: next.target })}
                        allowedTypes={IVR_OPTION_ALLOWED_DESTINATION_TYPES}
                        extensions={extensions}
                        ringGroups={ringGroups}
                        ivrMenus={ivrs.filter((menu) => menu.id !== ivr.id)}
                        keyBy="number"
                        typeLabels={{ ivr: "Untermenü" }}
                        label=""
                        compact
                      />
                      <Input
                        value={opt.label ?? ""}
                        onChange={(e) => updateOption(idx, "label", e.target.value)}
                        placeholder="Bezeichnung (optional)"
                        className="h-8 w-full min-w-0 flex-1"
                      />
                      <Button type="button" variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => removeOption(idx)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Abbrechen</Button>
              <Button type="submit" disabled={saving}>{saving ? "Speichern..." : "Speichern"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
