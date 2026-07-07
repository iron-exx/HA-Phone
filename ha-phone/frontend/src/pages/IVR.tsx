import { useEffect, useState, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Pencil, Trash2, Upload, Volume2, PhoneIncoming } from "lucide-react";

import { type Extension, type RingGroup, type IVRMenu, type IVROption } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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

// ---- Zod schema ----
const ivrSchema = z.object({
  number: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
  name: z.string().min(1, "Required").max(64, "Max 64 chars"),
  timeout: z.coerce.number().int().min(3, "Min 3s").max(60, "Max 60s"),
  max_invalid_tries: z.coerce.number().int().min(1, "Min 1").max(10, "Max 10"),
});

type IVRFormValues = z.infer<typeof ivrSchema>;

// ---- Format option destination for display ----
function formatOptionTarget(
  action: string,
  target: number | undefined,
  extensions: Extension[],
  ringGroups: RingGroup[],
  ivrs: IVRMenu[]
): string {
  if (action === "hangup") return "Auflegen";
  if (action === "voicemail") return `Voicemail ${target}`;
  if (action === "extension") {
    const ext = extensions.find((e) => e.number === target);
    return ext ? `${target} ${ext.display_name}` : `Nebenstelle ${target}`;
  }
  if (action === "ring_group") {
    const rg = ringGroups.find((g) => g.number === target);
    return rg ? `${target} ${rg.name}` : `Rufgruppe ${target}`;
  }
  if (action === "ivr") {
    const ivr = ivrs.find((item) => item.number === target);
    return ivr ? `${target} ${ivr.name}` : `IVR ${target}`;
  }
  return String(target ?? "");
}

