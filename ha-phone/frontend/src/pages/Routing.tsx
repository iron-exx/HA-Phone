import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { type Route, type TimeCondition } from "@/types/api";
import { Button } from "@/components/ui/button";
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ---- Zod schemas ----
const routeSchema = z.object({
  did: z.string().min(1, "Required").max(32, "Max 32 chars"),
  destination_type: z.enum(["extension", "ring_group"]).default("extension"),
  destination_id: z.coerce.number().int().min(0, "Required"),
});

type RouteFormValues = z.infer<typeof routeSchema>;

const timeConditionSchema = z.object({
  name: z.string().min(1, "Required").max(64, "Max 64 chars"),
  did: z.string().min(1, "Required").max(32, "Max 32 chars"),
  open_hours_start: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
  open_hours_end: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
  open_days: z.string().min(1, "Required"),
  open_destination: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
  closed_destination: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
});

type TimeConditionFormValues = z.infer<typeof timeConditionSchema>;

// ---- Add Route dialog ----
function AddRouteDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (route: Route) => void;
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

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const created: Route = await resp.json();
      onCreated(created);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Route</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="did"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>DID (Phone Number)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. +4922222222" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="destination_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination Type</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="extension">Extension</SelectItem>
                      <SelectItem value="ring_group">Ring Group</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="destination_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination ID</FormLabel>
                  <FormControl>
                    <Input type="number" placeholder="e.g. 10" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Route"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit Route dialog ----
function EditRouteDialog({
  route,
  onClose,
  onUpdated,
}: {
  route: Route;
  onClose: () => void;
  onUpdated: (route: Route) => void;
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

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/routes/${route.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const updated: Route = await resp.json();
      onUpdated(updated);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Route</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="destination_type" render={({ field }) => (
              <FormItem>
                <FormLabel>Destination Type</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <FormControl>
                    <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="extension">Extension</SelectItem>
                    <SelectItem value="ring_group">Ring Group</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="destination_id" render={({ field }) => (
              <FormItem>
                <FormLabel>Destination ID</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Route"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Delete Route confirmation dialog ----
function DeleteRouteDialog({
  route,
  onClose,
  onDeleted,
}: {
  route: Route;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleDelete() {
    setDeleteLoading(true);
    try {
      const resp = await fetch(`/api/routes/${route.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      onDeleted(route.id);
      toast.success("Route deleted.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
      setDeleteLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !deleteLoading) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this route?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Delete this route? Inbound calls matching this DID will no longer be routed.
        </p>
        <DialogFooter>
          {!deleteLoading && (
            <Button variant="outline" onClick={onClose}>
              Keep Route
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteLoading}
          >
            {deleteLoading ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Add Time Condition Dialog ----
function AddTimeConditionDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (tc: TimeCondition) => void;
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
      closed_destination: undefined as unknown as number,
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
      if (!resp.ok) throw new Error(await resp.text());
      const created: TimeCondition = await resp.json();
      onCreated(created);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Time Condition</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input placeholder="e.g. Business Hours" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open From</FormLabel>
                  <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open Until</FormLabel>
                  <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>
            <FormField control={form.control} name="open_days" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Days</FormLabel>
                <FormControl><Input placeholder="mon-sun" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="open_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Destination (Extension)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="closed_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Closed Destination (Extension → Voicemail)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Time Condition"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit Time Condition Dialog ----
function EditTimeConditionDialog({
  condition,
  onClose,
  onUpdated,
}: {
  condition: TimeCondition;
  onClose: () => void;
  onUpdated: (tc: TimeCondition) => void;
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
      closed_destination: condition.closed_destination,
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
      if (!resp.ok) throw new Error(await resp.text());
      const updated: TimeCondition = await resp.json();
      onUpdated(updated);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Edit Time Condition</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input placeholder="e.g. Business Hours" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open From</FormLabel>
                  <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open Until</FormLabel>
                  <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>
            <FormField control={form.control} name="open_days" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Days</FormLabel>
                <FormControl><Input placeholder="mon-sun" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="open_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Destination (Extension)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="closed_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Closed Destination (Extension → Voicemail)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Time Condition"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Delete Time Condition Dialog ----
function DeleteTimeConditionDialog({
  condition,
  onClose,
  onDeleted,
}: {
  condition: TimeCondition;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const resp = await fetch(`/api/time-conditions/${condition.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      onDeleted(condition.id);
      toast.success("Time condition deleted.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
      setDeleting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !deleting) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this time condition?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Inbound calls matching {condition.did} will use the fallback catch-all routing.
        </p>
        <DialogFooter>
          {!deleting && (
            <Button variant="outline" onClick={onClose}>Keep</Button>
          )}
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting..." : "Delete Condition"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Ring groups ----
interface RingGroup {
  id: number;
  name: string;
  extension_numbers: string;
  ring_timeout: number;
}

function RingGroupsSection() {
  const [groups, setGroups] = useState<RingGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [numbers, setNumbers] = useState("");
  const [timeout, setTimeoutVal] = useState("30");
  const [saving, setSaving] = useState(false);

  function load() {
    fetch("/api/ring-groups")
      .then((r) => r.json())
      .then((data: RingGroup[]) => setGroups(data))
      .catch(() => toast.error("Rufgruppen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function addGroup() {
    if (!name.trim() || !numbers.trim()) {
      toast.error("Name und Nebenstellen (z.B. 10,11) sind erforderlich.");
      return;
    }
    if (!/^\d+(,\d+)*$/.test(numbers.trim())) {
      toast.error("Nebenstellen als kommagetrennte Nummern, z.B. 10,11,12.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/ring-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          extension_numbers: numbers.trim(),
          ring_timeout: Number(timeout) || 30,
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setName(""); setNumbers(""); setTimeoutVal("30");
      load();
      toast.success("Rufgruppe angelegt.");
    } catch {
      toast.error("Fehler beim Speichern.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteGroup(id: number) {
    try {
      const resp = await fetch(`/api/ring-groups/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error();
      setGroups((gs) => gs.filter((g) => g.id !== id));
      toast.success("Rufgruppe gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  return (
    <>
      <Separator className="my-8" />
      <div className="mb-2">
        <h2 className="text-xl font-semibold">Rufgruppen</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Mehrere Nebenstellen gleichzeitig klingeln lassen. Als Ziel einer eingehenden Route wählbar.
        </p>
      </div>
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Nebenstellen</TableHead>
              <TableHead>Timeout (s)</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((g) => (
              <TableRow key={g.id}>
                <TableCell className="font-medium">{g.name}</TableCell>
                <TableCell className="font-mono">{g.extension_numbers}</TableCell>
                <TableCell className="font-mono">{g.ring_timeout}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive"
                    aria-label={`Rufgruppe ${g.name} löschen`} onClick={() => deleteGroup(g.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Zentrale" className="h-9" /></TableCell>
              <TableCell><Input value={numbers} onChange={(e) => setNumbers(e.target.value)} placeholder="10,11,12" className="h-9 font-mono" /></TableCell>
              <TableCell><Input value={timeout} onChange={(e) => setTimeoutVal(e.target.value)} type="number" className="h-9 w-20 font-mono" /></TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addGroup} disabled={saving}>{saving ? "…" : "Hinzufügen"}</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </>
  );
}

// ---- Outbound dial rules ----
interface OutboundRule {
  id: number;
  pattern: string;
  strip: number;
  prepend: string;
  priority: number;
}

function OutboundRulesSection() {
  const [rules, setRules] = useState<OutboundRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [pattern, setPattern] = useState("");
  const [strip, setStrip] = useState("0");
  const [prepend, setPrepend] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    fetch("/api/outbound-rules")
      .then((r) => r.json())
      .then((data: OutboundRule[]) => setRules(data))
      .catch(() => toast.error("Ausgehende Regeln konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function addRule() {
    if (!pattern.trim()) {
      toast.error("Muster ist erforderlich (z.B. 0.).");
      return;
    }
    setSaving(true);
    try {
      const nextPriority = rules.length ? Math.max(...rules.map((r) => r.priority)) + 10 : 10;
      const resp = await fetch("/api/outbound-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pattern: pattern.trim(),
          strip: Number(strip) || 0,
          prepend: prepend.trim(),
          priority: nextPriority,
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setPattern(""); setStrip("0"); setPrepend("");
      load();
      toast.success("Regel hinzugefügt.");
    } catch {
      toast.error("Fehler beim Speichern. Läuft die PBX?");
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: number) {
    try {
      const resp = await fetch(`/api/outbound-rules/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error();
      setRules((rs) => rs.filter((r) => r.id !== id));
      toast.success("Regel gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  return (
    <>
      <Separator className="my-8" />
      <div className="mb-2">
        <h2 className="text-xl font-semibold">Ausgehende Regeln</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Gewählte Nummern werden vor dem Trunk umgeschrieben: <span className="font-mono">Muster</span> matcht,
          <span className="font-mono"> Entfernen</span> streicht führende Ziffern, <span className="font-mono">Voranstellen</span> ergänzt.
          Beispiel: <span className="font-mono">0.</span> · Entfernen <span className="font-mono">1</span> · Voranstellen <span className="font-mono">+49</span>.
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Muster</TableHead>
              <TableHead>Entfernen</TableHead>
              <TableHead>Voranstellen</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono">{r.pattern}</TableCell>
                <TableCell className="font-mono">{r.strip}</TableCell>
                <TableCell className="font-mono">{r.prepend || "—"}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    aria-label={`Regel ${r.pattern} löschen`}
                    onClick={() => deleteRule(r.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {/* Inline add row */}
            <TableRow>
              <TableCell>
                <Input value={pattern} onChange={(e) => setPattern(e.target.value)}
                  placeholder="z.B. 0." className="h-9 font-mono" />
              </TableCell>
              <TableCell>
                <Input value={strip} onChange={(e) => setStrip(e.target.value)}
                  type="number" min={0} className="h-9 w-20 font-mono" />
              </TableCell>
              <TableCell>
                <Input value={prepend} onChange={(e) => setPrepend(e.target.value)}
                  placeholder="z.B. +49" className="h-9 font-mono" />
              </TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addRule} disabled={saving}>
                  {saving ? "…" : "Hinzufügen"}
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </>
  );
}

// ---- Main page ----
export default function Routing() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);
  const [editRouteTarget, setEditRouteTarget] = useState<Route | null>(null);

  const [timeConditions, setTimeConditions] = useState<TimeCondition[]>([]);
  const [tcLoading, setTcLoading] = useState(true);
  const [tcDialogOpen, setTcDialogOpen] = useState(false);
  const [tcEditTarget, setTcEditTarget] = useState<TimeCondition | null>(null);
  const [tcDeleteTarget, setTcDeleteTarget] = useState<TimeCondition | null>(null);

  useEffect(() => {
    fetch("/api/routes")
      .then((r) => r.json())
      .then((data: Route[]) => setRoutes(data))
      .catch(() => toast.error("Failed to load routes."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetch("/api/time-conditions")
      .then((r) => r.json())
      .then((data: TimeCondition[]) => setTimeConditions(data))
      .catch(() => toast.error("Failed to load time conditions. Check that the PBX is running and try again."))
      .finally(() => setTcLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-xl font-semibold">Routing</h1>
        <Button onClick={() => setDialogOpen(true)}>Add Route</Button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : routes.length === 0 ? (
        <div className="text-center py-16">
          <h2 className="text-xl font-semibold mb-2">No routes configured</h2>
          <p className="text-muted-foreground text-sm max-w-sm mx-auto">
            Inbound routes control how incoming calls are distributed. Add a route to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>DID</TableHead>
              <TableHead>Destination Type</TableHead>
              <TableHead>Destination ID</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {routes.map((route) => (
              <TableRow key={route.id}>
                <TableCell className="font-medium">{route.did}</TableCell>
                <TableCell>{route.destination_type}</TableCell>
                <TableCell>{route.destination_id}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions for Route {route.did}</span>
                          </Button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent>Actions</TooltipContent>
                    </Tooltip>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        aria-label={`Edit Route ${route.did}`}
                        onClick={() => setEditRouteTarget(route)}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        aria-label={`Delete Route ${route.did}`}
                        className="text-destructive focus:text-destructive"
                        onClick={() => setDeleteTarget(route)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Ring groups section ─────────────────────────────────────────── */}
      <RingGroupsSection />

      {/* ─── Outbound dial rules section ─────────────────────────────────── */}
      <OutboundRulesSection />

      {/* ─── Time Conditions section ───────────────────────────────────── */}
      <Separator className="my-8" />

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Time Conditions</h2>
        <Button onClick={() => setTcDialogOpen(true)}>Add Time Condition</Button>
      </div>

      {tcLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : timeConditions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-sm font-semibold text-muted-foreground">No time conditions</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            Add a time condition to route inbound calls by schedule. Without one, all calls ring all extensions.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>DID</TableHead>
              <TableHead>Open Hours</TableHead>
              <TableHead>Days</TableHead>
              <TableHead>Open Destination</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {timeConditions.map((tc) => (
              <TableRow key={tc.id}>
                <TableCell className="font-medium">{tc.did}</TableCell>
                <TableCell>{tc.open_hours_start} – {tc.open_hours_end}</TableCell>
                <TableCell>{tc.open_days}</TableCell>
                <TableCell>ext {tc.open_destination}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions for {tc.did}</span>
                          </Button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent>Actions</TooltipContent>
                    </Tooltip>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        aria-label={`Edit Time Condition ${tc.did}`}
                        onClick={() => setTcEditTarget(tc)}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        aria-label={`Delete Time Condition ${tc.did}`}
                        className="text-destructive focus:text-destructive"
                        onClick={() => setTcDeleteTarget(tc)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Add Route Dialog */}
      {dialogOpen && (
        <AddRouteDialog
          open
          onClose={() => setDialogOpen(false)}
          onCreated={(route) => setRoutes((prev) => [...prev, route])}
        />
      )}

      {/* Delete Route Confirmation Dialog */}
      {deleteTarget && (
        <DeleteRouteDialog
          route={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={(id) => {
            setRoutes((prev) => prev.filter((r) => r.id !== id));
            setDeleteTarget(null);
          }}
        />
      )}

      {/* Edit Route Dialog */}
      {editRouteTarget && (
        <EditRouteDialog
          route={editRouteTarget}
          onClose={() => setEditRouteTarget(null)}
          onUpdated={(updated) => {
            setRoutes((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
            setEditRouteTarget(null);
          }}
        />
      )}

      {/* Add Time Condition Dialog */}
      {tcDialogOpen && (
        <AddTimeConditionDialog
          open
          onClose={() => setTcDialogOpen(false)}
          onCreated={(tc) => setTimeConditions((prev) => [...prev, tc])}
        />
      )}

      {/* Edit Time Condition Dialog */}
      {tcEditTarget && (
        <EditTimeConditionDialog
          condition={tcEditTarget}
          onClose={() => setTcEditTarget(null)}
          onUpdated={(updated) => {
            setTimeConditions((prev) => prev.map((tc) => (tc.id === updated.id ? updated : tc)));
            setTcEditTarget(null);
          }}
        />
      )}

      {/* Delete Time Condition Dialog */}
      {tcDeleteTarget && (
        <DeleteTimeConditionDialog
          condition={tcDeleteTarget}
          onClose={() => setTcDeleteTarget(null)}
          onDeleted={(id) => {
            setTimeConditions((prev) => prev.filter((tc) => tc.id !== id));
            setTcDeleteTarget(null);
          }}
        />
      )}
    </div>
  );
}