// ---- Add IVR Dialog ----
function AddIVRDialog({
  open,
  onClose,
  onCreated,
  extensions,
  ringGroups,
  ivrs,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (ivr: IVRMenu) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrs: IVRMenu[];
}) {
  const form = useForm<IVRFormValues>({
    resolver: zodResolver(ivrSchema),
    defaultValues: {
      number: undefined as unknown as number,
      name: "",
      timeout: 10,
      max_invalid_tries: 3,
    },
  });
  const [saving, setSaving] = useState(false);
  const [options, setOptions] = useState<IVROption[]>([]);
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

  async function onSubmit(values: IVRFormValues) {
    if (options.length === 0) {
      toast.error("Mindestens eine Menü-Option ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/ivrs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...values,
          options: JSON.stringify(options),
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const created: IVRMenu = await resp.json();

      // Upload greeting if selected
      if (greetingFile) {
        const formData = new FormData();
        formData.append("file", greetingFile);
        await fetch(`/api/ivrs/${created.id}/greeting`, {
          method: "POST",
          body: formData,
        });
      }

      onCreated(created);
      toast.success("IVR-Menü angelegt.");
      onClose();
    } catch (error) {
      toast.error(`Fehler: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="w-[min(720px,calc(100vw-2rem))] max-w-[min(720px,calc(100vw-2rem))] max-h-[90vh] overflow-y-auto overflow-x-hidden p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle>IVR-Menü anlegen</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField control={form.control} name="number" render={({ field }) => (
                <FormItem>
                  <FormLabel>Durchwahl</FormLabel>
                  <FormControl><Input type="number" min={10} max={99} placeholder="z.B. 50" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input placeholder="z.B. Hauptmenu" {...field} /></FormControl>
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
                {greetingFile && (
                  <span className="text-sm text-muted-foreground">{greetingFile.name}</span>
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
                <p className="text-sm text-muted-foreground">Noch keine Optionen. Fügen Sie mindestens eine hinzu.</p>
              ) : (
                <div className="space-y-2">
                  {options.map((opt, idx) => (
                    <div key={idx} className="flex flex-col gap-2 rounded-md border border-white/10 bg-white/[0.02] p-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground">Taste:</span>
                        <Input
                          value={opt.key}
                          onChange={(e) => updateOption(idx, "key", e.target.value)}
                          className="h-8 w-12 font-mono text-center"
                          maxLength={2}
                        />
                      </div>
                      <Select
                        value={opt.action}
                        onValueChange={(v) => updateOption(idx, "action", v)}
                      >
                        <SelectTrigger className="h-8 w-full sm:w-36">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="extension">Nebenstelle</SelectItem>
                          <SelectItem value="ring_group">Rufgruppe</SelectItem>
                          <SelectItem value="ivr">Untermenü</SelectItem>
                          <SelectItem value="voicemail">Voicemail</SelectItem>
                          <SelectItem value="hangup">Auflegen</SelectItem>
                        </SelectContent>
                      </Select>
                      {opt.action !== "hangup" && (
                        <Select
                          value={opt.target ? String(opt.target) : ""}
                          onValueChange={(v) => updateOption(idx, "target", Number(v))}
                        >
                          <SelectTrigger className="h-8 w-full sm:w-48">
                            <SelectValue placeholder="Ziel wählen" />
                          </SelectTrigger>
                          <SelectContent>
                            {opt.action === "extension" && extensions.map((e) => (
                              <SelectItem key={e.number} value={String(e.number)}>
                                {e.number} {e.display_name}
                              </SelectItem>
                            ))}
                            {opt.action === "ring_group" && ringGroups.map((g) => (
                              <SelectItem key={g.number} value={String(g.number)}>
                                {g.number} {g.name}
                              </SelectItem>
                            ))}
                            {opt.action === "ivr" && ivrs.map((menu) => (
                              <SelectItem key={menu.number} value={String(menu.number)}>
                                {menu.number} {menu.name}
                              </SelectItem>
                            ))}
                            {opt.action === "voicemail" && extensions.map((e) => (
                              <SelectItem key={e.number} value={String(e.number)}>
                                {e.number} {e.display_name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
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
              <Button type="submit" disabled={saving}>{saving ? "Speichern..." : "IVR anlegen"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit IVR Dialog ----
function EditIVRDialog({
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
    resolver: zodResolver(ivrSchema),
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
      if (!resp.ok) throw new Error(await resp.text());

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
      toast.error(`Fehler: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function deleteGreeting() {
    try {
      await fetch(`/api/ivrs/${ivr.id}/greeting`, { method: "DELETE" });
      toast.success("Begrüßung gelöscht.");
    } catch {
      toast.error("Begrüßung konnte nicht gelöscht werden.");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="w-[min(720px,calc(100vw-2rem))] max-w-[min(720px,calc(100vw-2rem))] max-h-[90vh] overflow-y-auto overflow-x-hidden p-4 sm:p-6">
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
                    <Volume2 className="h-4 w-4 text-green-500" />
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
                    <div key={idx} className="flex flex-col gap-2 rounded-md border border-white/10 bg-white/[0.02] p-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground">Taste:</span>
                        <Input
                          value={opt.key}
                          onChange={(e) => updateOption(idx, "key", e.target.value)}
                          className="h-8 w-12 font-mono text-center"
                          maxLength={2}
                        />
                      </div>
                      <Select
                        value={opt.action}
                        onValueChange={(v) => updateOption(idx, "action", v)}
                      >
                        <SelectTrigger className="h-8 w-full sm:w-36">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="extension">Nebenstelle</SelectItem>
                          <SelectItem value="ring_group">Rufgruppe</SelectItem>
                          <SelectItem value="ivr">Untermenü</SelectItem>
                          <SelectItem value="voicemail">Voicemail</SelectItem>
                          <SelectItem value="hangup">Auflegen</SelectItem>
                        </SelectContent>
                      </Select>
                      {opt.action !== "hangup" && (
                        <Select
                          value={opt.target ? String(opt.target) : ""}
                          onValueChange={(v) => updateOption(idx, "target", Number(v))}
                        >
                          <SelectTrigger className="h-8 w-full sm:w-48">
                            <SelectValue placeholder="Ziel wählen" />
                          </SelectTrigger>
                          <SelectContent>
                            {(opt.action === "extension" || opt.action === "voicemail") && extensions.map((e) => (
                              <SelectItem key={e.number} value={String(e.number)}>
                                {e.number} {e.display_name}
                              </SelectItem>
                            ))}
                            {opt.action === "ring_group" && ringGroups.map((g) => (
                              <SelectItem key={g.number} value={String(g.number)}>
                                {g.number} {g.name}
                              </SelectItem>
                            ))}
                            {opt.action === "ivr" && ivrs.filter((menu) => menu.id !== ivr.id).map((menu) => (
                              <SelectItem key={menu.number} value={String(menu.number)}>
                                {menu.number} {menu.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
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

// ---- Main IVR page ----
export default function IVR() {
  const [ivrs, setIvrs] = useState<IVRMenu[]>([]);
  const [loading, setLoading] = useState(true);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<IVRMenu | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<IVRMenu | null>(null);

  function load() {
    Promise.all([
      fetch("/api/ivrs").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
    ])
      .then(([ivrData, extData, rgData]: [IVRMenu[], Extension[], RingGroup[]]) => {
        setIvrs(ivrData);
        setExtensions(extData);
        setRingGroups(rgData);
      })
      .catch(() => toast.error("IVR-Menüs konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      const resp = await fetch(`/api/ivrs/${deleteTarget.id}`, { method: "DELETE" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail || "Fehler beim Löschen.");
      }
      setIvrs((prev) => prev.filter((i) => i.id !== deleteTarget.id));
      toast.success("IVR-Menü gelöscht.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Löschen.");
    }
    setDeleteTarget(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <PhoneIncoming className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-xl font-semibold">IVR-Menüs</h1>
        </div>
        <Button onClick={() => setDialogOpen(true)}>Neues IVR-Menü</Button>
      </div>

      <p className="text-sm text-muted-foreground mb-6">
        Digitaler Empfang: Anrufer hören eine Begrüßung und werden per Tastendruck weitergeleitet.
      </p>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : ivrs.length === 0 ? (
        <div className="text-center py-16">
          <PhoneIncoming className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold mb-2">Noch keine IVR-Menüs</h2>
          <p className="text-muted-foreground text-sm max-w-sm mx-auto">
            Legen Sie ein IVR-Menü an, um Anrufer automatisch per Tastendruck weiterzuleiten.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Durchwahl</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Optionen</TableHead>
              <TableHead>Timeout</TableHead>
              <TableHead>Begrüßung</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ivrs.map((ivr) => {
              const options: IVROption[] = (() => {
                try { return JSON.parse(ivr.options || "[]"); } catch { return []; }
              })();
              return (
                <TableRow key={ivr.id}>
                  <TableCell className="font-mono font-medium">{ivr.number}</TableCell>
                  <TableCell className="font-medium">{ivr.name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {options.map((opt, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-violet-500/10 text-xs font-mono">
                          <span className="font-bold">{opt.key}</span>
                          <span className="text-muted-foreground">→</span>
                          <span>{formatOptionTarget(opt.action, opt.target, extensions, ringGroups, ivrs)}</span>
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono">{ivr.timeout}s</TableCell>
                  <TableCell>
                    {ivr.greeting_file ? (
                      <span className="inline-flex items-center gap-1 text-green-500 text-xs">
                        <Volume2 className="h-3 w-3" />
                        Vorhanden
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">Keine</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditTarget(ivr)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => setDeleteTarget(ivr)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {/* Add IVR Dialog */}
      {dialogOpen && (
        <AddIVRDialog
          open
          onClose={() => setDialogOpen(false)}
          onCreated={(ivr) => setIvrs((prev) => [...prev, ivr])}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrs={ivrs}
        />
      )}

      {/* Edit IVR Dialog */}
      {editTarget && (
        <EditIVRDialog
          ivr={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={(updated) => {
            setIvrs((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
            setEditTarget(null);
          }}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrs={ivrs}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteTarget && (
        <Dialog open onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>IVR-Menü löschen?</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Möchten Sie das IVR-Menü "{deleteTarget.name}" wirklich löschen?
            </p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>Abbrechen</Button>
              <Button variant="destructive" onClick={handleDelete}>Löschen</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
